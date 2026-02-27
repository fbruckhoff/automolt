---
trigger: model_decision
description: Git commit & versioning
---
Use this rule for any repository that follows Conventional Commits and SemVer.

## Commit message format

Use the Conventional Commits structure:

```text
<type>[optional scope in "()"]: <description>

[optional body]

[optional footer(s)]
```

## Allowed types

- `feat`
- `fix`
- `docs`
- `refactor`
- `test`
- `security`
- `chore`
- `build`
- `style`
- `perf`
- `ci`
- `revert`

## Scope policy

Scopes are optional.

When a repository defines an explicit scope allowlist, use that allowlist exactly.

For this repository, the authoritative allowlist is the **Allowed Scopes** section in `CONTRIBUTING.md`.

If commit scopes are regex-enforced in configuration (for example in `pyproject.toml` Commitizen settings), keep those definitions synchronized with `CONTRIBUTING.md`.

## SemVer policy

Versioning follows Semantic Versioning. Version tags must be prefixed with `v`.

When Commitizen is configured, follow the repository's configured bump map.

## Commit strategy

If there are several pending commits to be made, they must be ordered to prioritize functional fixes first, then infrastructure, then structural changes, then documentation, then build changes, etc. This ensures that critical fixes are available even if later commits need to be reverted or adjusted.
