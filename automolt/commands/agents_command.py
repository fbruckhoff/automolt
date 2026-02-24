"""Command handler for the 'agents' command.

Lists all available agents with a Rich radio button interface for selection.
Allows users to switch the session active agent (and remembered last-active)
by navigating with arrow keys
and confirming with ENTER.
"""

from pathlib import Path

import click
from rich.console import Console

from automolt.commands.agent_targeting import resolve_target_handle, set_selected_agent
from automolt.constants import CLI_NAME


@click.command("agents")
@click.pass_context
def agents(ctx: click.Context) -> None:
    """List and switch between available agents."""
    console: Console = ctx.obj["console"]
    base_path: Path = ctx.obj["base_path"]

    console.print()
    console.print("[bold]Available Agents[/bold]")
    console.print()

    # Get all agent directories
    agents_dir = base_path / ".agents"
    if not agents_dir.exists() or not agents_dir.is_dir():
        console.print(f"[yellow]No agents found. Use '{CLI_NAME} signup' to create an agent.[/yellow]")
        return

    # Get all subdirectories (agent handles)
    agent_handles = sorted(item.name for item in agents_dir.iterdir() if item.is_dir())

    if not agent_handles:
        console.print(f"[yellow]No agents found. Use '{CLI_NAME} signup' to create an agent.[/yellow]")
        return

    # Get current session target (or lazily initialize from remembered last-active)
    try:
        current_active = resolve_target_handle(base_path, explicit_handle=None)
    except FileNotFoundError:
        current_active = None
    except ValueError as exc:
        console.print(f"[yellow]Warning: {exc}[/yellow]")
        current_active = None

    # If there's only one agent, just show info and return
    if len(agent_handles) == 1:
        only_agent = agent_handles[0]
        if current_active == only_agent:
            console.print(f"[green]Only agent '{only_agent}' is already active.[/green]")
        else:
            console.print(f"[dim]Only agent found: '{only_agent}'[/dim]")
            console.print(f"[yellow]Setting '{only_agent}' as the selected agent for this session...[/yellow]")
            set_selected_agent(base_path, only_agent)
            console.print(f"[green]Agent '{only_agent}' is now selected.[/green]")
        return

    # Use proper radio button interface with arrow navigation
    selected_index = _show_radio_selection(console, agent_handles, current_active)

    if selected_index is not None:
        selected_agent = agent_handles[selected_index]
        if selected_agent != current_active:
            set_selected_agent(base_path, selected_agent)
            console.print()
            console.print(f"[green]Agent '{selected_agent}' is now selected.[/green]")
        else:
            console.print()
            console.print(f"[dim]Agent '{selected_agent}' is already selected.[/dim]")
    else:
        console.print("\n[yellow]Agent selection cancelled.[/yellow]")


def _show_radio_selection(console: Console, choices: list[str], current_active: str | None) -> int | None:
    """Show a radio button selection interface with arrow key navigation using curses."""
    import curses

    # Find current active index
    active_index = 0
    if current_active and current_active in choices:
        active_index = choices.index(current_active)

    current_selection = active_index

    def curses_main(stdscr):
        nonlocal current_selection

        # Set up curses
        curses.curs_set(0)  # Hide cursor
        stdscr.clear()

        # Colors
        curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_CYAN, curses.COLOR_BLUE)

        while True:
            stdscr.clear()

            # Title
            stdscr.addstr(0, 0, "Available Agents", curses.A_BOLD)
            stdscr.addstr(1, 0, "Use ↑↓ arrows to navigate, ENTER to select, ESC to cancel:", curses.A_DIM)
            stdscr.addstr(2, 0, "")

            # Display choices
            for i, choice in enumerate(choices):
                y_pos = 3 + i

                if i == current_selection:
                    # Selected item
                    marker = "●"
                    attr = curses.color_pair(1) | curses.A_BOLD
                else:
                    # Unselected item
                    marker = "○"
                    attr = curses.color_pair(2)

                # Show if this is the current active agent
                line = f"  {marker} {choice}"
                if choice == current_active:
                    line += " (active)"
                    if i == current_selection:
                        attr = curses.color_pair(3) | curses.A_BOLD

                stdscr.addstr(y_pos, 0, line, attr)

            stdscr.refresh()

            # Get input
            key = stdscr.getch()

            if key == curses.KEY_UP:
                current_selection = (current_selection - 1) % len(choices)
            elif key == curses.KEY_DOWN:
                current_selection = (current_selection + 1) % len(choices)
            elif key in (curses.KEY_ENTER, 10, 13):  # ENTER
                return current_selection
            elif key == 27:  # ESC
                return None
            elif key == 3:  # Ctrl+C
                return None

    try:
        # Run curses interface
        result = curses.wrapper(curses_main)
        return result
    except Exception:
        # Fallback to simple selection if curses fails
        return _fallback_selection(console, choices, current_active)


def _fallback_selection(console: Console, choices: list[str], current_active: str | None) -> int | None:
    """Fallback selection method if curses fails."""
    from rich.prompt import IntPrompt

    console.print("[bold]Available Agents[/bold]")
    console.print()

    for i, choice in enumerate(choices, 1):
        active_indicator = " [dim](active)[/dim]" if choice == current_active else ""
        console.print(f"  ({i}) ○ {choice}{active_indicator}")

    console.print()
    console.print(f"[dim]Enter the number of your choice (1-{len(choices)}), or 0 to cancel:[/dim]")

    try:
        selection = IntPrompt.ask("Select agent", default=0, show_default=False)

        if 1 <= selection <= len(choices):
            return selection - 1
        else:
            return None
    except KeyboardInterrupt, EOFError:
        return None
