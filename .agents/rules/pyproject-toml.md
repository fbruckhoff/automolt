---
glob: "pyproject.toml"
description: Keep Commitizen scope regex and CONTRIBUTING.md Allowed Scopes synchronized
---

Apply this rule only when editing `pyproject.toml`.

## Scope synchronization contract

When changing Commitizen scope enforcement in `[tool.commitizen.customize]`, keep `CONTRIBUTING.md` synchronized in the same change.

Specifically, if you edit either of these fields:

- `schema_pattern`
- `commit_parser`

then you must also update `CONTRIBUTING.md` **Allowed Scopes** to exactly match the effective scope allowlist.

Likewise, when a scope is added or removed in `CONTRIBUTING.md`, this file must be updated to match.

## Verification steps

1. Extract allowed scopes from `schema_pattern` and/or `commit_parser`.
2. Compare against `CONTRIBUTING.md` **Allowed Scopes**.
3. Reconcile differences before finalizing edits.

Optional runtime check:

```bash
uv run cz check --message "fix(<scope>): sync scope policy"
```

Use lowercase scopes unless the repository explicitly defines otherwise.
