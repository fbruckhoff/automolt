---
includes: CLI command structure, command handlers, and flow of control
excludes: Specific command implementation details
related: AUTOMATION.md
---

# CLI Architecture

## Overview

The CLI layer is the top-level controller in the automolt architecture. It handles user interaction, parses commands, and delegates work to the appropriate services.

## Command Flow

- **Entry Point**: `main.py` imports and runs `cli.py`
- **Command Router**: `cli.py` defines the main `@click.group()` and registers commands
- **Command Execution**: Commands delegate to specific handlers in the `commands/` folder

## Command Handlers

Command handlers are responsible for the control flow and user interaction:

- **Location**: Files reside under `commands/`
- **Naming Convention**: Files must match the corresponding command, postfixed with `_command`
  - Example: `commands/signup_command.py` for the `signup` command

### Responsibilities

1. **Control Flow**
   - Act as the "driver" of the conversation
   - Determine when to perform actions
   - Delegate business logic to Services

2. **User Interface**
   - Print formatted text with `Rich`
   - Collect user input (`click.prompt`, etc.)
   - Parse command arguments
   - Provide feedback (spinners, progress bars)

3. **Service Delegation**
   - Each command handler calls a specific Service for business logic
   - Services handle the "how" while command handlers handle the "when"

## Command Structure

Command handlers contain command-specific presentation logic:
- Parse inputs
- Display outputs
- Provide visual feedback
- Handle command-specific options

## Cross-Cutting Rules

- Services never call CLI commands
- If a Service needs another feature, it calls the corresponding Service method directly
- The CLI layer manages `ctx.invoke` for command invocation
