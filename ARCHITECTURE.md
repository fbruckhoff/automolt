# Architecture

## Bird's-eye view

`automolt` is a local-first CLI for operating Moltbook agents. It combines interactive command workflows with a deterministic automation runtime that can run in foreground or via macOS `launchd`.

The architecture optimizes for three things:

- clear boundaries between presentation, orchestration, and I/O,
- reproducible local state in the current workspace,
- safe automation behavior with explicit validation before side effects.

## Top-Level Domain Map

This is the high-level documentation/layering map for the current design-doc structure.

### Core Architecture

- `docs/design-docs/cli-architecture.md`: CLI command structure, command handlers, and flow of control.
- `docs/design-docs/models-and-persistence.md`: Data models, persistence layer, file operations, and validation boundaries.
- `docs/design-docs/client-configuration.md`: Client configuration structure, session management, and agent resolution.
- `docs/design-docs/session-targeting-design.md`: Design rationale and invariants for handle targeting semantics.
- `docs/design-docs/core-beliefs.md`: Long-lived architectural principles and agent-first operating constraints.

### Development Workflow

- `docs/design-docs/contributing-and-releases.md`: Where contributor/release policy lives and how enforcement stays aligned with repository configuration.

### Subsystems

- `docs/design-docs/automation-system.md`: Full automation reference covering runtime, queue, LLM pipeline, setup workflow, and queue inspection.
- `docs/design-docs/automation-runtime-design.md`: Design-level orchestration model for heartbeat execution and scheduler ownership.

## Codemap

Use symbol search for names below (avoid hardcoded links that can drift).

### Entrypoint and command routing

- `main` in `automolt.main` starts the CLI.
- `cli` in `automolt.cli` constructs shared context (`Console`, `MoltbookClient`, services) and registers command groups.
- Command handlers live under `automolt.commands`:
  - top-level commands: `init`, `signup`, `agents`, `search`, `comment`, `upvote`,
  - grouped commands: `automation.*`, `profile.*`, `submolt.*`.

These modules own CLI I/O, option parsing, UX rendering, and command-level error presentation.

### Services (business orchestration)

`automolt.services` is the orchestration layer:

- `AgentService`, `SearchService`, `PostService`, `SubmoltService` wrap domain operations.
- `AutomationService` owns queue lifecycle, prompt composition, analysis/action execution, and heartbeat semantics.
- `SchedulerService` owns tick evaluation, runtime lifecycle, and foreground/background scheduling behavior.
- `LLMProviderService`, `LLMExecutionService`, `OpenAILLMClient` form the LLM provider/runtime path.

Services coordinate work and enforce domain rules; they should not contain command rendering logic.

### Models and typed contracts

`automolt.models` defines Pydantic contracts used at boundaries:

- workspace state (`ClientConfig`, `AgentConfig`, scheduler/runtime models),
- automation schemas (`AnalysisDecision`, `ActionPlan`, provider config),
- API payload models (posts, search results, submolt entities).

### Persistence and local runtime state

`automolt.persistence` isolates file/database/runtime-state I/O:

- config stores: `client_store`, `agent_store`, `session_store`,
- prompt stores: `prompt_store`, `system_prompt_store`,
- automation stores: `automation_store` (SQLite queue), `automation_log_store`,
- scheduler store: `scheduler_store` (runtime lock/state + launchd plist helpers).

Runtime workspace conventions:

- `client.json`, `FILTER_SYS.md`, `ACTION_SYS.md` in workspace root,
- `.agents/<handle>/agent.json`, prompts, logs, scheduler state,
- `.sessions/<PPID>.json` for per-terminal active-agent targeting.

### External boundaries

- `MoltbookClient` in `automolt.api.client` is the boundary for Moltbook REST calls.
- `OpenAILLMClient` is the boundary for OpenAI Responses API calls.

## Architectural invariants

- Command handlers do not perform raw API/file/DB work directly; they delegate.
- Services do not call Click command handlers.
- Persistence modules do not import Click or Rich.
- Agent targeting order is stable: explicit `--handle` -> session `active_agent` -> `client.json:last_active_agent`.
- Explicit `--handle` never mutates session/remembered active agent.
- Automation write-side effects are gated by setup/runtime validation.
- Upvote/downvote policy remains explicit: no automated downvotes.

## Cross-cutting concerns

- **Reliability:** atomic writes for key config files, runtime lock files for scheduler exclusivity, due-time checks independent of launchd poll interval.
- **Security:** sensitive config permissions hardened (`0600` best effort), API key redaction in operator-facing output, no secret values in normal UX messages.
- **Observability:** structured runtime/log artifacts under per-agent directories, explicit automation status/monitor/tick surfaces.
- **Agent-first operation:** stable docs and plan artifacts (`AGENTS.md`, `.agents/PLANS.md`, `docs/`) are intended as the progressive-disclosure context for coding agents.
