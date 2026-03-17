---
includes: Design-level architecture of automation heartbeat execution, scheduling ownership, and queue/LLM orchestration
excludes: Full command option reference and API endpoint catalog
related: ../../ARCHITECTURE.md, core-beliefs.md, session-targeting-design.md
---

# Automation Runtime Design

## Intent

The automation subsystem runs periodic heartbeat cycles for one target agent and keeps scheduling concerns separate from business logic.

## Design decomposition

- `SchedulerService` decides *when* to execute.
- `AutomationService` decides *what* to execute.
- `automation_store` persists queue state, planner policy fingerprints, and status derivation.
- `automation_log_store` persists stage traces plus planner/runtime event history.
- `scheduler_store` persists runtime locks/state and background scheduler integration.
- `LLMExecutionService` + `OpenAILLMClient` execute stage-specific model calls with structured outputs.

## Heartbeat model

A heartbeat cycle is modeled as:

1. preflight validation (automation enabled, keys/config/prompt prerequisites),
2. planner-first policy refresh and deterministic guard evaluation (`BEHAVIOR_SUBMOLT.md` fingerprint + parsed policy),
3. optional planner execution and side effects (`create_submolt`, optional `create_post`) with event persistence,
4. queue maintenance (initialize, prune, refill when needed) only when planner did not act,
5. analysis/action scan over candidates, including optional reactive planner escalation from action output,
6. persistence of cycle completion timestamp and observable outcomes.

This keeps command surfaces (`tick`, `start`, `monitor`, `status`) thin while centralizing execution semantics in service code.

## Scheduling model

Foreground and background runtime share due-time semantics:

- due checks are computed from persisted automation configuration and `last_heartbeat_at`,
- background launch cadence is a trigger mechanism, not the source of truth,
- runtime lock files prevent duplicate local scheduler execution per handle.

## Policy boundaries

- Setup completeness is enforced before runtime side effects.
- Read-only queue inspection (`automation list`) remains decoupled from provider auth prerequisites.
- Action policy constraints (for example, no automated downvotes) are explicit service-level behavior.
- Planner cadence/rate controls (interval, max/day, duplicate-name protection) are deterministic runtime guards, not model-only policy.
- Planner parse/prompt failures are observable events and do not block heartbeat timestamp persistence.

## Verification status

- **Verified:** 2026-03-17
- **Verified against:** `services/automation_service.py`, `services/scheduler_service.py`, `services/llm_execution_service.py`, `persistence/automation_store.py`, `persistence/automation_log_store.py`, `persistence/scheduler_store.py`, and `commands/automation/reload_command.py`.
