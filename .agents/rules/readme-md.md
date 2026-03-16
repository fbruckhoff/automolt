---
description: Style and scope constraints when editing README.md
glob: "README.md"
---

Apply this rule only when editing `README.md`.

## Scope

- Keep `README.md` product-facing and user-facing.
- Avoid duplicating contributor process details that belong in `CONTRIBUTING.md`.
- Point contributors to `CONTRIBUTING.md` for contribution workflow details.

## Style guide requirement

Follow the GitHub Docs style guide for tone, structure, and readability:

- https://docs.github.com/en/contributing/style-guide-and-content-model/style-guide

Use best judgment from that guide, especially:

- clear, direct language,
- short sections with descriptive headings,
- task-oriented instructions,
- consistent terminology.

## Consistency checks

Before finalizing README changes:

1. Verify contribution-specific instructions are in `CONTRIBUTING.md`, not duplicated here.
2. Verify `README.md` still links to `CONTRIBUTING.md` for contribution setup and policy.
3. Verify any mention of commit conventions links to Conventional Commits when relevant.
