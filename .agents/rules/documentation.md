---
description: Workflow for updating living documentation from active Execution Plans and implemented system behavior
---

# Documentation Consolidation Rule

This rule governs how documentation is updated from Execution Plans and verified implementation behavior.

## Scope and Rules

- Source plan artifacts are ExecPlan files under `docs/exec-plans/active/` (or a recently completed plan in `docs/exec-plans/completed/` when backfilling docs).
- This rule is not the default for every implementation task. Apply it when:
  - docs updates are explicitly requested, or
  - implementation changed user-visible behavior, architecture boundaries, or operational contracts.
- Living documentation `*.md` files live under `/docs` with category-based placement:
  - `docs/design-docs/` for architecture, rationale, boundaries, and core beliefs
  - `docs/product-specs/` for product-facing behavior contracts
  - `docs/references/` for stable reference material
  - `docs/generated/` for generated artifacts (only when explicitly requested)
- Execution plans are first-class artifacts under `docs/exec-plans/`:
  - active plans in `docs/exec-plans/active/`
  - completed plans in `docs/exec-plans/completed/`
  - debt register in `docs/exec-plans/tech-debt-tracker.md`
- The target documentation must describe current behavior and architecture as verifiably implemented in the codebase, not implementation instructions.
- Each documentation file must have YAML frontmatter:
```
---
includes: ...
excludes: ...
related: ...
---
```

`includes:` describes what part(s) of the system this documentation file covers.
`excludes:` optional scope clarifier when boundaries are non-obvious.
`related:` optional complementary docs list (do not include `_index.md`).

- If boundaries are blurry with other docs, update all affected docs to clarify coverage.
- Do not follow circular references. Do not reload files already in context.
- `docs/design-docs/_index.md` is the design-doc catalog; update it when design-doc coverage changes.

## Inputs

1. One or more source ExecPlan files from `docs/exec-plans/active/` (or specific completed plans when requested).
2. Optional target docs under `/docs/**`; if no fit exists, create a focused doc in the correct category.
3. Relevant source code modules for fact verification.

## Non-Negotiable Quality Gates

1. Every newly added or changed documentation claim must be verified against code.
2. Any discrepancy must be recorded in the source ExecPlan’s `Surprises & Discoveries` and/or `Decision Log`.
3. If documentation work is intentionally deferred, add one concise debt entry to `docs/exec-plans/tech-debt-tracker.md`.
4. `docs/exec-plans/tech-debt-tracker.md` is debt-only; never copy/move full ExecPlan content into it.
5. Do not move an ExecPlan from `active` to `completed` before required docs updates and verification are done.

## Execution Workflow

### Step 1) Discover and baseline

- Read source ExecPlan(s) and target docs.
- Discover documentation context via:
  1. `ARCHITECTURE.md`
  2. `docs/design-docs/_index.md`
  3. relevant docs in `docs/`
- Identify the exact claims that changed and the code modules required for verification.

### Step 2) Choose update depth

- Use one mode and record the decision in the ExecPlan:
  - **Skip:** no doc-visible behavior/contract changes.
  - **Minimal:** localized doc edits only.
  - **Full:** cross-cutting or architecture-level changes.

### Step 3) Update living docs

- Merge validated behavior into target docs under `/docs/**`.
- Rewrite as factual documentation; remove process/implementation-instruction language.
- Update `docs/design-docs/_index.md` when design-doc set or status changes.

### Step 4) Verify and self-audit

- Re-read updated docs for omissions, overstatements, stale claims, and scope overlap.
- Re-check every new claim against code.
- Record discrepancies and decisions in the source ExecPlan.

### Step 5) Finalize plan state

- Update ExecPlan `Progress` and `Outcomes & Retrospective`.
- If deferred documentation work remains, append one concise debt tracker entry only.
- Confirm the debt tracker remains a debt log and does not contain full plan/research content.
- If plan is complete, move from `docs/exec-plans/active/` to `docs/exec-plans/completed/` with:
  `{yyyy-MM-dd-HH-mm-ss}-{original-file-name-without-extension}.md`

## Deliverable Checklist

- [ ] Documentation updated in `/docs/**` where required
- [ ] New/changed claims verified against code
- [ ] Discrepancies/decisions captured in source ExecPlan
- [ ] `docs/design-docs/_index.md` updated when applicable
- [ ] Deferred items added to debt tracker when applicable
