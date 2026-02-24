# Click File Handling

Use Click's built-in types for robust file and path handling.

## File Type (I/O Operations)

**Use `click.File()` when reading/writing file contents:**
```python
@click.command()
@click.argument('input', type=click.File('rb'))
@click.argument('output', type=click.File('wb'))
def inout(input, output):
    """Copy contents of INPUT to OUTPUT."""
    while True:
        chunk = input.read(1024)
        if not chunk:
            break
        output.write(chunk)
```

**Key features:**
- Supports `-` for stdin (reading) and stdout (writing)
- Handles str and bytes correctly
- `'r'` = text mode, `'rb'` = binary mode
- `'w'` = write mode, `'a'` = append mode

**Opening behavior:**
- **Stdin/stdout and read mode:** Opens immediately (fails fast)
- **Write mode:** Opens lazily on first I/O operation
- Use `lazy=True` to defer all file opening until first I/O
- Use `atomic=True` for atomic writes (writes to temp file, then moves)

**When to use lazy mode:**
- Minimizes resource handling issues
- Prevents accidentally emptying files
- Use with `LazyFile.close_intelligently()` for manual prompts

## Path Type (Validation)

**Use `click.Path()` when validating paths without reading contents:**
```python
@click.command()
@click.argument('filename', type=click.Path(exists=True))
def touch(filename):
    """Print FILENAME if the file exists."""
    click.echo(click.format_filename(filename))
```

**Validation options:**
- `exists=True`: Path must exist
- `file_okay=True/False`: Accept/reject files
- `dir_okay=True/False`: Accept/reject directories
- `readable=True`: Path must be readable
- `writable=True`: Path must be writable
- `executable=True`: Path must be executable
- `resolve_path=True`: Return absolute path

**Returns:** Path string (not file object)

## Choosing Between File and Path

**Use `File`:**
- Reading/writing file contents
- Need stdin/stdout support (-)
- Want automatic file handling

**Use `Path`:**
- Validating paths only
- Opening files manually later
- Checking permissions/existence
- Working with directories
- Need path string for other operations

**Format filenames nicely:**
```python
click.echo(click.format_filename(filename))
```
Handles undecodable bytes properly in error messages.

Full reference: https://click.palletsprojects.com/en/stable/handling-files/
