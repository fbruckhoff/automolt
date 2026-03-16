---
includes: Design contract for handle resolution, session scoping, and active-agent state mutation rules
excludes: Full per-command UX copy and unrelated scheduler internals
related: ../../ARCHITECTURE.md, core-beliefs.md
---

# Session Targeting Design

## Intent

Agent-targeted commands should behave consistently across interactive and automation workflows without forcing users to pass `--handle` every time.

## Resolution contract

`resolve_target_handle` establishes one order:

1. explicit `--handle` (highest priority),
2. session `active_agent` from `.sessions/<PPID>.json`,
3. lazy initialization from `client.json:last_active_agent`.

This order is stable across command surfaces.

## Mutation contract

Mutations are deliberately constrained:

- explicit `--handle` does not write session state,
- only selection flows that call `set_selected_agent` update session and remembered active agent,
- stale `.sessions` files are swept based on process liveness.

## Why this matters

This model gives users short commands by default while preserving deterministic explicit targeting in scripts and automation.

It also keeps state ownership clear:

- session store owns per-terminal state,
- client store owns remembered defaults,
- command handlers/services only consume these contracts.

## Verification status

- **Verified:** 2026-03-10
- **Verified against:** `commands/agent_targeting.py`, `persistence/session_store.py`, `persistence/client_store.py`, `commands/agents_command.py`, and `docs_old/CLIENT_CONFIG.md`.
