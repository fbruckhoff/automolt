# AGENTS.md

## automolt CLI

Working conventions for contributors and coding agents collaborating on the `automolt` repository.

## Research Protocol

Before scanning source files, read `docs/_INDEX.md` and then the relevant living docs in `docs/`. This keeps implementation work aligned with current architecture and avoids duplicate investigation.

## Project Scope

`automolt` is a Python command-line client for the Moltbook social network, focused on:

- local client/workspace initialization,
- agent identity/profile management,
- search/comment/upvote/submolt operations,
- automation setup and scheduler lifecycle control.

## Tech Stack

- Python 3.14.3+
- Click
- Rich
- Pydantic
- httpx
- OpenAI Python SDK
- Ruff
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

When dependencies or entry points change in `pyproject.toml`, reinstall the tool from repository root:

```bash
uv tool install --editable --reinstall .
```

Editable install symlinks source code, so routine Python and documentation edits are reflected immediately.

## Architecture

High-level layering:

1. **Controllers**: CLI commands and automation command surface
2. **Services**: business logic and orchestration
3. **Models / Persistence / API Client**: typed data, local storage, and HTTP integration

Reference docs:

- `docs/CLI_ARCHITECTURE.md`
- `docs/MODELS_AND_PERSISTENCE.md`
- `docs/CLIENT_CONFIG.md`
- `docs/AUTOMATION.md`

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

## Contribution Expectations

- Keep changes focused and architecture-consistent.
- Prefer clear, maintainable implementations over clever shortcuts.
- Update living documentation for behavior changes.
- Never commit secrets, credentials, or personal data.
