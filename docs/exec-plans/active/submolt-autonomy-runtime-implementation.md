# Implement autonomous submolt planner runtime

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This document must be maintained in accordance with `.agents/PLANS.md`.

## Purpose / Big Picture

After this change, an automation-enabled agent can create and post to submolts autonomously on a controlled cadence without inflating the token cost of the existing high-frequency reply loop. The user-visible result is that every scheduled automation tick now evaluates a dedicated submolt planning path before any queue-item processing, creates a submolt and post when cadence permits, and records auditable event history in the same automation log store used by other automation runtime events. If a submolt is created in that cycle, queue-item commenting is skipped for that cycle so automation performs only one action step. Cadence edits in `BEHAVIOR_SUBMOLT.md` (for example, changing every 24h to every 2h) also take effect immediately on the next tick via file-change detection plus explicit reload support.

A human can see this working by running a forced automation tick for an eligible agent and then confirming three observable outcomes: a new submolt/post is created when cadence permits, the submolt automation event log is updated, and normal reply behavior remains unchanged for queue items.

Documentation depth decision: `full`, because this introduces a new runtime stage, new persistence contract, and new cross-cutting automation behavior.

## Progress

- [x] (2026-03-17 10:43Z) Reviewed current automation architecture, queue contracts, and scheduler/runtime boundaries.
- [x] (2026-03-17 10:44Z) Finalized architectural decision to keep `ActionPlan` compact and add a separate conditional `submolt_planner` stage.
- [x] (2026-03-17 10:45Z) Authored this active ExecPlan with phased implementation milestones and validation strategy.
- [x] (2026-03-17 14:43Z) Updated generated report + active ExecPlan to resolve cadence-edit UX gap with per-tick file-change detection and manual reload strategy.
- [x] (2026-03-17 15:16Z) Revised runtime ordering and failure-boundary semantics per engineering review: planner-first execution, one-step-per-cycle enforcement, heartbeat timestamp persistence isolation, sequential prompt loading, shared `automation_log_store` event persistence, and per-cycle guard re-evaluation.
- [x] (2026-03-17 16:09Z) Implemented Phase 1 runtime foundations: planner-first scheduled execution, deterministic guards, event persistence, behavior-file fingerprint refresh/reparse, and `automation reload`.
- [x] (2026-03-17 16:11Z) Implemented Phase 2 reactive escalation with compact action-schema extensions (`promote_to_submolt`, `promotion_topic`) and reactive planner invocation path.
- [x] (2026-03-17 16:15Z) Implemented Phase 3 policy/observability + docs/test hardening: planner policy controls (`max/day`, topic/name fields), monitor event surfacing, persistence/runtime tests, and design-doc updates.

## Surprises & Discoveries

- Observation: The current heartbeat path is intentionally optimized around queue items and stops after the first acted reply, so a naive in-loop submolt branch would couple unrelated concerns and increase failure surface in the hot path.
  Evidence: `automolt/services/automation_service.py` executes oldest-first queue scanning with `ItemProcessingOutcome` short-circuit semantics.

- Observation: Existing submolt and post creation already include verification challenge handling via shared service code, which can be reused directly by a planner execution path.
  Evidence: `automolt/services/submolt_service.py` and `automolt/services/post_service.py` call `ContentVerificationService.verify_if_required(...)`.

- Observation: Time-based planner guards alone are insufficient for good UX when cadence values are edited at runtime, because stale in-memory policy can delay effect until the previous interval expires.
  Evidence: Operator scenario: `submolt_create_interval_hours` changed 24 -> 2 should affect the next tick, but would be delayed without behavior-file refresh semantics.

- Observation: Planner placement cannot rely on the existing queue-item short-circuit path because `ItemProcessingOutcome.ACTED` intentionally exits queue scanning early; therefore planner must execute in a planner-first phase so it is never starved by queue outcomes.
  Evidence: `automolt/services/automation_service.py` queue loop behavior currently breaks after first acted item.

- Observation: Keeping planner failures non-fatal to the heartbeat requires planner-stage provider/model errors to be logged as planner failure events instead of bubbling up as cycle-fatal exceptions.
  Evidence: Planner-stage `LLMClientError` handling now records `submolt-planner` stage traces and returns planner-failure outcomes while `last_heartbeat_at` still persists at cycle completion.

- Observation: Persisting planner event history in JSONL under `.agents/<handle>/logs/automation-events.jsonl` gives simpler additive rollout than introducing a second SQLite schema while still enabling deterministic guard lookups (last successful create + max/day counts).
  Evidence: Added typed event helpers in `automolt/persistence/automation_log_store.py` and runtime guard checks now consume those helpers.

