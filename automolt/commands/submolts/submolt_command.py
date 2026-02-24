"""Command handler for the 'submolt' command group.

Provides subcommands for managing submolts (communities) on Moltbook.
"""

import re
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

from automolt.api.client import MoltbookAPIError
from automolt.commands.agent_targeting import resolve_target_handle
from automolt.constants import CLI_NAME
from automolt.persistence.agent_store import load_agent_config
from automolt.services.submolt_service import SubmoltService

# Submolt name must be lowercase alphanumeric with optional hyphens
SUBMOLT_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@click.group("submolt")
@click.option(
    "--handle",
    type=str,
    default=None,
    help="Agent handle to use. Defaults to session active agent.",
)
@click.pass_context
def submolt(ctx: click.Context, handle: str | None) -> None:
    """Manage submolts (communities) on Moltbook."""
    del ctx, handle


@submolt.command("create")
@click.option(
    "--handle",
    type=str,
    default=None,
    help="Agent handle to use. Defaults to session active agent.",
)
@click.pass_context
def create(ctx: click.Context, handle: str | None) -> None:
    """Create a new submolt (community) on Moltbook."""
    console: Console = ctx.obj["console"]
    base_path: Path = ctx.obj["base_path"]
    submolt_service: SubmoltService = ctx.obj["submolt_service"]

    inherited_handle = _resolve_parent_submolt_handle(ctx)
    effective_handle = handle if handle is not None else inherited_handle

    # Resolve command target handle using session-aware semantics.
    try:
        active_handle = resolve_target_handle(base_path, effective_handle)
    except FileNotFoundError:
        console.print(f"[red]No client.json found. Run '{CLI_NAME} init' first.[/red]")
        ctx.exit(1)
        return
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        ctx.exit(1)
        return

    if not active_handle:
        console.print(f"[yellow]No target agent selected. Use '{CLI_NAME} agents', run '{CLI_NAME} signup', or pass --handle.[/yellow]")
        return

    # Load agent config to get API key
    try:
        config = load_agent_config(base_path, active_handle)
    except FileNotFoundError:
        console.print(f"[red]Agent '{active_handle}' not found locally.[/red]")
        ctx.exit(1)
        return
    except ValueError:
        console.print(f"[red]Agent config for '{active_handle}' is corrupted.[/red]")
        ctx.exit(1)
        return

    if not config.agent.api_key:
        console.print("[red]Agent must be claimed before creating a submolt.[/red]")
        ctx.exit(1)
        return

    console.print()
    console.print("[bold]Create a New Submolt[/bold]")
    console.print()

    # Prompt for submolt name with validation
    name = _prompt_for_name(console)

    # Prompt for display name
    display_name = _prompt_for_display_name(console)

    # Prompt for description
    description = _prompt_for_description(console)

    # Create submolt via API
    console.print()
    with console.status("Creating submolt..."):
        try:
            result = submolt_service.create_submolt(config.agent.api_key, name, display_name, description)
        except MoltbookAPIError as exc:
            console.print(f"[bold red]Failed to create submolt:[/bold red] {exc.message}")
            if exc.hint:
                console.print(f"[dim]Hint: {exc.hint}[/dim]")
            ctx.exit(1)
            return

    console.print()
    console.print(
        Panel(
            f"[bold green]Submolt '{result.display_name}' created![/bold green]\n\n"
            f"[bold]Name:[/bold] {result.name}\n"
            f"[bold]Display Name:[/bold] {result.display_name}\n"
            f"[bold]Description:[/bold] {result.description}\n"
            f"[bold]Owner:[/bold] {result.owner}\n"
            f"[bold]Subscribers:[/bold] {result.subscriber_count}\n\n"
            "[dim]You are automatically subscribed as the owner.[/dim]",
            title=f"Submolt Created — {result.name}",
            border_style="green",
        )
    )


def _resolve_parent_submolt_handle(ctx: click.Context) -> str | None:
    """Return --handle passed to parent submolt group, if available."""
    if ctx.parent is None:
        return None

    parent_handle = ctx.parent.params.get("handle")
    if isinstance(parent_handle, str):
        return parent_handle

    return None


def _prompt_for_name(console: Console) -> str:
    """Prompt for a URL-friendly submolt name with validation."""
    while True:
        name = click.prompt("Enter submolt name (URL-friendly, lowercase)").strip()

        if not name:
            console.print("[red]Name cannot be empty. Please try again.[/red]")
            continue

        if not SUBMOLT_NAME_PATTERN.match(name):
            console.print("[red]Name must be lowercase alphanumeric with optional hyphens (e.g., 'ai-thoughts').[/red]")
            continue

        return name


def _prompt_for_display_name(console: Console) -> str:
    """Prompt for a human-readable display name."""
    while True:
        display_name = click.prompt("Enter display name (human-readable)").strip()

        if not display_name:
            console.print("[red]Display name cannot be empty. Please try again.[/red]")
            continue

        return display_name


def _prompt_for_description(console: Console) -> str:
    """Prompt for a submolt description."""
    while True:
        description = click.prompt("Enter description").strip()

        if not description:
            console.print("[red]Description cannot be empty. Please try again.[/red]")
            continue

        return description
