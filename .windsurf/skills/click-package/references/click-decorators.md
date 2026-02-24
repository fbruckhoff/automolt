# Click Decorators

- `@click.password_option()`: Hidden prompt with confirmation
- `@click.confirmation_option()`: Dangerous operation confirmation (--yes flag)
- `@click.version_option()`: Auto --version flag

## Rules:
- Treat `@click.command()` as a transformer: the function becomes a `Command`, not a callable.
- Rely on Click’s name normalization unless CLI UX demands a custom name.
- Decorator order matters; options/arguments attach in decoration order.
- Assume decorated params are appended, not inserted—ordering affects parsing and callbacks.
- Prefer `@click.group()` only when subcommands are real; don’t over-group.
- Use `@argument` for required positional data; don’t fake it with options.
- Use `cls=` only when extending Click internals; default classes cover most needs.
- Prefer `password_option()` over manual prompts for secure input.
- Use `confirmation_option()` only for destructive actions; it exits early by design.
- Prefer `version_option()` over custom callbacks; it’s eager, safe, and standardized.
- Avoid redefining `--help`; let `help_option()` handle eager exit correctly.
- Use `pass_context` sparingly; leaking ctx everywhere couples commands tightly.
- Prefer `pass_obj` to pass state, not control.
- Use `make_pass_decorator()` for layered apps; it avoids manual ctx plumbing.
- Use `pass_meta_key` for cross-cutting concerns, not core command data.

For full reference, see the "Decorators" section of the Click API docs:
https://click.palletsprojects.com/en/stable/api/#decorators

Additional reference:
https://click.palletsprojects.com/en/stable/option-decorators/
