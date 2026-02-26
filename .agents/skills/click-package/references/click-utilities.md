# Click Utilities

Click provides utilities for common CLI tasks beyond argument parsing.

## Output
**Use `click.echo()` instead of `print()`:**
```python
click.echo('Hello World!')
click.echo('Error!', err=True)  # Write to stderr
click.echo(b'\xe2\x98\x83', nl=False)  # Binary data, no newline
```
**Benefits:**
- Works consistently across terminals
- Supports Unicode on Windows console
- Handles both text and binary data
- Auto-strips ANSI codes when not a terminal
**Styled output:**
```python
click.secho('Hello World!', fg='green')
click.secho('ATTENTION', fg='white', bg='red', bold=True)
```
## Paging Long Output
**Use `click.echo_via_pager()` for long text:**
```python
@click.command()
def less():
    click.echo_via_pager("\n".join(f"Line {idx}" for idx in range(200)))
```
**For generated content, use generator:**
```python
def _generate_output():
    for idx in range(50000):
        yield f"Line {idx}\n"
click.echo_via_pager(_generate_output())
```
## Interactive Input
**Get single character:**
```python
click.echo('Continue? [yn] ', nl=False)
c = click.getchar()  # Reads from terminal, even if stdin is pipe
if c == 'y':
    click.echo('Proceeding...')
```
**Pause for keypress:**
```python
click.pause()  # Waits for any key; NOP if not interactive
```
**Launch editor for multi-line input:**
```python
message = click.edit('\n\n# Enter message above')
if message is not None:
    # User saved the file
    process(message)
```
**Edit specific file:**
```python
click.edit(filename='/path/to/file.txt')
```
## Progress Bars
**Wrap iterable with progress bar:**
```python
with click.progressbar(all_users, label='Processing users') as bar:
    for user in bar:
        modify_user(user)
```
**For unknown length, provide explicit length:**
```python
with click.progressbar(items, length=total_count) as bar:
    for item in bar:
        process(item)
```
**Manual updates for irregular progress:**
```python
with click.progressbar(length=total_size, label='Extracting') as bar:
    for archive in zip_file:
        archive.extract()
        bar.update(archive.size)
```
## File Operations
**Open files intelligently (handles stdin/stdout):**
```python
with click.open_file(filename, 'w') as f:
    f.write('Hello World!\n')
```
Use `-` for stdin/stdout. Prevents closing standard streams.
**Get platform-appropriate app config directory:**
```python
config_dir = click.get_app_dir('MyApp')
config_file = os.path.join(config_dir, 'config.ini')
```
**Format filenames safely (handles non-Unicode):**
```python
click.echo(f"Path: {click.format_filename(filename)}")
```
## Other Utilities
**Clear screen:**
```python
click.clear()
```
**Launch applications:**
```python
click.launch("https://example.com")  # Opens in browser
click.launch("/path/to/file.txt", locate=True)  # Opens file manager
```
**Get consistent streams:**
```python
stdin_text = click.get_text_stream('stdin')
stdout_binary = click.get_binary_stream('stdout')
```

# Rules

## Echo and Output
- Use `click.echo()` instead of `print()`; it handles encoding, Unicode, binary data, auto-flushes, and strips ANSI when not a TTY.
- Use `err=True` on `click.echo()` to write to stderr instead of stdout.
- Use `nl=False` to suppress the trailing newline in `click.echo()`.
- Use `color=True/False` to force or suppress ANSI styling regardless of TTY detection.

## Styling
- Use `click.secho()` to combine styling and output in one call; it's `echo(style(...))`.
- Treat bytes passed to `click.secho()` as unstyled; only strings get styled.
- Use `click.style()` for inline styling; set `reset=False` to compose styles without auto-reset.
- Use `click.unstyle()` to strip ANSI codes from strings; rarely needed since `echo()` does this.
- Prefer named colors (`'red'`, `'green'`) over RGB tuples unless precise color is required.
- Use `bright_*` color names for bold/bright variants; don't rely on `bold=True` for color intensity.

## Paging
- Use `click.echo_via_pager()` for output longer than a screen; it invokes the system pager.
- Pass a generator to `click.echo_via_pager()` for lazy evaluation of large output.