## Decision Log

- Decision: Implement autonomous submolt behavior through a separate `submolt_planner` stage instead of overloading `ActionPlan` with create/post payload fields.
  Rationale: The action stage is the highest-frequency path and must remain token-efficient and stable for normal replies.
  Date/Author: 2026-03-17 / Cascade

- Decision: Enforce cadence/rate guards deterministically in runtime code before planner invocation.
  Rationale: Hard runtime guards prevent accidental over-creation even if model output is noisy.
  Date/Author: 2026-03-17 / Cascade

- Decision: Roll out in three phases, with scheduled proactive execution as the first deliverable.
  Rationale: Phase-based sequencing minimizes regression risk while keeping architecture extensible for reactive linking behavior.
  Date/Author: 2026-03-17 / Cascade

- Decision: Use per-tick `os.stat` fingerprint checks (`st_mtime_ns` + `st_size`) for `BEHAVIOR_SUBMOLT.md` and re-parse policy immediately on change; also add explicit `automolt automation reload`.
  Rationale: This is the most pragmatic balance of responsiveness and implementation risk: low overhead, no file-watcher daemon complexity, and deterministic operator override.
  Date/Author: 2026-03-17 / Cascade

- Decision: Execute planner evaluation and (when due) planner side effects before queue processing on every heartbeat cycle; if planner creates a submolt/post, skip queue comment/upvote execution for that cycle.
  Rationale: Planner-first ordering guarantees autonomy is not suppressed by queue short-circuit behavior, and one-step-per-cycle enforcement keeps automation behavior controlled and auditable.
  Date/Author: 2026-03-17 / Cascade

- Decision: Keep planner event persistence in existing `automolt/persistence/automation_log_store.py` and evaluate cadence guards from successful planner-create events only; queue-processing failures never mutate planner cadence markers.
  Rationale: Reusing one log store keeps persistence simple, and deriving cadence from successful planner outcomes ensures planner due-state is always reconsidered correctly on the next cycle when queue processing fails.
  Date/Author: 2026-03-17 / Cascade

- Decision: Make heartbeat prompt/policy loading and parsing sequential inside heartbeat execution, and persist heartbeat-cycle timestamps regardless of planner success/failure.
  Rationale: Sequential loading avoids initialization races, and isolating heartbeat timestamp persistence preserves scheduler stability even when planner execution errors.
  Date/Author: 2026-03-17 / Cascade

- Decision: Treat planner prompt/policy availability as planner-stage gating (skip/failure events) rather than global runtime prerequisites.
  Rationale: Missing `SUBMOLT_PLANNER_SYS.md` or `BEHAVIOR_SUBMOLT.md` should not regress baseline reply automation behavior.
  Date/Author: 2026-03-17 / Cascade

- Decision: Surface planner observability directly in foreground monitor event rendering (`PLANNER_EVALUATED`, `PLANNER_SKIPPED`, `PLANNER_FAILED`, `PLANNER_ACTED`).
  Rationale: Operators need immediate stage-level visibility without adding new command surfaces during initial rollout.
  Date/Author: 2026-03-17 / Cascade

## Outcomes & Retrospective

Completed end-state:

- Heartbeat cycles now run planner-first evaluation with deterministic guards and one-step-per-cycle behavior (planner action skips queue processing for that cycle).
- `BEHAVIOR_SUBMOLT.md` policy is parsed with persisted file fingerprint metadata and supports explicit operator refresh via `automolt automation reload --handle <handle>`.
- Planner outcomes are persisted in shared `automation_log_store` event history (`automation-events.jsonl`) and surfaced in monitor output.
- Action-stage schema remains compact but now supports reactive planner escalation through optional `promote_to_submolt` and `promotion_topic` fields.
- Documentation was updated at `full` depth (`automation-system.md`, `automation-runtime-design.md`, `_index.md`), and validation passed (`ruff` + `unittest`).

## Context and Orientation

Automation runtime is split across scheduler orchestration and heartbeat execution.

`automolt/services/scheduler_service.py` decides when a cycle is due and calls `AutomationService.execute_heartbeat_cycle(...)`. `automolt/services/automation_service.py` decides what to do during a cycle. In this plan's final runtime order, each heartbeat executes these phases sequentially: behavior-file fingerprint check and parse refresh, planner guard evaluation and optional planner execution, then (only when planner did not perform a create/post action) queue refill + analysis/action reply path, followed by heartbeat timestamp persistence.

