---
glob: "CONTRIBUTING.md"
description: Style and synchronization requirements when editing CONTRIBUTING.md
---

Apply this rule only when editing `CONTRIBUTING.md`.

## Style guide requirement

Follow the GitHub Docs style guide for tone, structure, and readability:

- https://docs.github.com/en/contributing/style-guide-and-content-model/style-guide

## Required sections and intent

`CONTRIBUTING.md` must clearly cover:

- development setup,
- contribution workflow,
- commit conventions,
- **Allowed Scopes**,
- release workflow,
- security reminders for contributors.

## Allowed Scopes verification (mandatory)

When editing `CONTRIBUTING.md`, explicitly verify completeness and correctness of **Allowed Scopes** by inspecting both files:

1. `CONTRIBUTING.md` (**Allowed Scopes** section), and
2. `pyproject.toml` in `[tool.commitizen.customize]`:
   - `schema_pattern`, and/or
   - `commit_parser`.

Synchronization rule:

- If scopes differ between docs and regex configuration, update them to match in the same change.
- Do not leave partial synchronization.

## Git rules reference

Ensure `CONTRIBUTING.md` mentions `.agents/rules/git.md` and clarifies that repository-specific scope policy lives in `CONTRIBUTING.md`.
