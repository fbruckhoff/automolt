---
description: Implement from an active ExecPlan, then perform documentation updates when required
---

- [ ] If the user has specified an input source execution plan (ExecPlan) in `docs/exec-plans/active/`, compare the plan against the requirements for ExecPlans as outlined in `.agents/PLANS.md`. If it does not follow the required structure and rules, treat it as a draft and refine it to satisfy the requirements of ExecPlan documents while staying true to the original intent. If the user has not specified any specific ExecPlan file, create a new file under `docs/exec-plans/active/` with an appropriate name in kebab-case, and write it based on the user's intent.

- [ ] Treat the ExecPlan as the implementation source of truth. Implement all required milestones from the selected ExecPlan. Keep `Progress`, `Decision Log`, `Surprises & Discoveries`, and `Outcomes & Retrospective` current while working.

- [ ] Validate implementation completeness and correctness against the ExecPlan acceptance criteria. Fix any mistakes or inconsistencies before proceeding.

- [ ] When done, sequentially apply all relevant code cleanup rules.

- [ ] Choose documentation update depth based on implementation impact:
  - `skip`: no doc-visible behavior or contract changes
  - `minimal`: localized edits in existing docs
  - `full`: cross-cutting architecture/behavior docs updates

- [ ] Apply `/documentation.md` only when depth is `minimal` or `full`, or when documentation updates are explicitly requested by the user.

- [ ] If design docs were added or changed, update `docs/design-docs/_index.md` with verification status.

- [ ] If documentation updates are intentionally deferred, append exactly one concise debt entry to `docs/exec-plans/tech-debt-tracker.md`.

- [ ] Before completion, verify `docs/exec-plans/tech-debt-tracker.md` contains only debt entries and no full plan/research sections.

- [ ] When the ExecPlan is complete, move it from `docs/exec-plans/active/` to `docs/exec-plans/completed/` using `{yyyy-MM-dd-HH-mm-ss}-{original-file-name-without-extension}.md`.
