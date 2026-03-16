---
includes: Agent-first operating principles and architecture beliefs derived from implemented system behavior
excludes: Command-level option reference and user onboarding instructions
related: ../../ARCHITECTURE.md, automation-runtime-design.md, session-targeting-design.md
---

# Core Beliefs

These beliefs describe how `automolt` is expected to evolve without architectural drift. They are derived from implemented code (`automolt/`), the prior living docs (`docs_old/`), and archived directives (`tasks/archive/`).

## 1) Layer boundaries are a product feature

- CLI command handlers own interaction, prompts, argument parsing, and output rendering.
- Services own orchestration and business decisions.
- Persistence owns local file/DB/runtime-state I/O.
- API client modules own external protocol details.

This separation is intentional because `automolt` is both an operator-facing CLI and an automation runtime; behavior should remain reusable and testable outside command rendering.

## 2) Local-first state is authoritative

Workspace-local state is first-class, not incidental:

- `client.json` and system prompts (`FILTER_SYS.md`, `ACTION_SYS.md`) at client root,
- agent runtime state under `.agents/<handle>/...`,
- session targeting under `.sessions/<PPID>.json`.

The project optimizes for deterministic local operation and recoverability through explicit state files.

## 3) Agent targeting must be deterministic

All agent-aware commands follow one resolution order:

1. explicit `--handle`,
2. session `active_agent`,
3. remembered `client.json:last_active_agent` (with lazy session init).

Mutations are constrained:

- explicit `--handle` never mutates session or remembered state,
- only explicit selection flows (`automolt agents`) update both session and remembered state.

## 4) Automation is policy-driven and validated before side effects

Automation execution is designed around explicit gates:

- setup/runtime prerequisites are validated before heartbeat writes,
- queue status is derived from typed, persisted fields,
- stage behavior is driven by prompt contracts and strict structured LLM outputs.

This keeps automation behavior predictable even when providers or prompts change.

## 5) Security defaults are enforced in normal paths

- Sensitive local config files are permission-hardened (`0600` best effort).
- API keys are treated as secrets in UX output.
- External traffic goes through explicit API boundaries (`MoltbookClient`, `OpenAILLMClient`).

Security behavior should remain built-in at boundaries, not optional per command.

## 6) Observability is part of runtime correctness

The scheduler and automation runtime are expected to be inspectable:

- runtime state and lock artifacts exist per handle,
- action/analysis traces are persisted locally,
- status and monitor commands expose current runtime condition.

Operator confidence and debugging speed depend on this observability surface.

## 7) Progressive disclosure beats context overload

Agent-facing docs should guide discovery in layers:

- stable entry points (`AGENTS.md`, `ARCHITECTURE.md`, `docs/design-docs/_index.md`),
- then subsystem-specific design docs,
- then implementation detail in code and execution-plan artifacts.

This allows fast onboarding for coding agents while preserving depth when needed.

## 8) Plans are versioned operational context

Complex work should not rely on ephemeral chat context. Plans, progress, and technical debt are repository artifacts (`docs/exec-plans/`) so future agents can continue work with minimal hidden state.
