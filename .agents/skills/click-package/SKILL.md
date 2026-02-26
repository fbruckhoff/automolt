---
name: click-package
description: Click package best practices and patterns. Use for any Click-related code including CLI development, commands, options, arguments, groups, contexts, parameters, or testing.
---

# Click Package Guide

## Getting Started

**About Click**
Overview of Click concepts and initial setup. Use when starting a new Click project.
Reference: click-info.md

**List Click in Dependencies**
Add to `pyproject.toml`. Pip handles installation.

**Use virtualenv** to isolate dependencies.
https://click.palletsprojects.com/en/stable/virtualenv/

**Use Package Entry Points**
Package CLI as installable with entry points defined in `pyproject.toml`.
https://click.palletsprojects.com/en/stable/entry-points/

**Architecture Best Practices**
Project structure, command organization, and CLI design patterns.
Reference: click-architecture.md

## Commands and Structure

**Commands and Groups**
Define CLI commands with @click.command() or organize with @click.group().
Reference: click-commands.md

**Advanced Groups and Context**
Nested/chained commands, shared state via ctx.obj, pipeline workflows.
Reference: click-advanced-groups-context.md

**Context Object**
Working with ctx object, ctx.obj, ctx.invoke, context operations.
Reference: click-context.md

## Parameters and Validation

**Parameters (Options and Arguments)**
Parameter types, validation, options, and arguments.
Reference: click-parameters.md

**Types**
Built-in types for conversions. Implement custom types by subclassing `ParamType`.
Reference: click-types.md

**Callbacks and Validation**
Validate parameter values and control callback execution flow.
Reference: click-callbacks.md

**Decorators and Shortcuts**
Common decorators like @click.version_option, @click.pass_context, @click.pass_obj.
Reference: click-decorators.md

## User Interaction

**User Input and Prompts**
Use `prompt=True` for interactive input, `click.confirm()` for yes/no prompts.
Reference: click-prompts.md

**File Handling**
Use `click.File()` for I/O with stdin/stdout, `click.Path()` for path validation.
Reference: click-files.md

**Utilities**
Output, colors, progress bars, editors, file operations.
Reference: click-utilities.md

## Documentation and Help

**Help Pages**
Use docstrings for command help, `help=` parameter for options.
Reference: click-help.md

**Formatting**
Custom help output with `HelpFormatter`. Click handles formatting automatically.
Reference: click-formatting.md

**Shell Completion**
Tab completion for Bash, Zsh, and Fish shells.
Reference: click-completion.md

## Testing and Error Handling

**Testing**
Write tests for Click commands with CliRunner.
Reference: click-testing.md

**Exception Handling and Exit Codes**
Automatic error handling. Use `standalone_mode=False` for manual control.
Reference: click-exceptions.md

## Advanced Topics

**Parsing**
Click manages parsing automatically. Use context flags to control behavior.
Reference: click-parsing.md

**Unicode Support**
Requires proper locale configuration for Unicode handling.
Reference: click-unicode.md

**Extending Click**
https://click.palletsprojects.com/en/stable/extending-click/

**Upgrade Guides**
Changes, deprecations, and migration guidance.
https://click.palletsprojects.com/en/stable/upgrade-guides/