A queue item is a local SQLite record stored in `.agents/<handle>/automation.db` table `items`, represented by `automolt/models/automation.py:QueueItem`. The current structured LLM contracts are in `automolt/models/llm.py`: `AnalysisDecision`, `ActionPlan(reply_text, upvote, promote_to_submolt, promotion_topic)`, and `SubmoltPlannerPlan(...)`.

A "planner stage" in this plan means a separate LLM call and execution pathway that is not run for every queue item. It is invoked only when deterministic runtime conditions say autonomy work is due, or when a future reactive escalation flag is set. This stage is always evaluated before queue-item processing; if it performs a submolt/post create action, queue commenting is skipped for the rest of that heartbeat.

Submolt cadence policy comes from per-agent `BEHAVIOR_SUBMOLT.md`. This plan now defines explicit refresh semantics: every heartbeat tick checks whether this file changed since last successful parse, and if so, reparses policy before due-state evaluation. A "fingerprint" here means file metadata tuple (`st_mtime_ns`, `st_size`) captured from `os.stat`, persisted per handle, and compared on each tick.

Submolt and post side effects already exist in service-layer APIs:

- `automolt/services/submolt_service.py:create_submolt(...)`
- `automolt/services/post_service.py:create_post(...)`

Both already handle Moltbook verification challenges through `ContentVerificationService`, so the planner can reuse those paths instead of duplicating verification logic.

Automation event logging already exists in `automolt/persistence/automation_log_store.py`. Planner success/skip/failure events in this plan will be persisted through that same store (not a separate planner-specific log store), so guard evaluation and operator observability use one consistent event history.

## Plan of Work

Milestone 1 introduces the minimum safe autonomous pathway: scheduled proactive submolt creation/posting. Add dedicated planner models, planner prompt loading, deterministic cadence guards, behavior-file change detection, and event persistence. Integrate planner execution into heartbeat cycles as a planner-first branch that runs before queue processing on every cycle and is evaluated independently from queue outcomes. If planner performs submolt/post creation in that cycle, skip queue commenting for that cycle to enforce one action step per heartbeat. Keep default behavior unchanged when planner is disabled or not due. Add `automation reload` so operators can force immediate behavior-file re-parse on demand.

Milestone 2 introduces reactive escalation from queue-item action outcomes. Extend `ActionPlan` with compact optional escalation fields only (`promote_to_submolt`, `promotion_topic`) and invoke planner in reactive mode when escalation is requested and hard runtime guards allow execution. Ensure reactive planner context is compact and references source item metadata.

Milestone 3 adds policy hardening and operator observability. Add configuration and prompt-level policy fields needed for max/day and topic controls, add status/monitor visibility for planner executions, and complete documentation updates in automation design docs plus any README/operator command references impacted by new behavior.

Across all milestones, keep architecture boundaries strict: command handlers keep CLI UX only, services orchestrate behavior, persistence modules own I/O contracts, and model contracts remain explicit and validated.

## Concrete Steps

All commands run from repository root:

    /Users/franz/Desktop/Tapsweets/Apps/CLI/automolt/automolt

Implementation sequence:

1. Add planner model contracts and runtime context models.

   Edit `automolt/models/llm.py` (or a new adjacent model module if clearer) to define a strict structured output model for `submolt_planner`. Include fields for create/post intent, submolt/post payloads, optional follow-up reply-link intent, and concise rationale.

2. Add persistence for submolt automation history and behavior-policy fingerprint state.

   Extend `automolt/persistence/automation_log_store.py` with planner event types and typed read/write helpers. Include created timestamp, trigger source (`scheduled`/`reactive`), status, and error summary. Keep behavior-file fingerprint and parsed-policy snapshot state in existing runtime state persistence (`automolt/persistence/automation_store.py`) so event history and runtime metadata remain clearly separated but planner events share the same automation log store as other runtime events.

3. Implement deterministic planner guard evaluation with behavior-file refresh check.

   In `automolt/services/automation_service.py`, add a pre-guard behavior refresh step: `stat` current `BEHAVIOR_SUBMOLT.md`, compare with persisted fingerprint, and re-parse policy immediately when changed. Then run guard evaluation helpers for minimum interval, max creations/day, and duplicate-name prevention checks. These checks must run before any planner LLM call and must derive cadence state from last successful planner-create events in `automation_log_store` so due-state is always re-evaluated correctly on every new cycle.

4. Add planner LLM execution path.

   In `automolt/services/llm_execution_service.py` and `automolt/services/openai_llm_client.py`, add a stage execution method for planner responses using strict JSON schema validation exactly like existing analysis/action calls.

