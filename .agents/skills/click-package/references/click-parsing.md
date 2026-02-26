# Click Parsing

**Rules:**
- Treat `OptionParser` as internal; Click manages parsing automatically.
- Avoid direct interaction with the parser; use decorators and parameter definitions instead.
- Rely on Click's built-in parsing logic; custom parsers are rarely needed.
- Assume parsing happens in `Command.main()` before callback invocation.
- Trust that eager parameters are processed before non-eager ones automatically.
- Expect options to be parsed in the order they appear on the command line.
- Assume arguments are positional and parsed in declaration order.
- Use `allow_interspersed_args=False` to require all options before arguments.
- Use `allow_extra_args=True` to collect unparsed arguments in `ctx.args`.
- Use `ignore_unknown_options=True` to skip unrecognized options instead of failing.
- Treat parsing errors as automatic failures; Click shows usage and exits.
- Assume `--` stops option parsing; everything after is treated as arguments.
- Expect short options to support clustering (e.g., `-abc` = `-a -b -c`).
- Assume long options support `--option=value` and `--option value` equally.
- Trust that boolean flags don't consume values; they set `True`/`False` directly.
- Use `is_flag=True` to force option to act as a flag even if not auto-detected.
- Expect `nargs=-1` to consume all remaining arguments for that parameter.
- Assume `multiple=True` allows the same option to appear multiple times.
- Treat parsing as separate from validation; parsing extracts values, callbacks validate.
- Rely on Click to handle `--help` eagerly; it exits before other processing.
- Assume completion happens during parsing; shell sends partial command line.
- Use `token_normalize_func` on Context to customize how tokens are normalized.
- Expect environment variables to be read during parsing if `envvar` is set.
- Assume defaults are applied after parsing if no value was provided.
- Trust that required parameters are validated after all parsing completes.

For full reference, see the "Parsing" section of the Click API docs:
https://click.palletsprojects.com/en/stable/api/#parsing
