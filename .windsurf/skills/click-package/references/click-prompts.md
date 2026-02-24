# Click User Input and Prompts

Use prompts to gather user input interactively when values aren't provided via command line.

## Option Prompts

**Prompt for missing option values:**
```python
@click.command()
@click.option('--name', prompt=True)
def hello(name):
    click.echo(f"Hello {name}!")
```

**Custom prompt text:**
```python
@click.option('--name', prompt='Your name please')
```

**Optional prompts (only prompt if flag given):**
```python
@click.option('--name', prompt=True, prompt_required=False, default="Default")
def hello(name):
    click.echo(f"Hello {name}!")
```
- Without flag: uses default, no prompt
- With `--name` flag: prompts for value

**Avoid:** Don't use `prompt=True` with `multiple=True`. Prompt manually in function instead.

## Manual Prompts

**Prompt for specific types:**
```python
value = click.prompt('Please enter a valid integer', type=int)
```

**Type inferred from default:**
```python
value = click.prompt('Please enter a number', default=42.0)  # accepts floats
```

## Confirmation Prompts

**Yes/no confirmation:**
```python
if click.confirm('Do you want to continue?'):
    click.echo('Well done!')
```

**Auto-abort on 'no':**
```python
click.confirm('Do you want to continue?', abort=True)
```

## Dynamic Defaults

**Use callable for dynamic defaults that still allow prompting:**
```python
import os

@click.option(
    "--username", prompt=True,
    default=lambda: os.environ.get("USER", ""),
    show_default="current user"
)
def hello(username):
    click.echo(f"Hello, {username}!")
```

This allows environment/config defaults while keeping interactive prompts active.

Full reference: https://click.palletsprojects.com/en/stable/prompts/
