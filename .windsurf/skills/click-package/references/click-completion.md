# Click Shell Completion

Click provides tab completion for command names, option names, and parameter values in Bash, Zsh, and Fish.

## Requirements

**Shell completion only works when:**
- Script is installed via entry points (not run with `python script.py`)
- User has configured their shell with completion script

## User Setup Instructions

Provide these instructions to users (replace `foo-bar` with your program name):

**Bash (~/.bashrc):**
```bash
eval "$(_FOO_BAR_COMPLETE=bash_source foo-bar)"
```

**Zsh (~/.zshrc):**
```bash
eval "$(_FOO_BAR_COMPLETE=zsh_source foo-bar)"
```

**Fish (~/.config/fish/completions/foo-bar.fish):**
```bash
_FOO_BAR_COMPLETE=fish_source foo-bar | source
```

**For faster shell startup, pre-generate the script:**
```bash
_FOO_BAR_COMPLETE=bash_source foo-bar > ~/.foo-bar-complete.bash
```
Then source it in shell config: `. ~/.foo-bar-complete.bash`

## Custom Completions

**Custom parameter type completion:**
```python
class EnvVarType(ParamType):
    name = "envvar"

    def shell_complete(self, ctx, param, incomplete):
        return [
            CompletionItem(name)
            for name in os.environ if name.startswith(incomplete)
        ]

@click.command()
@click.option("--ev", type=EnvVarType())
def cli(ev):
    click.echo(os.environ[ev])
```

**Custom completion for specific parameter:**
```python
def complete_env_vars(ctx, param, incomplete):
    return [k for k in os.environ if k.startswith(incomplete)]

@click.command()
@click.argument("name", shell_complete=complete_env_vars)
def cli(name):
    click.echo(f"Value: {os.environ[name]}")
```

**Function signature:**
- `ctx`: Current command context
- `param`: Parameter requesting completion
- `incomplete`: Partial word being completed (may be empty string)
- **Returns:** List of `CompletionItem` objects or list of strings

## What Gets Completed

- Command names
- Option names (only after `-` or `--` is typed)
- Choice parameter values
- File and path parameter values
- Custom completions via `shell_complete`
- Hidden commands/options are not shown

## Adding Support for Other Shells

Check PyPI first - someone may have already added support. Implementation requires:
1. Subclass `ShellComplete`
2. Register with `@add_completion_class`
3. Implement `get_completion_args()` - parse shell's completion context
4. Implement `format_completion()` - format items for shell
5. Set `source_template` - completion script for shell

See Click source for built-in implementations (Bash, Zsh, Fish) as reference.

# Rules
- Assume shell completion only works when the CLI is installed via entry points; not with `python script.py`.
- Require users to configure their shell with the completion script; it's not automatic.
- Use environment variable `_<PROG>_COMPLETE` to trigger completion script generation.
- Set `_<PROG>_COMPLETE=bash_source` to generate Bash completion script.
- Set `_<PROG>_COMPLETE=zsh_source` to generate Zsh completion script.
- Set `_<PROG>_COMPLETE=fish_source` to generate Fish completion script.
- Use uppercase program name with underscores in the env var; dashes become underscores.
- Recommend pre-generating completion scripts for faster shell startup; eval is slower.
- Use `CompletionItem` for rich completions with help text; plain strings work too.
- Set `CompletionItem.value` to the completion value; what gets inserted.
- Set `CompletionItem.help` to show help text next to the completion; shell-dependent support.
- Set `CompletionItem.type` to hint the completion type; values: `plain`, `dir`, `file`.
- Return list of `CompletionItem` or list of strings from `shell_complete()` functions.
- Implement `ParamType.shell_complete()` for type-level completions; applies to all params of that type.
- Use `shell_complete=` parameter to provide param-specific completions; overrides type completion.
- Receive `ctx`, `param`, `incomplete` in completion functions; `incomplete` is the partial word.
- Treat `incomplete` as potentially empty string; user may tab with no input yet.
- Filter completions by `incomplete` prefix; shells don't filter automatically.
- Use `ctx` to access command state and other parameters; useful for context-aware completions.
- Use `param` to identify which parameter is being completed; rarely needed.
- Return empty list when no completions are available; don't return None.
- Assume Click completes command names, option names, and parameter values automatically.
- Expect option name completion only after `-` or `--` is typed; not in other contexts.
- Use `Choice` type for automatic completion of valid choices; no custom code needed.
- Use `File` or `Path` types for automatic file/directory completion; shell handles it.
- Set `hidden=True` on commands/options to exclude them from completion; useful for deprecated items.
- Assume completion happens in a subprocess; avoid expensive operations in completion functions.
- Keep completion functions fast; slow completions make the shell feel unresponsive.
- Avoid network calls or heavy I/O in completion functions; use caching if necessary.
- Return completions in a sensible order; most relevant first if possible.
- Use `ctx.params` to access already-parsed parameters; useful for dependent completions.
- Implement `Command.shell_complete()` for command-level custom completions; rarely needed.
- Override `Group.shell_complete()` to customize subcommand completion; rarely needed.
- Use `get_completion()` to manually trigger completion; useful for testing.
- Set `complete_var=` on `Command.main()` to customize the completion env var name.
- Subclass `ShellComplete` to add support for new shells; register with `@add_completion_class`.
- Implement `ShellComplete.get_completion_args()` to parse shell-specific completion context.
- Implement `ShellComplete.format_completion()` to format completions for the shell.
- Set `ShellComplete.source_template` to the shell script template for activation.
- Use `ShellComplete.source()` to generate the activation script; called by Click automatically.
- Test completions by setting the env var and running the command; check generated script.
- Document completion setup in your CLI's README or help; users need to configure it.
- Provide copy-paste instructions for each supported shell; make setup easy.
- Consider adding a `--install-completion` command to automate setup; user convenience.
- Warn users that completion requires shell restart or re-sourcing config; common gotcha.
- Assume Bash, Zsh, and Fish are supported by default; other shells need custom implementation.
- Use `click.shell_completion.add_completion_class()` to register custom shell support.
- Expect completion to work with chained commands if `chain=True`; completes next command.
- Assume completion respects `allow_interspersed_args` and other parsing settings.
- Use completion to improve UX for complex CLIs; reduces need to remember all options.
- Test completion with real shells; behavior varies between Bash, Zsh, and Fish.
- Avoid returning too many completions; overwhelming users defeats the purpose.

Full Reference:
https://click.palletsprojects.com/en/stable/shell-completion
https://click.palletsprojects.com/en/stable/api/#shell-completion/
