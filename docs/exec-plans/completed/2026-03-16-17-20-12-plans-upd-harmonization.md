# PLANS.md Crosswalk and Workflow Adaptation Status

## Scope

This file records the completed harmonization work across:

- `AGENTS.md`
- `.agents/PLANS.md`
- `.agents/rules/documentation.md`
- `.agents/skills/documentation/SKILL.md`
- `.agents/workflows/implement-and-document.md`

## Executive Summary

Harmonization is now implemented:

- ExecPlan lifecycle is consistently centered on `docs/exec-plans/active/` -> `docs/exec-plans/completed/`.
- Legacy `/tasks`, `/tasks/archive`, `/reports`, and `*-IMPL.md` references were removed from the three legacy files.
- Documentation workflow is now conditional (`skip`/`minimal`/`full`) to reduce over-triggering.
- `.agents/PLANS.md` now includes compact debt-tracker conditions.

## TODO Resolution Status

All requested TODO items are resolved:

- Resolved overlap by harmonizing legacy files to ExecPlan model.
- Resolved conflicts/mismatches in:
  - `.agents/rules/documentation.md`
  - `.agents/skills/documentation/SKILL.md`
  - `.agents/workflows/implement-and-document.md`
- Resolved source-of-truth ambiguity (ExecPlans in `docs/exec-plans/active/`).
- Resolved boundary ambiguity by clarifying file roles and conditional workflow routing.
- Resolved terminology drift (`Execution Plan` is canonical).
- Resolved archival drift (removed legacy `/tasks/archive` semantics from legacy files; retained only `docs/exec-plans/completed/{timestamp}-{name}.md`).
- Added concrete guidance to avoid over-triggering docs workflow (`skip`/`minimal`/`full`).
- Added compact debt-tracker condition in `.agents/PLANS.md`.

Deferred by design (explicitly kept as minor):

- timezone/source convention detail for completion timestamp naming
- cancelled/superseded lifecycle branch in `.agents/PLANS.md`

## Desired Adaptations Implementation Check

1. **Explicit routing model implemented**
   Implemented: workflow and rule now operate from active ExecPlans in `docs/exec-plans/active/`, with completion move to `completed/`.

2. **Terminology normalized**
   Implemented: legacy files no longer refer to `IMPL Directive`, `Implementation Directive`, or `/tasks/*-IMPL.md`.

3. **Archival language unified**
   Implemented: legacy `/tasks/archive` archival references removed; completion archival now aligned to `docs/exec-plans/completed/{timestamp}-{name}.md`.

4. **Clear workflow-step verification requested**
   Implemented via the `Current status of workflow adaptation` section below.

## Roles and Precedence

## `AGENTS.md`

- Repository operating contract and architecture boundaries.
- Defines discovery protocol, docs structure, and when ExecPlans are expected.
- Highest repository-level instruction file for agents.

## `.agents/PLANS.md`

- ExecPlan authoring/implementation standard.
- Defines quality bar, required sections, and plan lifecycle behavior.
- Operational source of truth for plan rigor and completion handling.

## Legacy files (still relevant, now narrowed)

- `.agents/rules/documentation.md`
  Documentation update rule, now scoped to docs work derived from ExecPlans and implemented behavior.

- `.agents/skills/documentation/SKILL.md`
  Invocation guidance for docs-focused tasks; no longer a blanket post-implementation default.

- `.agents/workflows/implement-and-document.md`
  Operator workflow checklist for implementation runs, now ExecPlan-first and docs-update-conditional.

## Workflow

## AI coding agent perspective

1. Read `AGENTS.md` to establish repository conventions and boundaries.
2. For complex work, operate from an active ExecPlan (`docs/exec-plans/active/*.md`) and follow `.agents/PLANS.md`.
3. Implement and validate against ExecPlan acceptance criteria.
4. Determine documentation depth:
   - `skip` if no doc-visible behavior/contract changed
   - `minimal` for local doc edits
   - `full` for architecture or cross-cutting behavior changes
5. Apply `.agents/rules/documentation.md` only when depth is `minimal`/`full` or docs updates are explicitly requested.
6. If deferred documentation work remains, add one concise debt entry to `docs/exec-plans/tech-debt-tracker.md`.
7. Move completed plan to `docs/exec-plans/completed/` using `{yyyy-MM-dd-HH-mm-ss}-{original-file-name-without-extension}.md`.

## Human operator perspective

1. Keep the target work anchored in an active ExecPlan for non-trivial work.
2. Ask the agent to execute implementation against that plan.
3. Decide whether docs updates are required:
   - no behavior/contract change -> skip docs update
   - narrow behavior/contract change -> minimal docs update
   - broad architecture/system behavior change -> full docs update
4. Use `implement-and-document` when you want a structured end-to-end run (implementation + cleanup + conditional documentation update + plan closeout).
5. For small code-only changes, you can skip `implement-and-document` and ask for a focused implementation/test pass.

## When to use legacy `implement-and-document`, if at all

- Use it for complex or cross-cutting tasks where you want strict process sequencing.
- Optional for small scoped changes.
- Not required when you explicitly request implementation-only work with no documentation impact.

## Relevance of `documentation.md` rule

- **Still relevant:** yes, for documentation consolidation/verification tasks.
- **Not default:** do not apply automatically to every code change.
- **Best use:** when documentation must be updated to reflect changed behavior/contracts, or when user explicitly asks for docs work.

## Relevance of `SKILL.md`

- **Still relevant:** yes, as trigger guidance for docs-focused tasks.
- **Not universal:** should not be auto-applied for pure implementation runs without doc impact.
- **Primary value:** consistent, quality-checked docs updates tied to ExecPlan context.

## Current status of workflow adaptation

- Documentation-consolidation steps are effectively human/operator-driven and conditionally applied by task scope.
- Legacy documentation rule no longer conflicts with ExecPlan lifecycle because it now references `docs/exec-plans/*` and deferred debt handling there.
- Workflow over-triggering risk is reduced by explicit `skip`/`minimal`/`full` depth gating.
- Legacy `/tasks`/`/reports` process dependencies have been removed from the three legacy files.

## Simplifications Potential (`.agents/PLANS.md`)

`PLANS.md` remains high quality and thorough. Remaining simplification opportunities:

1. Introduce optional two-tier execution mode (`core` vs `extended`) for speed-sensitive work.
2. Consolidate duplicated guidance across sections into a tighter non-negotiables block.
3. Add compact completion checklist near lifecycle bullets for faster compliance.

Preserve as strict:

- self-contained novice-guiding plans
- observable acceptance and evidence-based validation
- living sections (`Progress`, `Surprises & Discoveries`, `Decision Log`, `Outcomes & Retrospective`)
