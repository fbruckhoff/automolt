---
includes: Analysis and design options for enabling fully autonomous submolt creation and submolt posting in the automation runtime.
excludes: Full implementation patch details and unrelated CLI command documentation.
related: ../design-docs/automation-system.md, ../design-docs/automation-runtime-design.md, ../exec-plans/completed/2026-03-16-18-03-39-submolt-create-and-post-support.md
---

# Automation + Submolt Autonomy Report

## Objective

Enable an agent to autonomously:

1. create a submolt,
2. post into that submolt,
3. optionally reference that new submolt from a response flow,
4. enforce time-frequency rules (for example every 12 or 24 hours),

while preserving token efficiency and not bloating the normal post/comment reply loop.

## Current System Reality (Verified)

From current code and docs:

- Automation is queue-centric around discovered posts/comments (`automation_store.items`).
- The action stage structured output is `ActionPlan(reply_text, upvote)` only.
- `BEHAVIOR.md` is injected into action-stage prompts for queue-item replies.
- Action execution currently writes comments/upvotes; it does not run submolt/post creation paths.
- Prompt payloads currently include item metadata and rationale, but no explicit time-policy metadata such as last submolt creation timestamp.

Implication: autonomous submolt creation is currently out-of-band relative to the queue action schema.

## Core Design Tension

You identified the key tension correctly:

- adding `create_submolt` fields directly to the existing action schema is convenient,
- but it increases prompt/schema payload size on every normal reply decision,
- and normal reply cycles are the highest-frequency path.

Given token efficiency goals, the baseline action schema should remain compact for standard comment/reply work.

## Recommended Architecture

## 1) Introduce a Separate Submolt Planner Stage (Preferred)

Add a dedicated planner stage invoked conditionally (not per queue item):

- stage name: `submolt_planner`
- invocation conditions:
  - scheduled cadence due (for example once per 12h or 24h), or
  - explicit escalation trigger from a relevant queue item.

This isolates submolt logic from the hot path and preserves current action-stage token efficiency.

## 2) Keep Existing `ActionPlan` for Normal Replies

Do not overload `ActionPlan` with full create/post payload fields for every action request.

Optionally add one compact escalation signal only, for reactive chaining:

- `promote_to_submolt: bool = false`
- `promotion_topic: str | None`

This keeps per-item schema overhead minimal.

## 3) Add a New Structured Output Model for Submolt Planner

Example model contract:

- `should_create_submolt: bool`
- `submolt_name: str | None`
- `display_name: str | None`
- `description: str | None`
- `allow_crypto: bool`
- `should_post: bool`
- `post_title: str | None`
- `post_content: str | None`
- `post_url: str | None`
- `should_link_in_followup_reply: bool`
- `followup_reply_text: str | None`
- `decision_rationale: str`

Use strict schema validation, same as existing OpenAI structured-output flow.

## 4) Add Submolt-Automation Metadata to Runtime Context

For time-based reasoning, pass explicit metadata in planner prompts:

- `current_utc`
- `last_submolt_created_at_utc` (or null)
- `hours_since_last_submolt_creation`
- `last_submolt_posted_at_utc` (or null)
- `hours_since_last_submolt_post`
- `owned_submolts_recent` (compact list)
- `source_trigger` (`scheduled` or `reactive`)
- `source_item_id` and short source summary for reactive mode

This gives the model deterministic scheduling context without requiring it to infer timing from prose.

## 5) Persist Submolt Automation History

Add persistence for idempotence and scheduling gates (new SQLite table or JSON log):

- `event_id`
- `event_type` (`create_submolt`, `create_post`, `reply_link`)
- `submolt_name`
- `post_id`
- `created_at_utc`
- `source_trigger`
- `source_item_id`
- `status` (`success`, `failed`)
- `error_summary`

This supports accurate `last_*` metadata and auditability.

## BEHAVIOR.md Strategy for Token Efficiency

## Recommended: Split Prompt Domains

Use two behavior prompt domains:

- `BEHAVIOR.md` (existing): normal reply/upvote behavior.
- `BEHAVIOR_SUBMOLT.md` (new): submolt creation/post policy and cadence rules.

Load `BEHAVIOR_SUBMOLT.md` only when submolt planner is invoked.

This avoids paying submolt-policy tokens on every queue item.

## Cadence Change UX: Immediate Refresh Strategy

The current UX risk is stale cadence behavior after operators edit `BEHAVIOR_SUBMOLT.md` (for example, changing from every 24h to every 2h). The most pragmatic and effective approach is to combine lightweight automatic change detection with an explicit manual reload command.

Recommended mechanism:

1. Track a persisted behavior-file fingerprint using `os.stat` metadata (`st_mtime_ns` + `st_size`) for `BEHAVIOR_SUBMOLT.md`.
2. On every automation tick, compare the current fingerprint to the last parsed fingerprint.
3. If changed, re-parse submolt cadence/policy immediately before guard evaluation.
4. Recompute due-state immediately using the new cadence against persisted event history (`last_submolt_created_at_utc`), so shortened intervals can trigger without waiting for the old interval window.
5. Add `automolt automation reload --handle <handle>` to force refresh when operators want immediate deterministic control.

