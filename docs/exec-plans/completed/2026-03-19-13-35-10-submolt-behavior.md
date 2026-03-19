# Harden submolt planner cadence, duplicate prevention, and self-interaction safety

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This document must be maintained in accordance with `.agents/PLANS.md`.

## Purpose / Big Picture

After this change, `automolt automation start` must not create submolts more frequently than the cadence defined in `BEHAVIOR_SUBMOLT.md`, must avoid duplicate or near-duplicate submolts, must treat crypto as disallowed by default, and must never comment on content authored by the same agent. The planner will receive richer runtime context (current time, last submolt creation time, and up to the last 10 submolt titles) exactly at planner decision time so it can follow natural-language cadence rules such as “once per week.”

A human should be able to verify this by running foreground automation in dry mode and live mode and observing that: (1) planner skips creation when weekly cadence is not satisfied, (2) planner sees recent-title context and declines duplicates, (3) search continues to discover new posts/comments even while backlog exists, including activity inside the agent’s own submolts authored by other agents, and (4) the agent never posts a comment on its own posts or own comments.

Documentation depth decision: `full`, because this is cross-cutting runtime behavior spanning planner policy interpretation, prompt construction, queue/search semantics, and safety invariants.

## Progress

- [x] (2026-03-19 13:18Z) Reviewed architecture and automation design docs (`ARCHITECTURE.md`, `docs/design-docs/_index.md`, `docs/design-docs/automation-system.md`).
- [x] (2026-03-19 13:24Z) Traced planner cadence and prompt composition paths in `automolt/services/automation_service.py`.
- [x] (2026-03-19 13:29Z) Traced search ingestion and queue behavior in `automation_service.py`, `search_service.py`, and `automation_store.py`.
- [x] (2026-03-19 13:33Z) Identified current prompt defaults and policy/runtime log contracts in `system_prompt_store.py` and `automation_log_store.py`.
- [x] (2026-03-19 13:38Z) Authored this active ExecPlan with concrete edits, tests, and acceptance criteria.
- [x] (2026-03-19 13:31Z) Implemented planner-context and cadence hardening changes in `automation_service.py` and `automation_log_store.py` (recent titles, cadence prose parsing fallback, duplicate/near-duplicate guards, runtime planner guardrail prompt composition).
- [x] (2026-03-19 13:32Z) Implemented search freshness and self-interaction safeguards (`execute_heartbeat_cycle` search-every-cycle semantics, queue `author_name` persistence, author-resolution fallback, deterministic `self-authored-item` skip guard before comment writes).
- [x] (2026-03-19 13:34Z) Added and expanded tests in `tests/test_submolt_planner_runtime.py`, `tests/test_automation_log_store.py`, and `tests/test_automation_store_runtime_state.py`; full unittest suite passed.
- [x] (2026-03-19 13:35Z) Updated design docs (`automation-system.md`, `automation-runtime-design.md`, `_index.md`) and prepared plan archival path.

## Surprises & Discoveries

- Observation: Deterministic cadence enforcement currently defaults to `24` hours unless frontmatter explicitly sets `submolt_create_interval_hours`, even when `BEHAVIOR_SUBMOLT.md` body prose says “once per week.”
  Evidence: `automolt/services/automation_service.py` uses `DEFAULT_SUBMOLT_CREATE_INTERVAL_HOURS = 24` and `_parse_submolt_policy_prompt(...)` only reads cadence from frontmatter fields.

- Observation: The planner user prompt already includes `current_utc` and `last_submolt_created_at_utc`, but there is no recent-submolt-title history in planner context.
  Evidence: `_build_submolt_planner_user_prompt(...)` includes timestamps but not a list of historical submolt titles.

- Observation: Duplicate prevention is currently narrow: exact-name check against successful `create_submolt` events only.
  Evidence: `_evaluate_submolt_runtime_guards(...)` only calls `automation_log_store.has_successful_submolt_name(...)` for exact normalized name matches.

- Observation: Search refill currently runs only when there are no unanalyzed queue rows, which can starve discovery of newer content during long-lived backlog processing.
  Evidence: `execute_heartbeat_cycle(...)` only calls `_search_and_enqueue(...)` when `automation_store.has_unanalyzed(...)` is false.

- Observation: There is no deterministic “self-authored target” guard before posting a comment.
  Evidence: `_execute_action_for_relevant_item(...)` calls `self._api.add_comment(...)` without checking whether the target post/comment author matches the running handle.

- Observation: The default submolt planner system prompt does not explicitly forbid duplicate creation and does not enforce “crypto disallowed unless explicitly allowed by behavior policy.”
  Evidence: `automolt/persistence/system_prompt_store.py` default `submolt_planner` prompt only defines JSON schema keys and generic output constraints.

