# Automation Documentation Capture Track

This checklist was used to verify consolidation from implementation directives into `docs/AUTOMATION.md`.

Deletion workflow status (performed one-by-one after verification):

- [x] `AUTOMATION-FEEDBACK-IMPL.md` verified + deleted
- [x] `AUTOMATION-IMPL.md` verified + deleted
- [x] `AUTOMATION-IMPL-V2.md` verified + deleted
- [x] `AUTOMATION-LLM-API-CALL-IMPL.md` verified + deleted
- [x] `AUTOMATION-SCHEDULER-IMPL.md` verified + deleted
- [x] `AUTOMATION-TEST-IMPL.md` verified + deleted
- [x] `AUTOMATION-SETUP-IMPL.md` verified + deleted

Legend:

- [x] captured in `docs/AUTOMATION.md`
- [~] intentionally not carried forward (superseded/outdated directive-only content)

---

## 1) `AUTOMATION-FEEDBACK-IMPL.md`

- [x] Purpose: improve runtime observability and trust.
- [x] Problem statement: scheduler-level visibility alone is insufficient.
- [x] Problem statement: provider auth/runtime failures must be explicit and actionable.
- [x] Operator-facing needs: search/analyze/act/why-not visibility.
- [x] Architecture positioning: CLI/scheduler/automation/persistence ownership.
- [x] Gap: no full persisted heartbeat event stream yet (recorded as future improvement).
- [x] Gap: reason taxonomy harmonization beyond auth failures (recorded as future improvement).
- [x] Requirement: monitor/runtime output should expose search, analysis, action outcomes.
- [x] Requirement: credential failures should not appear as successful cycles.
- [x] Requirement: concise, high-signal user messaging.
- [x] Optional recommendation: event ring buffer for monitor continuity (recorded as future improvement).
- [x] Security requirements: redact secrets; no API key/header leakage.
- [x] Acceptance intent: monitor should indicate real work, not just tick cadence.
- [~] Markdown inventory section (source-discovery process artifact, not living system behavior).
- [~] Proposed new model module `automation_feedback.py` (not implemented; replaced by current event dataclass approach).
- [~] Directive phase plan/checklist language (implementation process artifact).

---

## 2) `AUTOMATION-IMPL.md`

- [x] Automation system purpose and heartbeat queue architecture.
- [x] `AgentConfig.automation` high-level shape and semantics.
- [x] Stage routing split (`analysis`, `action`) and provider/model per stage.
- [x] Global provider config stored in `client.json` (captured with current naming: `llm_provider_config`).
- [x] Queue persistence location: `.agents/<handle>/automation.db`.
- [x] Queue schema includes identity/analysis/action terminal fields.
- [x] Dedupe via `INSERT OR IGNORE` on `item_id`.
- [x] Oldest-first retrieval for unanalyzed rows.
- [x] Prompt file locations (`FILTER.md`, `BEHAVIOR.md`).
- [x] Prompt files persisted per agent and validated for runtime readiness.
- [x] `setup_automation` responsibilities and invariant enforcement.
- [x] `execute_heartbeat_cycle` high-level flow and persistence semantics.
- [x] Separation-of-concerns guidance (CLI vs service vs persistence).
- [x] Setup success output includes routing/config and prompt status.
- [~] Legacy term `llm_provider_credentials` (superseded by `llm_provider_config`).
- [~] "scheduler out of scope" wording (superseded by implemented scheduler docs).
- [~] Historical migration notes for pre-existing local files (directive-era context only).

---

## 3) `AUTOMATION-IMPL-V2.md`

- [x] V2 refill-first behavior when backlog has no unanalyzed items.
- [x] Same-cycle continuation after refill.
- [x] Oldest-first scan loop.
- [x] Item outcome semantics: irrelevant / relevant_not_acted / acted.
- [x] Stop condition: first acted success or backlog exhaustion.
- [x] No pending-action priority execution phase.
- [x] Cycle timestamp persisted once per completed cycle.
- [x] Identity/content rules for posts/comments with `post_id` context.
- [x] Store helper `has_unanalyzed(...)` behavior.
- [x] Scheduler integration boundary preserved (`run_tick` invokes heartbeat execution).
- [~] Directive sequencing/checklist language (implementation process artifact).

---

## 4) `AUTOMATION-LLM-API-CALL-IMPL.md`

