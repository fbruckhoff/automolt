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

Versioning follows Semantic Versioning.

When Commitizen is configured, follow the repository's configured bump map.

## Release command

Use the repository's configured release command/tooling.

For this repository, use:

```bash
uv run cz bump --changelog
```
