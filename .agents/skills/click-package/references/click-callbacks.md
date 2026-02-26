# Click Package Callbacks

## Callback Execution & Order
- Click reconciles programmer-defined and user-provided argument order before callbacks.
- Callbacks run **after** parsing and full value conversion (including prompt input).
- Callback order generally follows the sequence arguments appear on the command line.
- **Eager** options (e.g. --help, --version) evaluate before all non-eager ones; the first eager option on the command line wins and exits.
- For repeated options, callback fires at the **first** occurrence's position.
- Repeated params pass all values to the first callback; others are ignored if not multi.
- Missing parameters still trigger their callbacks, fired at the very end.
- Missing callbacks can access/default to values from earlier parameters.

## Callback Context & Invocation
- Command callbacks receive only non-hidden parameters as keyword arguments.
- The context (`ctx`) is NOT passed unless the callback opts in via `@pass_context`.
- `Context.invoke()` inspects the callback and injects `ctx` only if required.
- Never assume a callback's signature includes `ctx`.
- Do not call command callbacks directly; always go through the context.
- Use `Context.invoke()` to call a callback safely when its signature is unknown.
- Treat `Context.invoke()` as the canonical adapter for callback invocation.

## Best Practices
- Prefer eager options only for flow-terminating behavior (help/version); misuse causes surprising skips.
- Always guard callbacks with `ctx.resilient_parsing` to avoid side effects during help parsing.
- Treat callbacks as pure functions when possible; side effects complicate ordering guarantees.
- Assume callback order is positional, not declarative; design accordingly.
- Don't rely on missing params being absent—callbacks still fire with defaults at the end.
- You can apply custom validation logic in parameter callbacks.

## Validation & Error Handling
- Raise `BadParameter` for user-facing validation; it auto-binds errors to params.
- Use `expose_value=False` to keep control flags out of command signatures.
- Do not mutate `ctx.params`; wrap values instead for clarity and safety.

## Advanced Patterns
- Normalize tokens when designing case-insensitive CLIs; do it at context creation.
- Prefer subcommands over `forward()` / `invoke()`; cross-calling commands is brittle.
- When forwarding unknown options, isolate them fully; don't partially parse unless unavoidable.
- Disable interspersed args if mixing foreign CLIs; reduces ambiguity.
- Open shared resources at group level with `with_resource()`; never manually manage lifetime.
- Register cleanup with `call_on_close()` for non-context resources.

Advanced References:
https://click.palletsprojects.com/en/stable/advanced/
https://click.palletsprojects.com/en/stable/complex/
