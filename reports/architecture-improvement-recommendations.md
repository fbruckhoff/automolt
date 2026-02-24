# Architecture Improvement Recommendations

Findings from the code quality inspection of the `automolt/` directory, focused on separation of concerns and architectural patterns.

## 1. Eager Context Initialization in `cli.py`

**File:** `automolt/cli.py`

The `cli()` group callback creates `MoltbookClient`, `AgentService`, and `Console` for every command invocation, even commands that don't need them:

- `automolt init` does not use `api_client` or `agent_service`
- `automolt agents` does not use `api_client` or `agent_service`

**Recommendation:** Use lazy initialization via a context helper or `@click.pass_context` with on-demand service creation. For example, a `get_agent_service(ctx)` helper that creates the service only when first accessed. This avoids unnecessary HTTP client creation and improves startup time for simple commands.

## 2. Inconsistent Error Propagation from Persistence Layer

**Files:** `automolt/persistence/agent_store.py`, `automolt/persistence/client_store.py`

The persistence layer now raises `ValueError` for corrupted configs, but not all callers handle it consistently:

- `profile_command.py` handles `ValueError` (added during cleanup)
- `signup_command.py` does not encounter this path (creates new configs)
- `agents_command.py` does not call `load_agent_config` directly

**Recommendation:** Consider a dedicated `ConfigCorruptedError` exception in the persistence layer instead of generic `ValueError`. This makes it easier for callers to distinguish between "bad data" and other `ValueError` sources.

## 3. Validation Duplication Between CLI and Models

**Files:** `automolt/commands/signup_command.py`, `automolt/models/agent.py`

Handle length validation exists in two places:
- `signup_command.py` checks `len(handle) > 50` in the prompt loop
- `models/agent.py` now enforces `max_length=50` via Pydantic

Similarly, description length is validated in both the command handler and the model.

**Recommendation:** This duplication is acceptable for UX (early feedback before API call), but consider extracting the validation constants (e.g., `MAX_HANDLE_LENGTH = 50`, `MAX_DESCRIPTION_LENGTH = 500`) into a shared location so both layers reference the same values.

## 4. Inconsistent Logging Coverage

**Files:** `automolt/services/automation_service.py`, `automolt/services/scheduler_service.py`, `automolt/services/search_service.py`, plus other service/persistence modules

The codebase now has structured logging in automation and scheduler pathways, but coverage is still uneven:

- Some modules use `logging` with useful operational context
- Other services/persistence modules still rely entirely on command-layer Rich output
- Logging configuration is not centralized at the CLI entrypoint

**Recommendation:** Standardize logging usage across all services and persistence modules, and configure log level centrally in the CLI entrypoint (optionally with a `--verbose` / `--debug` flag).

## 5. Hard-coded CLI Name (not good)

Some places like `automation_service.py` have the CLI name `automolt` hard-coded. It is better to obtain that from one single source or variable, so the CLI's name can be changed with ease if needed.