## Interactive Input
- Use `click.prompt()` for interactive input with type conversion and validation.
- Set `default=` on `click.prompt()` to allow empty input; without it, prompt repeats until input given.
- Use `hide_input=True` on `click.prompt()` for password entry; input is not echoed.
- Use `confirmation_prompt=True` to prompt twice and verify input matches; useful for passwords.
- Use `type=` on `click.prompt()` to convert input; it uses Click's type system.
- Use `value_proc=` on `click.prompt()` for custom conversion instead of type conversion.

## Confirmation
- Use `click.confirm()` for yes/no questions; returns boolean.
- Set `abort=True` on `click.confirm()` to raise `Abort` on negative answer.
- Set `default=None` on `click.confirm()` to require explicit yes/no; no default accepted.

## Progress Bars
- Use `click.progressbar()` as a context manager; it auto-closes and finalizes on exit.
- Provide `length=` to `click.progressbar()` when iterable doesn't support `len()`.
- Use `label=` on `click.progressbar()` to show descriptive text next to the bar.
- Set `show_eta=False` to hide time estimates; useful when progress is irregular.
- Set `show_percent=False` to hide percentage; useful when length is unknown.
- Set `show_pos=True` to display absolute position instead of just percentage.
- Use `item_show_func=` to display current item next to progress bar; return `None` to hide.
- Call `bar.update(n)` to manually advance progress by `n` steps; useful for non-iterable progress.
- Pass `current_item=` to `bar.update()` when using `item_show_func` for manual updates.
- Set `hidden=True` on `click.progressbar()` to suppress all output; useful for quiet mode.
- Use `update_min_steps=` to throttle rendering; prevents slowdown on very fast iterations.

## Terminal Input
- Use `click.getchar()` to read a single character from terminal; bypasses stdin buffering.
- Set `echo=True` on `click.getchar()` to show the typed character; default is hidden.
- Use `click.pause()` to wait for any keypress; it's a NOP when not connected to a terminal.
- Set `info=` on `click.pause()` to customize the prompt message.

## Editor Integration
- Use `click.edit()` to launch an editor for multi-line input; returns `None` if not saved.
- Set `editor=` on `click.edit()` to override the default editor; otherwise uses `$EDITOR`.
- Set `filename=` on `click.edit()` to edit an existing file instead of temp file.
- Set `extension=` on `click.edit()` to control syntax highlighting in the editor.
- Set `require_save=False` on `click.edit()` to return content even if not explicitly saved.

## File and Application Launching
- Use `click.launch()` to open URLs or files in the default application.
- Set `wait=True` on `click.launch()` to block until the application exits; doesn't work with `xdg-open`.
- Set `locate=True` on `click.launch()` to open file manager at the location instead of opening the file.

## Screen Control
- Use `click.clear()` to clear the terminal screen; it's a NOP when not a terminal.

## File Handling
- Use `click.open_file()` instead of `open()` for CLI file handling; it supports `-` for stdin/stdout.
- Use `lazy=True` on `click.open_file()` to defer opening until first access; default for write mode.
- Use `atomic=True` on `click.open_file()` to write to temp file and move on close; prevents partial writes.

## Stream Access
- Use `click.get_text_stream()` to get stdin/stdout/stderr as text streams with correct encoding.
- Use `click.get_binary_stream()` to get stdin/stdout/stderr as binary streams.

## Platform Utilities
- Use `click.get_app_dir()` to get platform-appropriate config directory; handles Windows/Mac/Linux differences.
- Set `roaming=True` on `click.get_app_dir()` for roaming profile on Windows; no effect elsewhere.
- Set `force_posix=True` on `click.get_app_dir()` to use `~/.appname` instead of XDG on POSIX.

## Filename Formatting
- Use `click.format_filename()` to safely display filenames; replaces invalid Unicode with `�`.
- Set `shorten=True` on `click.format_filename()` to strip directory path and show only basename.

For full reference, see the "Utilities" section of the Click API docs:
https://click.palletsprojects.com/en/stable/api/#utilities

Also see: https://click.palletsprojects.com/en/stable/utils/
