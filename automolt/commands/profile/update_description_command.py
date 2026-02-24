"""Command handler for the 'update-description' command.

Prompts the user for a new description and updates it both
remotely via the Moltbook API and locally in agent.json.
"""

from pathlib import Path
from typing import NoReturn

import click
from rich.console import Console

from automolt.api.client import MoltbookAPIError
from automolt.commands.agent_targeting import resolve_target_handle
from automolt.constants import CLI_NAME
from automolt.services.agent_service import AgentService

# Constants
MAX_DESCRIPTION_LENGTH = 500


@click.command("update-description")
@click.option(
    "--handle",
    type=str,
    default=None,
    help="Agent handle to update. Defaults to session active agent.",
)
@click.pass_context
def update_description(ctx: click.Context, handle: str | None) -> None:
    """Update a target agent's description.

    Args:
        ctx: Click context containing console, base_path, and agent_service.
    """
    console: Console = ctx.obj["console"]
    base_path: Path = ctx.obj["base_path"]
    agent_service: AgentService = ctx.obj["agent_service"]

    inherited_handle = _resolve_parent_profile_handle(ctx)
    effective_handle = handle if handle is not None else inherited_handle

    active_handle = _resolve_target_handle(console, base_path, ctx, effective_handle)
    if not active_handle:
        return

    description = _prompt_for_description(console)
    _update_agent_description(console, agent_service, active_handle, description, ctx)


def _resolve_parent_profile_handle(ctx: click.Context) -> str | None:
    """Return --handle passed to parent profile group, if available."""
    if ctx.parent is None:
        return None

    parent_handle = ctx.parent.params.get("handle")
    if isinstance(parent_handle, str):
        return parent_handle

    return None


def _resolve_target_handle(
    console: Console,
    base_path: Path,
    ctx: click.Context,
    explicit_handle: str | None,
) -> str | None:
    """Resolve command target handle using session-aware semantics.

    Args:
        console: Rich console for output.
        base_path: Base path for the automolt client.
        ctx: Click context for exit handling.

    Returns:
        The target agent handle, or None if no target agent is set.

    Raises:
        SystemExit: If client.json is not found.
    """
    try:
        target_handle = resolve_target_handle(base_path, explicit_handle)
    except FileNotFoundError:
        console.print(f"[red]No client.json found. Run '{CLI_NAME} init' first.[/red]")
        ctx.exit(1)
        return None
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        ctx.exit(1)
        return None

    if not target_handle:
        console.print(f"[yellow]No target agent selected. Use '{CLI_NAME} agents', run '{CLI_NAME} signup', or pass --handle.[/yellow]")
        return None

    return target_handle


def _update_agent_description(console: Console, agent_service: AgentService, active_handle: str, description: str, ctx: click.Context) -> NoReturn:
    """Update the agent description via API and display results.

    Args:
        console: Rich console for output.
        agent_service: Service for agent operations.
        active_handle: Handle of the active agent.
        description: New description to set.
        ctx: Click context for exit handling.

    Raises:
        SystemExit: Always exits after completion.
    """
    console.print()
    with console.status("Updating description..."):
        try:
            config = agent_service.update_description(active_handle, description)
        except FileNotFoundError:
            console.print(f"[red]Agent '{active_handle}' not found locally. The agent directory may have been removed.[/red]")
            ctx.exit(1)
        except MoltbookAPIError as exc:
            console.print(f"[bold red]Failed to update description:[/bold red] {exc.message}")
            if exc.hint:
                console.print(f"[dim]Hint: {exc.hint}[/dim]")
            ctx.exit(1)

    console.print(f"[green]Description updated for '{config.agent.handle}'.[/green]")
    console.print(f"[dim]New description: {config.agent.description}[/dim]")


def _prompt_for_description(console: Console) -> str:
    """Prompt the user for a new description in a validation loop.

    Args:
        console: Rich console for output.

    Returns:
        Validated description string.
    """
    while True:
        description = click.prompt("Enter new description")
        description = description.strip()

        if not description:
            console.print("[red]Description cannot be empty. Please try again.[/red]")
            continue

        if len(description) > MAX_DESCRIPTION_LENGTH:
            console.print(f"[red]Description must be {MAX_DESCRIPTION_LENGTH} characters or fewer.[/red]")
            continue

        return description
