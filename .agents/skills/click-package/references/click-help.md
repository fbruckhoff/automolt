# Click Help and Documentation

Click automatically generates help pages from docstrings and help parameters.

## Basic Help Text

**Command help from docstring:**
```python
@click.command()
@click.option('--count', default=1, help='number of greetings')
def hello(count):
    """This script prints hello and a name."""
    click.echo(f"Hello!")
```

**Arguments:** Document in command docstring, not with `help=` parameter
```python
@click.command()
@click.argument('filename')
def touch(filename):
    """Print FILENAME.

    FILENAME is the name of the file to check.
    """
    click.echo(filename)
```

## Controlling Help Display

**Show/hide defaults:**
- `show_default=True`: Display default value in help
- `show_default=False`: Hide default value
- Boolean flags with `default=False` hide default even if `show_default=True`

**Show environment variables:**
```python
@click.option('--username', envvar='USERNAME', show_envvar=True)
```

**Short help for subcommands:**
```python
@cli.command('init', short_help='init the repo')
def init():
    """Initializes the repository."""
```
Auto-generated from first sentence of docstring if not provided.

**Epilog for usage examples:**
```python
@click.command(epilog='See https://example.com for more details')
def init():
    """Initializes the repository."""
```

## Formatting Help Text

**Preserve line breaks with `\b`:**
```python
def cli():
    """First paragraph.

    \b
    This is
    a paragraph
    without rewrapping.
    """
```

**Truncate help text with `\f`:**
```python
def cli():
    """User-visible help.
    \f

    Internal notes not shown in help.
    """
```

**Custom meta variables:**
```python
@click.command(options_metavar='[[options]]')
@click.option('--count', metavar='<int>')
@click.argument('name', metavar='<name>')
def hello(name, count):
    """Prints hello <name> <count> times."""
```

## Customizing Help Options

**Change help flags:**
```python
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

@click.command(context_settings=CONTEXT_SETTINGS)
def cli():
    pass
```

**Control max width:**
```python
cli(max_content_width=120)
```

Full reference: https://click.palletsprojects.com/en/stable/documentation/