Why this is the pragmatic default:

- `stat` checks are cheap and safe to run every tick.
- No file-watcher daemon complexity or platform-specific edge cases.
- Manual reload provides deterministic operator control even in rare timestamp-granularity/editor edge cases.

## If Single-File Policy Is Required

If you must keep one file, parse a compact machine-readable frontmatter block and only inject the relevant section:

Example frontmatter fields:

- `submolt_enabled: true`
- `submolt_create_interval_hours: 12`
- `submolt_topic_policy: "topic xyz"`
- `submolt_max_creations_per_day: 1`

Then include only those fields (plus a short behavior excerpt) in planner prompts.

## Autonomous Pathways

## A) Scheduled Proactive Path (Daily/12h)

1. Tick starts.
2. Scheduler checks submolt cadence due state.
3. If due, invoke submolt planner stage.
4. If `should_create_submolt`, execute `SubmoltService.create_submolt`.
5. If `should_post`, execute `PostService.create_post` into created/target submolt.
6. Reuse existing verification flow automatically.
7. Persist event log + update last timestamps.

## B) Reactive Escalation Path (In Response to Post/Comment)

1. Normal analysis/action runs for queue item.
2. Action output includes compact escalation signal (`promote_to_submolt=true`) when appropriate.
3. Runtime invokes submolt planner in reactive mode with source context.
4. Create submolt + post.
5. Optionally publish a follow-up reply referencing the new submolt link.

This supports your "first create submolt, then point to it" scenario without bloating all action calls.

## Scheduling and Policy Controls

Recommended enforcement hierarchy:

1. Hard runtime guards (deterministic):
   - behavior policy refresh on file fingerprint change (or explicit reload),
   - minimum interval not elapsed => skip planner call,
   - max creations/day reached => skip,
   - duplicate submolt name collision handling.

2. LLM planner policy (soft):
   - topic fit,
   - naming/content quality,
   - whether to post immediately.

3. Command/service validation (existing):
   - submolt name constraints,
   - post content/url exclusivity,
   - verification handling.

This prevents accidental over-creation even if model output is noisy.

## Minimal Incremental Rollout Plan

Phase 1 (low risk):

- Add deterministic cadence gate + persistence timestamps for submolt events.
- Add planner stage + `BEHAVIOR_SUBMOLT.md` support.
- Add per-tick `BEHAVIOR_SUBMOLT.md` fingerprint checks with immediate re-parse/recompute.
- Add explicit `automolt automation reload` command to force behavior refresh.
- Execute create+post autonomously only from scheduled trigger.

Phase 2:

- Add reactive escalation signal in action schema.
- Enable create+post followed by link reply when reactive trigger present.

Phase 3:

- Add richer policy controls (`max/day`, allowed topics, naming templates).
- Add monitoring/status surfacing for submolt automation events.

## Recommendation Summary

- Do not put full `create_submolt` payload fields into the always-on action schema.
- Add a separate submolt planner stage and optional separate behavior prompt file.
- Inject explicit time metadata (`current_utc`, `last_submolt_created_at_utc`, elapsed hours) for correct interval reasoning.
- Detect `BEHAVIOR_SUBMOLT.md` changes per tick via persisted file fingerprint and re-parse immediately.
- Provide `automolt automation reload` as a manual override for immediate config refresh.
- Keep hard scheduling/rate guards deterministic in runtime code.
- Support reactive "create then reference" via a compact escalation flag from normal action output.

This gives autonomous submolt creation/posting with strong token efficiency and clear architecture boundaries.

# Decision

Verdict: **approve the separate planner architecture**, and implement it as a staged rollout that keeps the current analysis/action hot path stable.

## Final implementation decision

1. Keep the existing `ActionPlan(reply_text, upvote)` as the default queue-item contract.
2. Add a new conditional `submolt_planner` stage that runs outside the per-item loop.
3. Introduce deterministic runtime guards first (interval + max/day + duplicate-name prevention) before any planner call.
4. Add dedicated submolt automation persistence (event history with timestamps and status) to support idempotence and scheduling context.
5. Split prompt domains by adding `BEHAVIOR_SUBMOLT.md`, loaded only for planner invocations.
6. Add per-tick behavior file change detection (`st_mtime_ns` + `st_size`) and immediate cadence refresh.
7. Add `automolt automation reload` to force re-parse and recompute due-state on demand.

## Scope by phase

- **Phase 1 (implementation target now):** scheduled proactive creation/posting only, backed by deterministic guards and submolt event persistence.
- **Phase 2:** reactive escalation path from queue-item action output (compact escalation fields only).
- **Phase 3:** richer policy controls and runtime status/monitor surfacing for submolt automation events.

## Why this is final

- It matches current architecture boundaries (`SchedulerService` owns when; `AutomationService` owns what).
- It preserves token efficiency on the highest-frequency path.
- It reuses existing `SubmoltService`, `PostService`, and verification behavior without overloading current queue semantics.
- It minimizes regression risk by introducing autonomy through an additive, gated path rather than changing the existing action contract for every item.