- Observation: Repository-wide `ruff check .` currently fails due a pre-existing import-order lint in `automolt/services/agent_service.py` unrelated to this ExecPlan scope.
  Evidence: `uv run ruff check .` output reports `I001` in `automolt/services/agent_service.py:7`; changed files in this plan pass `ruff check`.

## Decision Log

- Decision: Keep deterministic runtime guards as the final enforcement layer, even after improving planner prompt context.
  Rationale: LLM instruction compliance can drift; hard guards protect against accidental over-creation and unsafe self-interactions.
  Date/Author: 2026-03-19 / Cascade

- Decision: Add dynamic planner system-prompt augmentation at runtime (not just static file edits) to inject immutable guardrails and current context.
  Rationale: Existing workspaces may already have custom `SUBMOLT_PLANNER_SYS.md`; runtime augmentation guarantees required instructions and context are always present without requiring manual prompt migration.
  Date/Author: 2026-03-19 / Cascade

- Decision: Treat crypto as denied by default in both prompt-level instruction and runtime execution safeguards.
  Rationale: User requirement is explicit; dual enforcement avoids accidental `allow_crypto=true` decisions from model output.
  Date/Author: 2026-03-19 / Cascade

- Decision: Execute search every heartbeat cycle before queue-item processing, while retaining queue dedupe by `item_id`.
  Rationale: This removes search starvation and preserves existing one-action-per-cycle semantics, because processing still short-circuits after acted outcomes.
  Date/Author: 2026-03-19 / Cascade

- Decision: Introduce explicit self-author metadata and fallback author-resolution checks before any comment write call.
  Rationale: “Never comment on own posts/comments” must be guaranteed for both newly discovered and legacy queue rows.
  Date/Author: 2026-03-19 / Cascade

## Outcomes & Retrospective

Implemented outcome matches the plan purpose. Planner/runtime now enforces cadence and duplicate protection deterministically with richer context (`recent_submolt_titles`) and runtime-composed planner guardrails. Search now executes every heartbeat cycle to preserve discovery freshness under backlog conditions. Action writes now enforce strict self-interaction safety by resolving author metadata (persisted and fallback API) and skipping self-authored targets with explicit rationale.

Validation outcomes:

- `uv run python -m unittest discover -s tests` -> `Ran 28 tests ... OK`.
- Targeted suites for this plan (`tests/test_submolt_planner_runtime.py`, `tests/test_automation_log_store.py`, `tests/test_automation_store_runtime_state.py`) all pass.
- Changed files pass `uv run ruff check <changed-files...>`.

Remaining gap outside plan scope: one pre-existing `ruff I001` import-order issue in `automolt/services/agent_service.py` is still present when running `ruff check .` globally.

## Context and Orientation

Automation runtime control flow is centered in `automolt/services/automation_service.py`, invoked by scheduler orchestration in `automolt/services/scheduler_service.py` and surfaced by CLI entrypoints in `automolt/commands/automation/scheduler_command.py`. Queue persistence is SQLite-backed in `automolt/persistence/automation_store.py`, planner event history is JSONL-backed in `automolt/persistence/automation_log_store.py`, and search/content hydration calls are encapsulated in `automolt/services/search_service.py`.

A “planner cycle” means the submolt planner stage that may create a submolt and optionally create a post. A “queue cycle” means normal analysis/action of discovered posts/comments. Current runtime is planner-first, then queue. However, current search refill runs only when there are no unanalyzed rows, which can suppress fresh discovery for long stretches. A “self-authored item” means either a post authored by the running agent handle or a comment authored by the running agent handle.

`BEHAVIOR_SUBMOLT.md` currently contributes two kinds of signal: deterministic frontmatter controls and freeform body text delivered to the planner LLM. The bug report shows this is insufficient today for weekly cadence safety because prose-only cadence can be ignored by deterministic defaults.

## Plan of Work

Milestone 1 hardens planner decision inputs and deterministic cadence rules. Extend planner context so the LLM receives current UTC, last successful submolt create timestamp, and a normalized list of the most recent submolt titles (up to 10) immediately at planner decision time. Add runtime-composed planner system prompt augmentation that always includes immutable rules: do not create duplicates, do not allow crypto unless explicitly authorized by behavior policy, and decline creation when cadence is not satisfied.

Milestone 2 fixes cadence and duplicate enforcement gaps. Extend policy parsing so cadence can be represented in deterministic controls beyond the current fixed defaults. Preserve explicit frontmatter as highest priority; when frontmatter cadence is absent, parse a constrained set of natural-language cadence forms from body text (for example: “once per week”, “every 7 days”, “every 2 weeks”). Apply deterministic guard evaluation before planner invocation and again after planner output validation. Expand duplicate checks from exact-name only to include recent-title normalization and “recently created equivalent” detection.

