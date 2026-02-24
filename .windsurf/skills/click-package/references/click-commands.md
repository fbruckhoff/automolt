# Click Commands and Groups
Commands and Groups are the building blocks for Click applications. Command wraps a function to make it a CLI command. Group wraps Commands and Groups to create applications.

## Commands
By default the command is the function name with underscores replaced by dashes.
**Basic command:**
```python
@click.command()
@click.option('--count', default=1)
def hello(count):
    for x in range(count):
        click.echo("Hello!")
```
**Rename command:** Pass name as first argument to `@click.command('new-name')`
**Deprecate command:** Use `@click.command(deprecated=True)`

## Groups
A group wraps one or more commands in help pages.
**Basic group:**
```python
@click.group()
def greeting():
    click.echo('Starting greeting ...')
@greeting.command('say-hello')
@click.option('--count', default=1)
def hello(count):
    for x in range(count):
        click.echo("Hello!")
```
**Key patterns:**
- `invoke_without_command=True`: Group executes even without subcommand
- `@click.pass_context`: Access context object with `ctx.invoked_subcommand`
- Lazy attachment: Use `cli.add_command(command)` to register commands later, if needed
- Arbitrary nesting: Groups can contain groups
**Parameter scoping:**
- Group parameters belong only to that group, not nested commands
- Command parameters must come after the command name
- `--help` before command name shows group help, not command help

## Context Object
**Auto environment variables:**
```python
if __name__ == '__main__':
    greet(auto_envvar_prefix='GREETER')
```
Creates `GREETER_USERNAME` env var for `--username` option.
For groups: `PREFIX_COMMAND_VARIABLE` (e.g., `WEB_RUN_SERVER_HOST`)

**Global context access:**
```python
ctx = click.get_current_context()
source = ctx.get_parameter_source("port")  # COMMANDLINE, ENVIRONMENT, or DEFAULT
```
Assume a new Context is created per command invocation; never reuse across runs.

# Rules

## Command Basics
- Treat `@click.command()` as a transformer; the decorated function becomes a `Command` object, not a callable.
- Use `@click.group()` only when subcommands are real; don't over-group single commands.
- Assume command names are auto-derived from function names with underscores replaced by dashes.
- Override the command name by passing `name=` to the decorator; use sparingly for UX clarity.
- Use `callback=` to attach a function to a command after creation; rarely needed with decorators.
- Set `params=` to register options/arguments programmatically; prefer decorators for readability.

## Help and Documentation
- Use `help=` to set command help text; prefer docstrings for multi-line help.
- Use `epilog=` for text after options in help; useful for examples or additional notes.
- Use `short_help=` to customize command listing in group help; auto-truncates from `help=` by default.
- Set `add_help_option=False` to suppress `--help`; rarely needed except for custom help handling.
- Set `no_args_is_help=True` to show help when no arguments given; useful for commands requiring input.
- Set `no_args_is_help=None` on groups to default to opposite of `invoke_without_command`.

## Command Behavior
- Set `hidden=True` to hide commands from help output; useful for deprecated or internal commands.
- Set `deprecated=True` or `deprecated="message"` to mark commands as deprecated; shows warning on use.
- Use `context_settings=` to pass defaults to the Context; applies to this command and children.
- Set `allow_extra_args=True` to collect unparsed args in `ctx.args`; useful for pass-through commands.
- Set `allow_interspersed_args=False` to require options before arguments; stricter parsing.
- Set `ignore_unknown_options=True` to skip unrecognized options; useful for wrapper commands.

## Groups
- Use `invoke_without_command=True` on groups to run group callback even without subcommand.
- Use `chain=True` on groups to allow multiple subcommands in one invocation; advanced feature.
- Use `result_callback=` on groups to process subcommand results; receives return value(s).
- Use `commands=` to pass a dict/list of commands to a group; prefer decorators for clarity.
- Set `command_class=` on groups to customize the default Command class for subcommands.
- Set `group_class=` on groups to customize the default Group class for subgroups.
- Set `group_class=type` to make subgroups inherit the parent's class; useful for custom groups.

## Registering Commands
- Use `add_command()` to register commands programmatically; useful for dynamic command loading.
- Use `@group.command()` decorator to attach commands to groups; cleaner than `add_command()`.
- Use `@group.group()` decorator to attach subgroups to groups; supports arbitrary nesting.
- Override `Group.get_command()` to implement custom command resolution or aliases.
- Override `Group.list_commands()` to control command order or filter commands in help.
- Use `Group.commands` dict to access registered commands by name; read-only access preferred.

