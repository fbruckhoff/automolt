# Click Exception Handling and Exit Codes

Click automatically handles exceptions and sets appropriate exit codes.

## Automatic Error Handling

**Click's `Command.main()` handles:**
1. `EOFError` and `KeyboardInterrupt` → converted to `Abort`
2. `ClickException` subclasses → displays error via `.show()` method, exits with `.exit_code`
3. `Abort` → prints "Aborted!" to stderr, exits with code 1
4. Success → exits with code 0

## Manual Exception Handling

**Invoke command directly (exceptions bubble up):**
```python
ctx = command.make_context("command-name", ["args", "go", "here"])
with ctx:
    result = command.invoke(ctx)
```

**Disable automatic handling:**
```python
command.main(
    ["command-name", "args", "go", "here"],
    standalone_mode=False,  # Disables exception handling and sys.exit()
)
```

Use `standalone_mode=False` when:
- Embedding Click commands in larger applications
- Writing tests
- Need custom exception handling

## Exception Types

**Base exceptions:**
- `ClickException`: Base for all user-facing errors
- `Abort`: Signal to abort execution

**Common subclasses:**
- `UsageError`: General usage error
- `BadParameter`: Specific parameter error (Click auto-augments with parameter name)
- `FileError`: File opening error from `FileType`

**All have `.show()` method to render error messages.**

## Exit Codes

**Standard exit codes:**
- `0`: Success or `--help` explicitly requested
- `1`: `Abort` exception
- `2`: Incorrect usage (help shown automatically)
- Custom: Set via `ClickException.exit_code`

**Help page exit codes:**
```python
@click.group()
def cli():
    pass

# User runs: cli --help
# Exit code: 0 (help requested)

# User runs: cli (with no subcommand)
# Exit code: 2 (incorrect usage, help shown automatically)
```

**Disable automatic help on error:**
```python
@click.group(no_args_is_help=False)
def cli():
    pass

# User runs: cli
# Shows error message instead of help, still exits with code 2
```

## Raising Exceptions

**Signal usage errors:**
```python
if not is_valid(value):
    raise click.UsageError("Invalid configuration")
```

**Signal parameter errors:**
```python
raise click.BadParameter("Must be positive", param_hint="--count")
```

**Abort execution:**
```python
if not click.confirm("Continue?"):
    raise click.Abort()
```

## Rules
- Treat exit code `0` as successful execution.
- Treat any exit code `> 0` as an error condition.
- Do not assume meaning of non-zero codes; they’re command- or OS-specific.
- Use exit codes as the primary machine-readable success signal.
- Prefer raising Click exceptions to trigger non-zero exits automatically.
- Call `ctx.exit(code)` to terminate early with a specific exit code.
- Avoid printing errors without setting a failing exit code.
- In tests, always assert `result.exit_code`, not just output.
- Design CLIs so scripts can rely on exit codes, not text parsing.
- Treat `ClickException` as the base for all user-facing errors; it has `.show()` and `.exit_code`.
- Use `ClickException.show()` to display error messages; it writes to stderr by default.
- Set `ClickException.exit_code` to control the exit code; defaults to 1.
- Use `ClickException.format_message()` to customize error message formatting; override in subclasses.
- Raise `UsageError` for general usage problems; Click shows usage line automatically.
- Raise `BadParameter` for parameter-specific errors; Click augments with parameter name.
- Set `param=` and `ctx=` on `BadParameter` for better error context; Click fills these automatically.
- Use `param_hint=` on `BadParameter` to manually specify which parameter failed.
- Raise `MissingParameter` when a required parameter is missing; subclass of `BadParameter`.
- Raise `NoSuchOption` when an unknown option is encountered; subclass of `UsageError`.
- Raise `BadOptionUsage` for option-specific usage errors; subclass of `UsageError`.
- Raise `BadArgumentUsage` for argument-specific usage errors; subclass of `UsageError`.
- Raise `FileError` when file operations fail; includes filename in error message.
- Set `filename=` on `FileError` to specify which file caused the error.
- Raise `Abort` to exit cleanly without showing an error message; prints "Aborted!" to stderr.
- Use `Exit` to exit with a specific code without an error message; rarely needed, prefer `ctx.exit()`.
- Assume `Command.main()` catches all exceptions in standalone mode; converts to exit codes.
- Set `standalone_mode=False` to disable exception handling; exceptions propagate normally.
- Expect `EOFError` and `KeyboardInterrupt` to be converted to `Abort` in standalone mode.
- Use `ctx.fail()` to raise `UsageError` with a message; cleaner than raising directly.
- Use `ctx.abort()` to raise `Abort`; cleaner than raising directly.
- Use `ctx.exit(code)` to exit with a specific code; bypasses exception handling.
- Treat `ctx.exit(0)` as successful termination; use for early exit on success.
- Call `exception.show(file=)` to write errors to a custom file; defaults to stderr.
- Override `ClickException.show()` in custom exceptions to control error display.
- Use `click.echo()` with `err=True` inside exception handlers; maintains Click's output handling.
- Assume exceptions are caught and displayed before the process exits; no need to print manually.
- Design custom exceptions to inherit from `ClickException` for consistent behavior.
- Use `UsageError` when the command line syntax is wrong; triggers usage display.
- Use `BadParameter` when a parameter value is invalid; more specific than `UsageError`.
- Raise exceptions early in callbacks or command functions; Click handles display and exit.
- Avoid catching `ClickException` unless you need custom handling; let Click manage it.
- Catch and re-raise as `ClickException` when wrapping non-Click errors for user display.
- Use `ParamType.fail()` in custom types instead of raising exceptions directly.
- Assume `fail()` raises `BadParameter` with proper context; it's the preferred method.
- Treat exit code 2 as "usage error"; reserved for incorrect command line usage.
- Treat exit code 1 as "general error"; used for `Abort` and most `ClickException` subclasses.
- Use custom exit codes by setting `exit_code` on `ClickException` instances or subclasses.
- Avoid exit codes 0, 1, 2 for custom errors; they have standard meanings.
- Test exception handling by checking `result.exception` in `CliRunner` tests.
- Use `result.exit_code` to verify the correct exit code was set; don't rely on output alone.
- Expect `--help` to exit with code 0; it's a successful operation, not an error.
- Expect missing required parameters to exit with code 2; it's a usage error.
- Design error messages to be actionable; tell users what to fix, not just what went wrong.
- Keep error messages concise; Click adds context like parameter names automatically.
- Use `ctx.obj` to pass error context between commands; useful for debugging information.
- Log detailed errors separately; Click exceptions are for user-facing messages only.

Full Reference:
https://click.palletsprojects.com/en/stable/exceptions/
https://click.palletsprojects.com/en/stable/command-line-reference/
https://click.palletsprojects.com/en/stable/api/#exceptions