- [x] Stage-aware LLM execution architecture.
- [x] Provider-agnostic extension path via provider service and execution router.
- [x] Current provider support: OpenAI only.
- [x] Runtime stage contracts (`AnalysisDecision`, `ActionPlan`).
- [x] Parse validation and one repair retry for invalid JSON.
- [x] Content sourcing rules for post/comment queue items.
- [x] Action flow semantics and reply posting conditions.
- [x] Queue terminal-state semantics (pending-analysis/pending-action/acted).
- [x] Per-item fault isolation and bounded retry behavior.
- [x] Security requirements (no secret logging; validation before calls).
- [x] Model catalog usage via `LLMProviderService`.
- [x] OpenAI response-length configuration via provider config (`max_output_tokens`).
- [x] Note that proactive preflight is not separately implemented (captured in known gaps).
- [~] Legacy endpoint claim `v1/chat/completions` (superseded by current `v1/responses`).
- [~] Legacy term `llm_provider_credentials` (superseded by `llm_provider_config`).
- [~] Directive-only hardening/test backlog language retained only as future-improvement context.

---

## 5) `AUTOMATION-SCHEDULER-IMPL.md`

- [x] Dual runtime modes: foreground and background (launchd).
- [x] One-handle-at-a-time scheduler command behavior.
- [x] Command set: `start`, `stop`, `status`, `monitor`, `tick`.
- [x] Setup validation before runtime operations.
- [x] Immediate startup verification tick behavior.
- [x] Due-time rules and interval floor (`max(interval_seconds, 60)`).
- [x] Manual tick semantics and schedule-respecting internal mode.
- [x] Runtime lifecycle state + lock behavior.
- [x] LaunchAgent installation/load/unload/remove lifecycle.
- [x] Runtime status reporting fields.
- [x] Logging locations for launchd stdout/stderr.
- [x] Separation of concerns across command/service/persistence.
- [x] Reliability goals: no full runtime crash on per-cycle failures.
- [~] Legacy wording "global provider credentials" (superseded by provider config terminology).
- [~] Directive test matrix language (transformed into operational checks + known gap notes).

---

## 6) `AUTOMATION-TEST-IMPL.md`

- [x] Product dry mode: `start --dry` keeps search/analysis/action generation but no network write.
- [x] Dry mode persisted acted marker: `replied_item_id = "--dry"`.
- [x] Dry mode foreground-only (`--background --dry` rejected).
- [x] Analysis contract includes `relevance_rationale` with legacy alias support for `reason`.
- [x] Queue persistence includes `relevance_rationale` column and mapping.
- [x] Monitoring visibility requirements for search/analysis/action stages.
- [x] Search completion counts split by post/comment insertions.
- [x] Analysis pass/fail and rationale output.
- [x] Dry action output includes full would-be text and target URL.
- [x] Live action output includes posted text and target URL.
- [x] Per-item LLM stage log persistence under `.agents/<handle>/logs`.
- [x] Log filename format and exact separator requirements.
- [x] Distinction between scheduler dry-run and heartbeat dry-action mode.
- [~] Directive acceptance-check checklist formatting (process artifact, not runtime documentation).

---

## 7) `AUTOMATION-SETUP-IMPL.md`

- [x] Setup supports both interactive and atomic modes.
- [x] Setup configures per-agent search/cutoff and stage routing in `agent.json`.
- [x] Setup configures global provider config in `client.json`.
- [x] Setup manages prompt files (`FILTER.md`, `BEHAVIOR.md`).
- [x] Session-aware target-handle resolution remains in effect.
- [x] Terminology uses `LLMProviderConfig` / `OpenAIProviderConfig`.
- [x] OpenAI provider config includes `api_key` and `max_output_tokens`.
- [x] Default `max_output_tokens` is documented as `1500`.
- [x] Client JSON shape documents `llm_provider_config.openapi` serialization.
- [x] Backward-compatible alias reading behavior is documented.
- [x] Setup command interface includes `--provider`, `--api-key`, `--max-output-tokens`, `--filter-md`, `--behavior-md`.
- [x] Mode selection: any setup flag -> atomic; none -> interactive.
- [x] Interactive mode sequence is documented.
- [x] Interactive mode defaults behavior is documented (existing values as defaults; empty keeps defaults).
- [x] Interactive mode documents hard-cutoff guidance for max response length.
- [x] Interactive mode documents prompt source methods (editor or source file path).
- [x] Prompt minimum content length enforcement is documented.
- [x] Atomic mode documents apply-only-provided and preserve-unspecified behavior.
- [x] Atomic mode documents prompt edit behavior for no-value vs file-path flags.
- [x] Atomic mode documents explicit keypress confirmation after editor launch.
- [x] Atomic mode documents per-flag status lines and saved character counts.
- [x] Fresh atomic setup edge-case behavior (persist partial + missing requirements guidance) is documented.
- [x] Runtime validation contract is documented for `automation status`, `automation start`, and heartbeat cycle start.
- [x] Runtime validation checks for provider config + prompt file presence/min length are documented.
- [x] Fail-fast behavior with actionable setup guidance is documented.
- [x] Security/UX items: hidden API key prompt, redacted key status, no full key display.
- [x] Permission hardening for `client.json` and `agent.json` documented.
- [x] Validation checklist outcomes are reflected in living docs.