## Command Collections
- Use `CommandCollection` to merge multiple groups into one flat namespace; useful for plugins.
- Set `sources=` on `CommandCollection` to specify groups to search; order matters for precedence.
- Use `add_source()` to add groups to a `CommandCollection` after creation.
- Treat `CommandCollection` as read-only; it doesn't invoke source group callbacks.

## Programmatic Invocation
- Use `Command.main()` to invoke a command programmatically; handles parsing and context creation.
- Set `standalone_mode=False` on `main()` to return values instead of exiting; useful for testing.
- Set `prog_name=` on `main()` to override the program name in help; defaults to `sys.argv[0]`.
- Set `args=` on `main()` to pass custom arguments; defaults to `sys.argv[1:]`.
- Use `Command.invoke()` to call a command with an existing context; lower-level than `main()`.
- Use `Command.make_context()` to create a context without invoking; useful for introspection.
- Use `Command.parse_args()` via `make_context()` to parse arguments; rarely called directly.

## Help Generation
- Use `Command.get_help()` to retrieve formatted help text; useful for custom help commands.
- Use `Command.get_short_help_str()` to get truncated help for listings; respects `short_help=`.
- Use `Command.format_help()` to write help to a formatter; low-level help generation.
- Use `Command.get_usage()` to get the usage line; useful for error messages.
- Override `Command.format_usage()` to customize usage line formatting; rarely needed.
- Override `Command.format_help_text()` to customize help text formatting; rarely needed.
- Override `Command.format_options()` to customize option formatting in help; rarely needed.
- Override `Command.format_epilog()` to customize epilog formatting; rarely needed.

## Parameters and Completion
- Use `Command.get_params()` to access the command's parameters; returns list of `Parameter` objects.
- Use `Command.shell_complete()` to implement custom completion; returns `CompletionItem` list.

## Callbacks and Error Handling
- Treat command callbacks as regular functions; they receive parsed parameter values as kwargs.
- Assume callbacks are invoked after all parsing and validation; parameters are already converted.
- Return values from callbacks to pass data to result callbacks in groups; useful for pipelines.
- Raise `click.Abort` to exit cleanly without error message; useful for user cancellation.
- Raise `click.ClickException` for user-facing errors; shows message and exits with code 1.
- Raise `click.UsageError` for parameter validation errors; shows usage and error message.
- Use `ctx.fail()` to raise `UsageError` with a message; cleaner than raising directly.
- Use `ctx.exit()` to exit with a specific code; bypasses exception handling.
- Use `ctx.abort()` to raise `Abort`; cleaner than raising directly.

## Architecture Best Practices
- Model Git-style CLIs as a root group with subcommands, not flat commands.
- Use the root command to parse global config and environment defaults.
- Initialize shared state exactly once in the root command.
- Avoid globals; everything subcommands need should live on `ctx.obj`.
- Assume subcommands depend on `ctx.obj`; design them to fail clearly if missing.
- Attach subcommands to a group; inherit state via Context, not globals.
- Prefer `make_pass_decorator(Type)` to stay robust in interleaved command trees.
- Enable `ensure=True` when commands must run standalone.
- Design child commands to depend on behavior, not context structure.
- Prefer explicit object passing over re-reading options in subcommands.

## Lazy Loading
- Use lazy-loaded subcommands only for large or slow-import CLIs.
- Always expose lazy commands in `list_commands()` for `--help`.
- Guard against non-Command returns; fail loudly.
- Run `--help` on every subcommand in tests to force-load them.
- Prefer eager imports if command behavior depends on shared globals.

## Command Aliases
- Implement command aliases by overriding `Group.get_command()`.
- Keep aliases out of `list_commands()` to avoid help clutter.
- Resolve aliases at runtime, not at definition time.
- Use prefix matching only when the result is unambiguous.
- Fail fast on ambiguous prefixes; never guess.
- Treat aliases as UX sugar, not API guarantees.
- Prefer explicit aliases over auto-shortening in large CLIs.
- Ensure alias resolution happens before lazy loading logic.
- Keep alias logic side-effect free; resolution should be cheap.
- Test collisions as commands grow; prefixes become unstable.

For full reference, see:
https://click.palletsprojects.com/en/stable/api/#commands
https://click.palletsprojects.com/en/stable/commands-and-groups/
https://click.palletsprojects.com/en/stable/complex/
https://click.palletsprojects.com/en/stable/extending-click/#id3
