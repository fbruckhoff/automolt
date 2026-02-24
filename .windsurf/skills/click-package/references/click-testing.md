# Testing Click Applications

# Setup & Basic Usage
- Use `click.testing.CliRunner` to invoke commands in tests; it simulates CLI invocation and provides integration testing.
- Create a runner instance with `runner = CliRunner()`; reuse it across tests if desired.
- Use `runner.invoke(command, args)` to run a command; returns a `Result` object.
- Pass `args` as a list of strings or a single string; Click parses it like the command line.

# Result Object
- Use `result.exit_code` to check the exit code; 0 is success, non-zero is error.
- Use `result.output` to get combined stdout/stderr output; it's a single string.
- Use `result.stdout` and `result.stderr` separately when `mix_stderr=False` on `invoke()`.
- Use `result.exception` to access any unhandled exception; `None` if command succeeded.
- Use `result.exc_info` to get the full exception traceback; useful for debugging.
- Check `result.output_bytes` for raw bytes output; useful for binary data tests.

# Invoke Options
- Use `input=` to simulate user input for prompts; separate multiple inputs with newlines.
- Use `env=` to set environment variables; pass as dict.
- Use `catch_exceptions=True` (default) to catch exceptions; set to `False` to let them propagate for debugging.
- Use `color=True/False` to force or suppress ANSI colors; useful for output testing.
- Set `terminal_width=` to control the terminal width; affects help formatting.
- Set `mix_stderr=False` to separate stdout and stderr; default is mixed.

# File & Environment Testing
- Use `runner.isolated_filesystem()` as a context manager for file operation tests; creates temp directory and cleans up on exit.
- Set `temp_dir=` on `isolated_filesystem()` to control where the temp dir is created.
- Use `runner.make_env()` to create an environment dict; includes Click-specific vars.

# Runner Configuration
- Set `charset=` on `CliRunner()` to control input/output encoding; defaults to UTF-8.
- Use `standalone_mode=False` on commands when testing to get return values; default is `True`.

# Testing Best Practices
- Test both success and failure cases; verify exit codes and error messages.
- Assert `result.exit_code == 0` for successful commands; 2 for usage errors, 1 for general errors.
- Assert expected output with `assert "expected text" in result.output`; use substring matching.
- Use `result.output.strip()` to remove trailing newlines; Click adds them automatically.
- Test subcommands by including subcommand names in `args`; e.g., `['subcommand', '--option']`.
- Test `--help` output by passing `['--help']` as args; verify exit code is 0 and help text is accurate.

# Parameter & Option Testing
- Test prompts by providing input; remember `confirmation_prompt` needs two inputs and `hide_input=True` prompts don't echo.
- Test required parameters by omitting them; verify error message and exit code 2.
- Test default values by omitting parameters; verify defaults are applied correctly.
- Test `multiple=True` options by passing the same option multiple times.
- Test `nargs=-1` arguments by passing multiple values; verify they're collected correctly.
- Test boolean flags by passing `--flag` and `--no-flag`; verify both work.
- Test `count=True` options by passing the option multiple times; verify count increments.
- Test `envvar=` parameters by setting environment variables; verify they're read correctly.

# Advanced Testing
- Test groups and chained commands with multiple subcommand names; verify callbacks run correctly.
- Test `ctx.obj` passing between commands; verify shared state works correctly.
- Test callbacks by verifying their side effects; check files created, state modified, etc.
- Test parameter validation with invalid values; verify error messages are helpful.
- Test deprecated parameters/commands; verify warning messages are shown.
- Test completion by setting the completion env var; e.g., `env={'_PROG_COMPLETE': 'bash_source'}`.
- Test with different terminal widths and color settings to verify formatting.

# General Guidelines
- Mock external dependencies; don't make real network calls or file operations.
- Use pytest fixtures to create reusable `CliRunner` instances; reduces boilerplate.
- Use descriptive test names; e.g., `test_command_with_invalid_option_shows_error`.
- Run tests in isolation; don't rely on test execution order.
- Test the happy path first, then edge cases and error conditions.
- Keep tests fast; avoid slow operations in command callbacks when testing.
- Avoid testing Click internals; test the CLI behavior as users would experience it.

Full reference:
https://click.palletsprojects.com/en/stable/testing/
https://click.palletsprojects.com/en/stable/api/#testing
