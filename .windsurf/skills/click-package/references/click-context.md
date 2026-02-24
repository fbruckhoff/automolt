# Click Context

## Rules:
- Assume a new Context is created per command invocation; never reuse across runs.
- Treat Context as the single source of truth for parsed params and runtime state.
- Use parent contexts to read shared state; avoid mutating parent data unless intentional.
- Rely on context chaining for subcommands; data flows downward, not upward.
- Navigate parent contexts only when necessary; deep traversal signals design smell.
- Register cleanup on the Context; never manage lifecycle manually outside it.
- Expect Context to own resource teardown after command completion.
- Pass Context explicitly (`pass_context`) only when logic truly depends on it.
- Mark the root with `pass_context()` when initializing shared state.
- Store app-level state on `ctx.obj`, not globals.
- Pass state downward implicitly via context, not via parameters.
- Attach subcommands to a group; inherit state via Context, not globals.
- Use pass-decorators to fetch the *nearest* matching object up the context chain.
- Treat `Context.find_object()` as read-only lookup; it fails if missing.
- Use context linking as a scoped dependency injection mechanism.
