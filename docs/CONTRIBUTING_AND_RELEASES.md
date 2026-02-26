---
includes: Contributor/release policy location and synchronization rules for docs and Commitizen config
excludes: Full contributor onboarding details and command runtime behavior
---

# Contributing and Releases

## Source of truth

Use the repository-root [`CONTRIBUTING.md`](../CONTRIBUTING.md) as the authoritative contributor guide.

`CONTRIBUTING.md` defines:

- development environment setup,
- commit conventions,
- allowed scopes,
- release workflow.

## Synchronization contract

When commit scope policy changes, update both of these together:

1. `CONTRIBUTING.md` **Allowed Scopes** section,
2. `pyproject.toml` Commitizen scope allowlist in:
   - `[tool.commitizen.customize].schema_pattern`
   - `[tool.commitizen.customize].commit_parser`

The `.windsurf/rules/git.md` rule is intentionally generic and defers repository-specific scopes to `CONTRIBUTING.md`.

## Release command

Use on explicit request only:

```bash
uv run cz bump --changelog
```

This updates version metadata, changelog, and creates a git tag according to project Commitizen configuration.

For onboarding and complete contribution instructions, always consult `CONTRIBUTING.md`.
