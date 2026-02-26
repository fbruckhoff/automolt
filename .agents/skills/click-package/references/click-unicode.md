# Click Unicode Support

Click handles Unicode text across different environments, but requires proper system locale configuration.

## Key Behaviors

**Click's Unicode handling:**
- Command line args are Unicode (not bytes)
- `sys.argv` is always text/Unicode
- File system API uses Unicode with surrogate support
- Standard streams opened in text mode by default
- Binary streams discovered when needed

## Common Issues

**Misconfigured locales cause Click to abort:**
```
RuntimeError: Click will abort further execution because Python was
configured to use ASCII as encoding for the environment.
```

**Solution - Export UTF-8 locale before running script:**

**German locale:**
```bash
export LC_ALL=de_DE.utf-8
export LANG=de_DE.utf-8
```

**US locale:**
```bash
export LC_ALL=en_US.utf-8
export LANG=en_US.utf-8
```

**Generic UTF-8 (newer systems):**
```bash
export LC_ALL=C.UTF-8
export LANG=C.UTF-8
```

**Check available locales:**
```bash
locale -a
```

**Note:** Some systems require `UTF-8` vs `UTF8` - check with `locale -a`.

## Testing with Streams

**Don't use `StringIO` for stdin/stdout:**
```python
# ❌ This breaks
sys.stdin = io.StringIO('Input here')
sys.stdout = io.StringIO()
```

**Use `BytesIO` with `TextIOWrapper`:**
```python
# ✓ Correct approach
input_data = 'Input here'
in_stream = io.BytesIO(input_data.encode('utf-8'))
sys.stdin = io.TextIOWrapper(in_stream, encoding='utf-8')

out_stream = io.BytesIO()
sys.stdout = io.TextIOWrapper(out_stream, encoding='utf-8')

# Get output from BytesIO, not TextIOWrapper
result = out_stream.getvalue()  # Not sys.stdout.getvalue()
```

## Environment Considerations

**Where Unicode issues appear:**
- SSH connections to machines with different locales
- Init systems and deployment tools (often no locale set)
- Cron jobs (minimal environment)
- Docker containers without locale configuration

**Python 3.7+ improvement:**
PEP 538 and PEP 540 changed default behavior in unconfigured environments, reducing `RuntimeError` occurrences. Still, proper locale configuration is recommended.

## Best Practices

**For deployment:**
- Always export UTF-8 locale in init scripts
- Set locale in Docker containers
- Configure cron job environments with locale
- Document locale requirements for users

**For development:**
- Test with proper UTF-8 locale set
- Use `TextIOWrapper` for stream testing
- Handle surrogate escapes in filenames (Click does this automatically)

Full Reference:
https://click.palletsprojects.com/en/stable/unicode-support/
https://click.palletsprojects.com/en/stable/wincmd/
