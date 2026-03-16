# AGENTS.md

This repo uses `.agents/` as the canonical agent config directory. Subdirectories of `.windsurf/` symlink into `.agents/` subdirectories.

## automolt CLI

Working conventions for contributors and coding agents collaborating on the `automolt` repository.

## Research Protocol

Use progressive disclosure. Start with stable entry points, then drill down:

1. `ARCHITECTURE.md` (high-level codemap and invariants)
2. `docs/design-docs/_index.md` (index of design docs: find relevant documentation files here and study them)
3. Source code modules

## Docs Structure

`docs/` is structured as follows:

- `design-docs/`: design rationale, architecture boundaries, core beliefs, verified design notes
- `exec-plans/`: versioned execution plans and technical debt tracking
  - `active/`: in-progress plans
  - `completed/`: archived finished plans
  - `tech-debt-tracker.md`: known technical debt backlog
- `generated/`: generated documentation artifacts
- `product-specs/`: behavior/specification docs for product-facing functionality
- `references/`: product-specific reference material not covered by skills

## Execution Plans (ExecPlans)

When writing complex features or significant refactors, use an ExecPlan (as described in `.agents/PLANS.md`) from design to implementation.

## Project Scope

`automolt` is a Python command-line client for the Moltbook social network, focused on:

- local client/workspace initialization,
- agent identity/profile management,
- search/comment/upvote/submolt operations,
- automation setup and scheduler lifecycle control.

## Architecture Boundaries

High-level layering:

1. **Controllers**: CLI commands and automation command surface
2. **Services**: business logic and orchestration
3. **Models / Persistence / API Client**: typed data, local storage, and HTTP integration

Key boundary rules:

- Command handlers own UX/CLI concerns and delegate behavior.
- Services own orchestration and policy.
- Persistence owns file/DB/runtime-state I/O.
- API client modules own external protocol boundaries.
- Keep these boundaries explicit; avoid leaking CLI concerns into service/persistence layers.

## Session Agent Resolution Contract

All agent-targeted commands must support `--handle`. Runtime targeting order is:

1. explicit `--handle` (highest priority),
2. session `active_agent` from `.sessions/<PPID>.json`,
3. lazy initialization from `client.json:last_active_agent`.

Additional rules:

- `--handle` never mutates session state or `last_active_agent`.
- Only `automolt agents` selection updates both current session `active_agent` and remembered `last_active_agent`.
- If users always pass `--handle`, no session file is required.
- Stale `.sessions/<PPID>.json` files should be swept when PPIDs no longer exist.

## Tech Stack

- Python 3.14.3+
- Click
- Rich
- Pydantic
- httpx
- OpenAI Python SDK
- Ruff
- Commitizen
- pre-commit
- UV

## Packaging and Imports

- Packaging is defined in `pyproject.toml`.
- The CLI entry point must remain:

```toml
[project.scripts]
automolt = "automolt.main:main"
```

- Use absolute imports throughout the codebase (for example, `from automolt.services.agent_service import AgentService`).
- Keep `automolt/__init__.py` setting `sys.dont_write_bytecode = True` to avoid `__pycache__` clutter in source directories.

## Dependency Management

For contributor machine setup, run from repository root:

```bash
make dev-setup
```

When dependencies or entry points change in `pyproject.toml`, reinstall the CLI tool from repository root:

```bash
uv tool install --editable --reinstall .
```

Editable install symlinks source code, so routine Python and documentation edits are reflected immediately.

## Commit Conventions and Scope Sync

- Follow `CONTRIBUTING.md` as the repository source of truth for contributor workflow, commit conventions, and release process.
- Repository-specific commit scope allowlist lives in `CONTRIBUTING.md` under **Allowed Scopes**.
- Keep `CONTRIBUTING.md` **Allowed Scopes** synchronized with `pyproject.toml` Commitizen scope enforcement (`schema_pattern` and `commit_parser`).

## Contribution Expectations

- Keep changes focused and architecture-consistent.
- Prefer clear, maintainable implementations over clever shortcuts.
- Update living documentation for behavior changes.
- Never commit secrets, credentials, or personal data.
