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
- Keep hard scheduling/rate guards deterministic in runtime code.
- Support reactive "create then reference" via a compact escalation flag from normal action output.

This gives autonomous submolt creation/posting with strong token efficiency and clear architecture boundaries.