Milestone 3 addresses search freshness and self-interaction safety. Modify heartbeat behavior so search executes every cycle (with dedupe still in persistence), including cycles with existing backlog. Persist source-author metadata in queue items and add a strict no-self-comment guard prior to posting replies. For legacy queue rows missing author metadata, resolve author from canonical API payload before action write calls. Mark self-authored targets as analyzed/relevant-not-acted with a deterministic rationale (for example `self-authored-item`) and never call `add_comment`.

Milestone 4 adds tests, operator observability, and documentation updates. Add targeted tests for cadence parsing, prompt augmentation payload, duplicate prevention behavior, search-each-cycle semantics, own-submolt discovery coverage, and no-self-comment guarantees. Update design docs to reflect the new guarantees and diagnostic outputs.

## Concrete Steps

All commands run from repository root:

    /Users/franz/Desktop/Tapsweets/Apps/CLI/automolt/automolt

Implementation sequence:

1. Extend planner event/history contracts in `automolt/persistence/automation_log_store.py`.

   Add helper(s) to fetch recent successful submolt creations with configurable limit and normalized title extraction. Extend event payload support (additive, backward-compatible) to include optional display title when available.

2. Add planner-context enrichment in `automolt/services/automation_service.py`.

   Expand `SubmoltPlannerContext` and planner prompt builders to include:

    - `current_utc` (already present, retain),
    - `last_submolt_created_at_utc` (already present, retain),
    - `recent_submolt_titles` (new, max 10, newest-first normalized string list),
    - `recent_submolt_created_at_utc` entries if needed for tie-breaking.

3. Add runtime-composed planner system prompt guardrail in `automation_service.py`.

   Introduce helper such as `_compose_submolt_planner_system_prompt(...)` that appends a non-overridable policy block to loaded `SUBMOLT_PLANNER_SYS.md`. The appended block must explicitly instruct:

    - never create duplicate or near-duplicate submolts,
    - compare against provided recent title list,
    - default `allow_crypto=false`,
    - only set `allow_crypto=true` when behavior policy explicitly allows crypto.

4. Harden policy parsing and deterministic cadence guards.

   In `automation_service.py`, extend `SubmoltPlannerPolicy` with explicit fields needed for cadence and crypto allow override. Keep frontmatter as primary deterministic source; add constrained natural-language cadence parsing fallback from body text when frontmatter cadence is absent. Ensure parse failures are explicit and observable (planner failure/skip with actionable reason) rather than silent fallback to 24h defaults.

5. Enforce duplicate prevention with broader checks.

   Add normalized-title duplicate checks that compare planned name/display name against recent successful submolt history (not only exact slug match). Reject plans that are duplicates or near-duplicates per deterministic normalization rules and record skip reason.

6. Implement crypto default deny and explicit override.

   Before submolt creation call, enforce policy:

    - if policy does not explicitly allow crypto, force `allow_crypto=False` regardless of model output,
    - if policy explicitly allows crypto, preserve planner output.

7. Make search run every heartbeat cycle.

   In `execute_heartbeat_cycle(...)`, run `_search_and_enqueue(...)` at cycle start (after planner-first phase and before queue scan), not only when queue is empty. Keep dedupe in `automation_store.insert_items(...)` unchanged.

8. Add source-author persistence and self-comment guards.

   Update queue schema and model contracts (`automolt/models/automation.py`, `automolt/persistence/automation_store.py`) to store `author_name` for search-derived items. Populate from `SearchResult.author.name` in `_search_and_enqueue(...)`. In `_execute_action_for_relevant_item(...)`, add deterministic guard that blocks comment posting when item author matches current handle. For legacy rows lacking `author_name`, resolve author via API fetch before writing comments.

9. Expand search/content helper metadata retrieval.

   In `automolt/services/search_service.py`, add helper(s) to fetch author metadata alongside content for post/comment queue items to support self-authored fallback checks and diagnostics.

10. Improve runtime observability.

   Extend heartbeat events and log messages with search diagnostics useful for this bug class: raw search result count, inserted post/comment counts, skipped-self-authored counts, and planner skip reasons tied to cadence/duplicate/crypto guardrails.

11. Add and update tests in `tests/`.

   Add focused tests for:

    - weekly cadence parsing from prose and/or frontmatter,
    - planner context includes current time, last create timestamp, and last 10 titles,
    - duplicate-title guard blocks repeated or near-duplicate plans,
    - crypto default deny behavior unless explicit behavior override,
    - search executes each cycle even with existing unanalyzed backlog,
    - comments in own submolts authored by other agents are still enqueued,
    - self-authored post/comment targets never trigger `add_comment`.

12. Update docs.

   Update `docs/design-docs/automation-system.md`, `docs/design-docs/automation-runtime-design.md`, and `docs/design-docs/_index.md` to capture final planner guardrails and search/self-interaction behavior.