5. Integrate planned side-effect execution.

   In `automolt/services/automation_service.py`, add a planner-first invocation path inside heartbeat execution that runs before queue scanning. Wire planner outputs to `SubmoltService.create_submolt(...)` and `PostService.create_post(...)`, then persist success/failure/skip events through `automation_log_store`. If planner completes a create/post action, mark the cycle as acted and skip queue item commenting for that cycle; if planner is skipped or fails, continue into normal queue scanning.

6. Add planner-specific prompt contract and safe parse semantics.

   Add support for per-agent `BEHAVIOR_SUBMOLT.md` prompt loading (likely via `automolt/persistence/prompt_store.py` helpers) and include only this prompt in planner calls. Do not include it in normal action-stage payloads. Perform planner prompt loading and behavior parse checks sequentially in heartbeat execution (no concurrent lazy initialization paths). Define parse error handling so malformed edits do not crash heartbeat cycles; persist an explicit failure/skipped event with parse error summary and keep runtime stable.

7. Phase 2 reactive escalation wiring.

   Add compact optional escalation fields to `ActionPlan` and action-stage prompts/system guidance, then trigger reactive planner mode when action output requests escalation and guard checks pass.

8. Add explicit operator reload command.

   Add `automolt automation reload --handle <handle>` under automation commands to force immediate re-parse of `BEHAVIOR_SUBMOLT.md`, refresh persisted fingerprint/policy snapshot, and report parse success/failure clearly.

9. Add tests for deterministic guards, planner parsing, refresh detection, reload command, persistence, and integration behavior.

   Add/extend tests in `tests/` to verify planner stage contracts, planner-first ordering, one-step-per-cycle skip behavior after planner create/post success, guard behavior, per-tick fingerprint change detection, immediate cadence re-evaluation after policy edits, reload command behavior, event persistence in `automation_log_store`, heartbeat timestamp persistence on planner failure, and that normal action-only cycles remain unchanged when planner is not due.

10. Update docs after behavior lands.

   Update `docs/design-docs/automation-system.md`, `docs/design-docs/automation-runtime-design.md`, and `docs/design-docs/_index.md` as needed to reflect new stage/persistence/runtime behavior.

Validation commands during and after implementation:

    uv run python -m unittest discover -s tests
    uv run ruff check .
    uv run python -m automolt.main automation tick --handle <handle> --dry
    uv run python -m automolt.main automation tick --handle <handle>
    uv run python -m automolt.main automation reload --handle <handle>
    uv run python -m automolt.main automation list --status all --handle <handle>

Expected evidence examples:

    - Dry tick output shows planner-eligible decision metadata but no network writes.
    - Live tick on due cadence runs planner before queue scan, creates submolt/post (when planner returns true), records a success event, and skips queue commenting for that cycle.
    - Editing `BEHAVIOR_SUBMOLT.md` to shorten interval (24h -> 2h) causes the very next tick to detect file change, re-parse policy, and run updated due-state checks.
    - A second tick inside minimum interval skips planner and records/prints skip reason.
    - A tick where planner fails still updates heartbeat timestamp and records planner failure event.
    - `automation reload` prints success when parseable, and prints actionable parse failure details when invalid.

## Validation and Acceptance

Acceptance for Milestone 1 is met when all of the following are true:

- Running `automation tick` on an eligible handle can invoke planner logic without requiring queue-item action-schema expansion.
- `automation tick` always evaluates planner eligibility before queue processing, independent of queue-item outcomes.
- `automation tick` detects changed `BEHAVIOR_SUBMOLT.md` metadata and re-parses cadence rules before evaluating planner eligibility.
- Deterministic guards prevent planner invocation when interval/max-day constraints are not satisfied.
- Successful planner create/post flows produce persisted event-history entries with timestamps and trigger source in `automation_log_store`, and queue commenting is skipped for that cycle.
- Planner failures produce persisted failure events in `automation_log_store` and do not prevent heartbeat timestamp persistence.
- `automation reload --handle <handle>` forces behavior-file re-parse and persists updated policy/fingerprint or returns a clear validation error.
- Existing queue reply flow still works with unchanged baseline `ActionPlan(reply_text, upvote)` behavior for normal non-escalation item handling.

Acceptance for Milestone 2 is met when a relevant queue-item action can request reactive escalation through compact fields and trigger planner execution with source-item context, while still honoring hard runtime guards.

Acceptance for Milestone 3 is met when planner outcomes and gating reasons are visible through runtime/operator surfaces and documentation reflects final behavior.

## Idempotence and Recovery

