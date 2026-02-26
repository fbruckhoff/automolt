# Click Architecture Best Practices

## CLI Structure & State Management
- Model Git-style CLIs as a root group with subcommands, not flat commands.
- Use the root command to parse global config, environment defaults, and initialize shared state exactly once.
- Load any config, env vars, and flags as early as possible at the root level.
- Store shared state on `ctx.obj`; treat it as the canonical app container.
- Pass state downward implicitly via context, not via parameters or globals.
- Use `@click.group()` to scope lifecycle and cleanup to the whole CLI run.
- Mark the root with `pass_context()` when initializing shared state.
- Assume subcommands depend on `ctx.obj`; design them to fail clearly if missing.
- Attach subcommands to a group; inherit state via Context, not globals.

## Context & Dependency Injection
- Use `pass_obj()` when you want the exact object stored on `ctx.obj`.
- Prefer `make_pass_decorator(Type)` to stay robust in interleaved command trees.
- Use pass-decorators to fetch the *nearest* matching object up the context chain.
- Treat `Context.find_object()` as read-only lookup; it fails if missing.
- Enable `ensure=True` when commands must run standalone; only use if the object has a zero-arg constructor.
- Expect `ensure=True` to overwrite inner objects; design for that.
- Assume plugins may override `ctx.obj`; never rely on its exact identity.
- Design child commands to depend on behavior, not context structure.
- Prefer explicit object passing over re-reading options in subcommands.
- Use context linking as a scoped dependency injection mechanism.

## Lazy Loading
- Use lazy-loaded subcommands only for large or slow-import CLIs; treat as a performance optimization, not a default.
- Implement lazy loading via a custom `Group` subclass; define by passing `cls=LazyGroup` at group creation.
- Defer imports to `Group.get_command()`, not module import time.
- Keep a static map of command names → import paths.
- Declare lazy subcommands as name → import-path mappings.
- Expect lazy loading during command resolution (`cli bar baz`), help rendering (`cli --help`), and shell completion (TAB).
- Do not assume lazy commands are unloaded during `--help`.
- Always expose lazy commands in `list_commands()` for `--help`.
- Guard against non-Command returns; fail loudly.
- Know that nested LazyGroups compose recursively.

## Lazy Loading Best Practices
- Design lazy modules to be import-safe and side-effect free.
- Avoid heavy work at import time in lazy-loaded modules; defer to callbacks when possible.
- Avoid order-dependent side effects in lazily imported modules.
- Prefer eager imports if command behavior depends on shared globals.
- Use callback-level imports for maximum deferral.
- Rely on Click metadata (options/args) to keep help functional.
- Prefer simpler callback deferral before custom Command subclasses.
- Assume lazy loading can hide circular imports; design defensively.
- Test help and completion paths; they trigger imports.
- Run `--help` on every subcommand in tests to force-load them.

## Unicode & Output Handling
- Writing Click-native code keeps behavior portable across platforms.
- Unicode-safe APIs are limited to `click.echo`, `click.prompt`, `click.get_text_stream`.
- Console detection decides behavior: real console → emulated unicode stream.
- Click flushes aggressively, but manual flushing may be needed in edge cases.
- Mixing byte and unicode writes can cause buffering artifacts; avoid it.
