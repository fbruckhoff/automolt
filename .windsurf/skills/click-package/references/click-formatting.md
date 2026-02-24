# Click Formatting

## Rules:
- Use `HelpFormatter` only for custom help output; Click handles formatting automatically.
- Treat `HelpFormatter` as a write-once buffer; it accumulates text in memory.
- Use `write()` to append raw unicode strings to the buffer.
- Use `indent()` and `dedent()` to control nesting levels; always pair them.
- Use `write_usage()` for standardized usage lines; it handles prog name and args.
- Use `write_heading()` for section headers; it adds proper spacing.
- Use `write_paragraph()` for flowing text; it handles wrapping automatically.
- Use `write_text()` for pre-formatted text that preserves paragraphs.
- Use `write_dl()` for definition lists; this is how options and commands are formatted.
- Use `section()` context manager for heading + indented content; it's cleaner than manual indent/dedent.
- Use `indentation()` context manager when you need temporary indent without a heading.
- Call `getvalue()` to retrieve the accumulated buffer as a string.
- Set `width` to control line wrapping; defaults to terminal width clamped to 78.
- Set `indent_increment` to control how much each nesting level indents.
- Use `wrap_text()` for manual text wrapping outside of HelpFormatter.
- Set `preserve_paragraphs=True` on `wrap_text()` to handle multi-paragraph text intelligently.
- Use `\b` (backslash-b) prefix on a paragraph to prevent rewrapping in that block.
- Treat `\b` as a formatting escape, not literal text; it signals "don't wrap this."
- Use `initial_indent` and `subsequent_indent` for hanging indents in `wrap_text()`.
- Assume `wrap_text()` operates on single paragraphs by default; enable `preserve_paragraphs` for multiple.
- Use `write_dl()` with `col_max` to limit the first column width in definition lists.
- Use `col_spacing` to control spacing between columns in definition lists.
- Treat formatting as presentation-only; don't embed logic in formatters.

For full reference, see the "Formatting" section of the Click API docs:
https://click.palletsprojects.com/en/stable/api/#formatting
