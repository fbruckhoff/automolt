# Contributing to Automolt

Thanks for contributing to `automolt`.

This guide is the source of truth for contributor setup, commit conventions, scope policy, and release workflow.

## Prerequisites

- Python 3.14.3+
- [uv](https://docs.astral.sh/uv/)
- Git

## Development environment setup

Run the one-command setup from repository root:

```bash
make dev-setup
```

This command:

1. syncs dev dependencies,
2. installs the `commit-msg` hook,
3. installs the CLI as an editable uv tool.

Manual equivalent:

```bash
uv sync --dev
uv run pre-commit install --hook-type commit-msg
uv tool install --editable --reinstall .
```

### IDE integration (Windsurf)

If using Windsurf on macOS, create symlinks for IDE integration:

```bash
ln -sf ../.agents/rules .windsurf/rules
ln -sf ../.agents/skills .windsurf/skills
ln -sf ../.agents/workflows .windsurf/workflows
```

When dependencies or entry points change in `pyproject.toml`, rerun:

```bash
uv tool install --editable --reinstall .
```

## Workflow

1. Create a focused branch.
2. Make changes with clear scope.
3. Run checks before opening a PR:

```bash
uv run ruff check .
uv run ruff format .
```

4. Update docs when behavior changes.
5. Write PR descriptions that explain what changed and why.

## Commit conventions

Commits must follow [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/).

Enforcement is done by Commitizen via `.pre-commit-config.yaml` (`commit-msg` hook).

Required format:

```text
<type>(<optional-scope>): <description>
```

### Allowed types

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

### Allowed Scopes

Scopes are optional. If you use a scope, it must be lowercase and one of:

- `agents`
- `api`
- `automation`
- `cli`
- `comment`
- `config`
- `init`
- `llm`
- `models`
- `persistence`
- `profile`
- `release`
- `scheduler`
- `search`
- `sessions`
- `submolts`
- `upvote`

> Scope source of truth: this section must stay synchronized with `pyproject.toml` `[tool.commitizen.customize]` `schema_pattern` and `commit_parser` scope allowlists.

## Synchronization

When commit scope policy changes, update both files in the same change:

1. `CONTRIBUTING.md` -> update **Allowed Scopes** section.
2. `pyproject.toml` -> update both:
   - `[tool.commitizen.customize].schema_pattern`
   - `[tool.commitizen.customize].commit_parser`

The `.agents/rules/git.md` rule is intentionally generic and defers repository-specific scopes to `CONTRIBUTING.md`.

Then verify:

```bash
uv run cz check --message "fix(<scope>): verify scope"
```

If the scope was removed, verify an old scope now fails.

## Semantic versioning and releases

This project uses [Semantic Versioning](https://semver.org/).

Commitizen bump mapping:

- `feat` -> `MINOR`
- `fix` -> `PATCH`
- `refactor` -> `PATCH`
- `security` -> `PATCH`

Release command:

```bash
uv run cz bump --changelog
```

This updates `pyproject.toml`, updates `CHANGELOG.md`, and creates a git tag for the new version.

## Security reminders

- Never commit secrets, credentials, or personal data.
- Treat local client state and API keys as sensitive.
