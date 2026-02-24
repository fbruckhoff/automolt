# Click Advanced Groups and Context Capabilities

# Sharing State Between Commands

**Use `ctx.obj` to pass data from parent to child commands:**
```python
@click.group()
@click.option('--debug/--no-debug', default=False)
@click.pass_context
def cli(ctx, debug):
    ctx.ensure_object(dict)
    ctx.obj['DEBUG'] = debug

@cli.command()
@click.pass_context
def sync(ctx):
    click.echo(f"Debug is {'on' if ctx.obj['DEBUG'] else 'off'}")
```

- Store shared configuration or state in `ctx.obj` (dict)
- Use `@click.pass_context` decorator to access context
- Access parent context via `ctx.parent` if needed

## Command Chaining

**Use chaining when users need to run multiple subcommands in sequence:**
```python
@click.group(chain=True)
def cli():
    pass

@cli.command('validate')
def validate():
    click.echo('validate')

@cli.command('build')
def build():
    click.echo('build')
```

Usage: `my-app validate build`

**Restrictions to note:**
- Only last command can use `nargs=-1`
- Cannot nest groups below chain group
- Options must come before arguments for each command

## Command Pipelines

**Use pipelines when commands should process and transform data sequentially.**

**For simple data passing, use shared context:**
```python
pass_ns = click.make_pass_decorator(dict, ensure=True)

@click.group(chain=True)
@pass_ns
def cli(ns):
    ns["data"] = []
```

**For complex transformations, use result callbacks:**
```python
@click.group(chain=True, invoke_without_command=True)
def cli():
    pass

@cli.result_callback()
def process_pipeline(results):
    # Process list of return values from chained commands
    for result in results:
        click.echo(result)

@cli.command("upper")
def make_uppercase():
    return lambda text: text.upper()
```

**Important:** Click closes files after callbacks. For pipelines processing files, use `open_file()` instead of `File` type.

## Loading Defaults from Configuration

**Use `default_map` to override defaults from config files:**
```python
@click.group()
def cli():
    pass

@cli.command()
@click.option('--port', default=8000)
def runserver(port):
    click.echo(f"Serving on http://127.0.0.1:{port}/")

if __name__ == '__main__':
    cli(default_map={'runserver': {'port': 5000}})
```

Or set via `context_settings` in decorator for persistent config.

## Custom Decorators

**Create custom decorators to simplify common patterns:**

Use `@click.pass_context` and `ctx.invoke()` to build decorators that pass custom objects to commands. Useful for dependency injection or state management patterns.


## Custom Groups
- You may customize CLI behavior if needed, by subclassing `click.Group`.
- Override `get_command()` to control resolution or add dynamic commands.
- Override `list_commands()` to control what appears in help/completion.
- Use custom groups for plugin systems or dynamic command discovery.
- Combine with lazy loading to minimize startup cost.
- Keep overridden methods fast; they run often during help/completion.
- Treat custom groups as the central point for CLI-wide behaviors.
- Avoid side effects in `get_command()`; only resolve or return commands.
- Use context and object passing normally; custom groups don’t break it.
- Test with both `--help` and completion to verify lazy or dynamic behavior.


Full reference:
https://click.palletsprojects.com/en/stable/commands/
https://click.palletsprojects.com/en/stable/extending-click/#id2
