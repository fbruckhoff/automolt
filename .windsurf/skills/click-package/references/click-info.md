**About the Click Package**

Click is a Python package for creating composable CLIs with minimal code. Highly configurable with sensible defaults.
- arbitrary nesting of commands
- automatic help page generation
- supports lazy loading of subcommands at runtime

Example:

```python
import click

@click.command()
@click.option('--count', default=1, help='Number of greetings.')
@click.option('--name', prompt='Your name',
              help='The person to greet.')
def hello(count, name):
    """Simple program that greets NAME for a total of COUNT times."""
    for x in range(count):
        click.echo(f"Hello {name}!")

if __name__ == '__main__':
    hello()
```

You can get the library directly from PyPI:

```bash
pip install click
```

**Getting Started**
https://click.palletsprojects.com/en/stable/quickstart/
https://dev.to/shrsv/build-easy-to-use-clis-in-python-with-click-23ah