All migration and persistence changes must be additive and safe on repeated runs. Table creation and column additions must use idempotent migration checks (`CREATE TABLE IF NOT EXISTS`, explicit schema inspection before `ALTER TABLE`).

If planner execution fails mid-cycle, persist a failure event with a concise error summary in `automation_log_store` and continue to preserve heartbeat stability, including heartbeat timestamp persistence. Do not leave partially written event entries without status.

If `BEHAVIOR_SUBMOLT.md` parsing fails after a file change or reload request, do not crash the heartbeat. Record a planner policy failure/skip event with parse details and preserve the last known good runtime policy snapshot until a valid parse succeeds.

For network-side content creation errors or verification failures, rely on existing service exceptions and log structured failure events rather than retry loops in the same cycle. Recovery is a future eligible tick after deterministic guards are re-evaluated from persisted successful planner-create timestamps; queue-path failures in a prior cycle do not suppress this re-evaluation.

## Artifacts and Notes

Operator-facing artifacts that should exist after implementation include per-item and per-planner traces under `.agents/<handle>/logs/`, plus planner event-history records written to the existing automation log store.

Representative planner event payload shape (for persistence/logging):

    {
      "event_type": "create_submolt",
      "source_trigger": "scheduled",
      "submolt_name": "example-lab",
      "status": "success",
      "created_at_utc": "2026-03-17T10:55:00+00:00"
    }

Representative planner skip payload shape:

    {
      "event_type": "planner_skip",
      "source_trigger": "scheduled",
      "status": "skipped",
      "error_summary": "interval-not-elapsed"
    }

## Interfaces and Dependencies

`automolt/models/llm.py` (or a sibling model module) must define a planner output model with strict fields and validation suitable for OpenAI structured responses. The model must be serializable and validated through the same execution path style as existing stage contracts.

`automolt/services/llm_execution_service.py` must expose a planner-stage execution method that returns parsed output and raw trace payload, matching existing `StageExecutionResult` semantics.

`automolt/services/openai_llm_client.py` must add planner completion support via Responses API with strict JSON schema mode and robust error handling consistent with analysis/action pathways.

`automolt/services/automation_service.py` must own planner orchestration, including sequential prompt/policy loading, planner-first guard checks, source-trigger context assembly, side-effect delegation to existing services, one-step-per-cycle enforcement (skip queue commenting after planner create/post success), and event persistence.

`automolt/persistence/automation_log_store.py` must expose idempotent event-history read/write APIs used by automation service to derive `last_submolt_created_at_utc`, `hours_since_last_submolt_creation`, and related planner context fields. `automolt/persistence/automation_store.py` continues to own non-log runtime state such as heartbeat timestamps and behavior-file fingerprint/policy snapshot metadata.

`automolt/persistence/prompt_store.py` must support reading/writing `BEHAVIOR_SUBMOLT.md` with the same minimum-content expectations applied to required runtime prompts, plus helper access patterns needed for fingerprint-based refresh checks.

Automation command modules under `automolt/commands/automation/` must expose `automation reload` with `--handle` support, using the same session/explicit-targeting contract as other agent-targeted commands.

Test dependencies remain the current project toolchain (`unittest`, existing fixtures/helpers, `ruff`). No new third-party runtime dependencies are required.

## Revision Notes

- 2026-03-17 / Cascade: Created initial active ExecPlan from approved `docs/generated/automation-submolt-autonomy-report.md` decision section to guide implementation of autonomous submolt planning in phased, low-risk milestones.
- 2026-03-17 / Cascade: Revised plan to resolve cadence-edit UX issue by requiring per-tick `BEHAVIOR_SUBMOLT.md` fingerprint detection (`st_mtime_ns` + `st_size`), immediate re-parse/recompute semantics, and an explicit `automation reload` operator command. Reason: cadence changes must apply immediately instead of waiting for previously parsed intervals.
- 2026-03-17 / Cascade: Revised plan after engineering feedback to make planner execution unambiguously planner-first, enforce one-step-per-cycle behavior (skip queue comments after planner create/post), keep planner events in existing `automation_log_store`, require sequential prompt/policy loading, isolate heartbeat timestamp persistence from planner failures, and require per-cycle cadence re-evaluation from persisted successful planner outcomes. Reason: eliminate short-circuit starvation and clarify recovery/observability semantics before implementation.
- 2026-03-17 / Cascade: Completed all three implementation phases, updated tests and design docs, and marked plan ready for archival to `docs/exec-plans/completed/`. Reason: acceptance criteria for planner runtime, reactive escalation, observability, and docs verification are met in the current codebase.
