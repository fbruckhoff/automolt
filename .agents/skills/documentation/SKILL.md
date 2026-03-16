---
name: documentation
description: Update living documentation from active Execution Plans and implemented behavior. Use for explicit documentation updates, verification, or docs refactors.
---

# Documentation Consolidation Skill

Use this skill for documentation work. It is not the default for every implementation task.

Primary rule to apply:

- `.agents/rules/documentation.md`

## Trigger Heuristics

Apply this skill when the user request includes any of:

- explicit requests to update or audit docs under `docs/**`
- requests to validate documentation claims against code
- requests to refactor design-doc boundaries or frontmatter coverage
- requests to reconcile docs with an active ExecPlan (Execution Plan) in `docs/exec-plans/active/`

## Required Workflow

1. Read source ExecPlan context and target docs.
2. Discover target docs with progressive disclosure: `ARCHITECTURE.md` -> `docs/design-docs/_index.md` -> relevant docs in `docs/`.
3. Select doc update depth: `skip`, `minimal`, or `full`.
4. Consolidate into living documentation only (no implementation instructions).
5. Verify new facts against code.
6. Record discrepancies and major decisions in the source ExecPlan.
7. If documentation work is deferred, add an item to `docs/exec-plans/tech-debt-tracker.md`.
8. Run final integrity checks (claims verified, docs index/status updated where applicable).

Execution timing:

- If a prompt directly asks for documentation consolidation/verification, apply this workflow immediately.
- If a prompt is implementation-only and does not include doc-impact changes, do not apply this workflow.

## Hard Constraints

- Do not introduce or rely on deprecated legacy directive/report paths.
- Treat `/docs` as category-structured living docs:
  - `docs/design-docs/`
  - `docs/product-specs/`
  - `docs/references/`
  - `docs/generated/` (generated artifacts)
- Treat `docs/exec-plans/` as versioned plan artifacts.
- Record every discrepancy explicitly.
- If no discrepancy exists, state this explicitly in the ExecPlan note/update.
- When creating/updating design docs, update `docs/design-docs/_index.md` with verification status.

## Output Expectations

- Updated documentation file(s) in `/docs/**`.
- Verified documentation claims against code.
- Source ExecPlan updated with doc decisions/discrepancies.
- Debt tracker updated only when docs work is intentionally deferred.
