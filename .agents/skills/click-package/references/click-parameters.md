# Click Parameters

## Parameter Types
**Click Package Parameter Types**
- Click uses `type=` to validate & convert params; improves help output
- Types apply to both options and arguments
- `Choice`: restricts to list of values; returns original choice object
- `Choice` supports enums; case-insensitive with `case_sensitive=False`
- Invalid choice raises error with list of valid options in help
- `IntRange` / `FloatRange`: enforce min/max; support open bounds & clamp
- Clamp mode sets out-of-range values to nearest boundary instead of error
- Built-in types: STRING (str), INT, FLOAT, BOOL, UUID, Choice, DateTime
- `BOOL`: accepts yes/no, true/false, 1/0, on/off variants
- `DateTime`: parses ISO-like formats into datetime objects
- `File`: opens file (text/binary); handles -, lazy/atomic modes
- `Path`: validates file/dir existence, permissions; returns path string
- `Path` supports checks: exists, readable, writable, executable, etc.
- Custom types: subclass `ParamType` and override `convert()` method
- In `convert()`, handle strings → desired type; call `fail()` on error
- Custom types should accept already-converted values (e.g. defaults)
More: https://click.palletsprojects.com/en/stable/parameter-types/
## Options
**Overview:** https://click.palletsprojects.com/en/stable/parameters/
**Detailed patterns:** https://click.palletsprojects.com/en/stable/options/
(Options, decorators, defaults, multi-value, tuples, counting, boolean flags, environment variables, prefix characters, optional values)
## Arguments
**Prefer options over arguments**
Use positional arguments sparingly and only when required (prefer options):
- Multiple positional arguments make CLI invocations confusing
- Optional or variable-length arguments are hard to reason about (parser fills left-to-right, non-obvious to users)
- Use positional arguments only for: subcommand names in groups, files to act on, or source→destination pairs
Arguments are positional and required by default.
**Key patterns:**
- `nargs=-1`: Variadic arguments (arbitrary number)
- `envvar`: Read from environment variables
- `--` separator: Handle files that look like options (e.g., `-foo.txt`)
- `ignore_unknown_options=True`: Alternative to `--` separator
**Basic example:**
```python
@click.command()
@click.argument('filename')
def touch(filename):
    click.echo(filename)
```
**Multiple arguments:**
```python
@click.argument('src', nargs=1)
@click.argument('dsts', nargs=-1)
def copy(src, dsts):
    for dst in dsts:
        click.echo(f"Copy {src} to {dst}")
```


# Rules

## Parameter Basics
- Treat parameters as the bridge between CLI strings and Python values; they parse, convert, and validate.
- Use `@click.option()` for optional named parameters; use `@click.argument()` for required positional ones.
- Prefer options over arguments; arguments are harder to document and less discoverable.
- Use arguments only for truly positional data: filenames, source/destination pairs, or subcommand names.
- Assume parameter decorators attach in order; they're processed bottom-to-top in the decorator stack.
- Treat `Option` as a subclass of `Parameter` with additional features; `Argument` is simpler with fewer features.
- Assume options can appear anywhere in the command line; arguments are positional.
- Use `--` to stop option parsing; everything after is treated as arguments.

## Naming
- Use `param_decls` to specify parameter names; options use `--name`, arguments use bare names.
- Use single-dash short options (`-n`) and double-dash long options (`--name`) for options.
- Assume Click auto-derives Python parameter names from the longest option/argument name.
- Use underscores in Python names; Click converts them to dashes in CLI names automatically.
- Override the Python name with `name=` in the decorator; rarely needed.

## Type Conversion and Defaults
- Use `type=` to specify conversion; Click converts strings to the target type automatically.
- Assume `type=str` by default; specify other types explicitly for conversion and validation.
- Use `default=` to provide a default value; parameters without defaults are required (except options).
- Use a callable for `default=` to compute defaults lazily; called without arguments when needed.
- Use `Parameter.get_default()` to retrieve the default value; handles callable defaults.
- Use `Parameter.type_cast_value()` to manually convert a value; applies type conversion logic.