Validation commands during and after implementation:

    uv run python -m unittest discover -s tests
    uv run python -m unittest tests/test_submolt_planner_runtime.py
    uv run python -m unittest tests/test_automation_log_store.py
    uv run python -m unittest tests/test_automation_store_runtime_state.py
    uv run ruff check .
    uv run python -m automolt.main automation start --handle <handle> --dry
    uv run python -m automolt.main automation tick --handle <handle> --dry

Expected verification evidence should include concise output proving:

    - planner skip reason `interval-not-elapsed` when weekly policy is not due,
    - planner prompt context references recent submolt titles,
    - search diagnostics report post/comment discovery each cycle,
    - self-authored items are skipped with explicit rationale and no reply write.

## Validation and Acceptance

Acceptance is met when all behavior checks below are true:

First, cadence correctness is observable. If `BEHAVIOR_SUBMOLT.md` says weekly cadence and one successful submolt creation happened within the last seven days, the next scheduled/forced planner evaluation must skip with an explicit cadence reason. This must hold even when frontmatter cadence is omitted and prose cadence is used.

Second, duplicate prevention is observable. Planner receives up to the last 10 submolt titles and declines creation when the planned title/name is duplicate or near-duplicate to recent history. Deterministic runtime guard must block creation even if the model attempts a duplicate.

Third, crypto policy is observable. Without explicit crypto allowance in `BEHAVIOR_SUBMOLT.md`, created submolts always use `allow_crypto=false`. With explicit allowance, planner may set true.

Fourth, search freshness is observable during `automation start`. New matching posts/comments are discovered on each cycle regardless of existing queue backlog, with dedupe preventing duplicate queue rows.

Fifth, self-interaction safety is guaranteed. The agent never calls comment creation against a post/comment authored by itself. This must be proven by automated tests and by dry-run/event evidence.

## Idempotence and Recovery

All storage changes must be additive and idempotent. SQLite schema evolution should use migration checks before adding new columns. JSONL event parsing must remain backward-compatible with older entries missing new optional fields.

If cadence parsing fails for malformed behavior text, planner should fail/skip safely with actionable reason and continue heartbeat stability. If author metadata is unavailable for a legacy queue row and cannot be resolved from API, treat that row as non-actionable for safety and record rationale rather than risking a self-comment.

If runtime prompt augmentation fails unexpectedly, fall back to original loaded system prompt and log a warning, but keep deterministic runtime guards active so safety guarantees remain enforced.

## Artifacts and Notes

Representative planner context fragment (illustrative):

    {
      "current_utc": "2026-03-19T13:40:00+00:00",
      "last_submolt_created_at_utc": "2026-03-15T09:12:00+00:00",
      "recent_submolt_titles": [
        "Human Sleep And Focus",
        "Cognitive Recovery Lab"
      ]
    }

Representative planner skip event for cadence:

    {
      "event_type": "planner_skip",
      "source_trigger": "scheduled",
      "status": "skipped",
      "error_summary": "interval-not-elapsed"
    }

Representative action skip rationale for self-authored target:

    {
      "item_id": "comment-123",
      "stage": "action-outcome",
      "upvote_error": "self-authored-item",
      "dry_run": true
    }

## Interfaces and Dependencies

`automolt/services/automation_service.py` remains the orchestration owner for planner execution, cadence/duplicate/crypto guardrails, search invocation timing, and self-comment prevention.

`automolt/persistence/automation_log_store.py` must expose stable helper interfaces for recent successful submolt history retrieval (limit-aware) and optional title metadata persistence.

`automolt/persistence/automation_store.py` and `automolt/models/automation.py` must evolve queue-item schema/contracts to carry source author metadata in a backward-compatible way.

`automolt/services/search_service.py` must provide metadata retrieval capabilities sufficient to support deterministic self-authored checks before comment writes.

`automolt/persistence/system_prompt_store.py` default text should be updated for new planner guardrails, but runtime-composed augmentation in `AutomationService` is still required to guarantee behavior for existing customized prompt files.

No new third-party dependencies are required; use existing `unittest` and project toolchain.

## Revision Notes

- 2026-03-19 / Cascade: Created initial active ExecPlan to remediate submolt cadence violations, duplicate creation risk, crypto-policy defaults, search freshness gaps, and self-comment safety, based on current runtime code-path analysis and user-reported behavior.
- 2026-03-19 / Cascade: Updated plan progress and discoveries during implementation to record completed milestone work, test/lint evidence, and one pre-existing unrelated repository lint finding.
- 2026-03-19 / Cascade: Updated outcomes/retrospective after code + documentation completion and prepared archival move to `docs/exec-plans/completed/` per PLANS workflow.
