# Click Types

**Rules:**
- Use built-in types for common conversions; avoid custom types unless necessary.
- Treat `ParamType.convert()` as the single conversion point; it must handle both strings and already-converted values.
- Ensure `convert()` works when `ctx` and `param` are `None`; this occurs during prompt input.
- Use `click.File()` for file handles, `click.Path()` for path validation without opening.
- Prefer `click.Path()` over `click.File()` when you only need the path string.
- Use `click.Choice()` for fixed sets; it handles case-insensitivity and normalization.
- Use `click.IntRange()` or `click.FloatRange()` for bounded numeric values.
- Set `clamp=True` on ranges to auto-correct out-of-bounds values instead of failing.
- Use `click.DateTime()` for date parsing; provide format strings in order of preference.
- Use `click.Tuple()` only with fixed `nargs`; each position gets its own type.
- Implement `ParamType.shell_complete()` for custom completion; return `CompletionItem` list.
- Call `fail()` with descriptive messages instead of raising exceptions in `convert()`.
- Set `ParamType.envvar_list_splitter` to control how environment variable lists split.
- Use `None` as envvar splitter for whitespace splitting; use specific chars for custom splitting.
- For `click.File()`, use `lazy=True` to defer opening until first IO; default is lazy for write, eager for read.
- Use `atomic=True` on `click.File()` for safe overwrites; writes to temp file then moves.
- For `click.Path()`, use `exists=True` to require the path exists; further checks are skipped if it doesn't.
- Use `resolve_path=True` to make paths absolute and resolve symlinks; `~` is not expanded.
- Use `allow_dash=True` on `click.Path()` to accept `-` as stdin/stdout indicator.
- Set `path_type=pathlib.Path` to return Path objects instead of strings.
- For `click.Choice()`, override `normalize_choice()` for custom mapping logic.
- Treat choice normalization as case-folding by default when `case_sensitive=False`.
- Ensure custom `ParamType` has a descriptive `name` class attribute.
- Return `None` when calling a type with `None`; this is the missing value sentinel.
- Use `get_metavar()` to customize how the type appears in help text.
- Use `get_missing_message()` to provide hints when a required value is missing.

For full reference, see the "Types" section of the Click API docs:
https://click.palletsprojects.com/en/stable/api/#types