## Required Parameters
- Use `required=True` on options to make them mandatory; arguments are required by default.
- Set `required=False` on arguments to make them optional; rarely used, prefer options.
- Assume parameter values are validated after all parsing; required checks happen at the end.

## Multiple Values
- Use `nargs=` to control how many values are consumed; default is 1 for single values.
- Set `nargs=2` (or any N) to consume exactly N values; returns a tuple.
- Set `nargs=-1` to consume all remaining values; returns a tuple of arbitrary length.
- Use `multiple=True` to allow the same option multiple times; returns a tuple of values.
- Combine `multiple=True` with `nargs>1` to get a tuple of tuples; each invocation is one tuple.

## Flags and Counters
- Use `is_flag=True` to make an option a boolean flag; no value consumed, sets True when present.
- Use `flag_value=` to specify what value a flag sets; auto-detects from `--flag/--no-flag` syntax.
- Use `--flag/--no-flag` syntax to create paired boolean flags; Click handles both automatically.
- Use `count=True` to make an option increment a counter; each occurrence adds 1.

## Environment Variables
- Use `envvar=` to read from environment variables; string or list of strings to try in order.
- Use `envvar_list_splitter=` to control how environment variable lists split; default is whitespace.
- Use `show_envvar=True` to display the environment variable in help; hidden by default.
- Use `allow_from_autoenv=True` on options to read from auto-generated env vars; requires `auto_envvar_prefix`.
- Assume auto-env vars are named `PREFIX_OPTION_NAME` in uppercase; underscores separate words.

## Prompting
- Use `prompt=True` to interactively prompt for missing values; useful for required sensitive data.
- Set `prompt="Custom prompt"` to customize the prompt message; defaults to option name.
- Use `hide_input=True` with `prompt=True` for password entry; input is not echoed.
- Use `confirmation_prompt=True` to prompt twice and verify match; useful for passwords.
- Set `prompt_required=False` to only prompt when the option is given without a value.
- Set `show_choices=True` on `Choice` types to list valid choices in the prompt.

## Callbacks
- Use `callback=` to validate or transform values after type conversion; called as `f(ctx, param, value)`.
- Assume callbacks are invoked in parameter order; earlier callbacks run before later ones.
- Return the (possibly modified) value from callbacks; it becomes the final parameter value.
- Use `expose_value=False` to hide the parameter from the command function; useful for side-effect params.
- Use `is_eager=True` to process parameters before others; useful for `--version` or `--help`.
- Combine `is_eager=True` with `expose_value=False` for parameters that exit early.

## Help and Documentation
- Use `help=` to document the parameter; shown in help output.
- Use `metavar=` to customize how the parameter appears in help; defaults to type-based metavar.
- Set `show_default=True` to display the default value in help; hidden by default for options.
- Set `show_default="custom"` to show a custom default description instead of the actual value.
- Use `hidden=True` to hide parameters from help output; useful for deprecated parameters.
- Set `deprecated=True` or `deprecated="message"` to mark parameters as deprecated; shows warning.
- Treat deprecated parameters as non-required; Click raises `ValueError` if `required=True` and `deprecated=True`.

## Shell Completion
- Use `shell_complete=` to provide custom completion; takes `ctx, param, incomplete` and returns list.

## Advanced Usage
- Use `ctx.params` to access all parsed parameter values; available in callbacks and command functions.
- Use `Parameter.get_error_hint()` to get a string representation for error messages.
- Use `Parameter.to_info_dict()` to get parameter metadata; useful for documentation generation.

For full reference, see the "Parameters" section of the Click API docs:
https://click.palletsprojects.com/en/stable/api/#parameters

Also see: https://click.palletsprojects.com/en/stable/arguments/
