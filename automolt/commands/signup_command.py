"""Command handler for the 'signup' command.

Manages the interactive signup flow: prompting for a handle, checking
availability, collecting a description, and registering the agent.
"""

from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

from automolt.api.client import MoltbookAPIError
from automolt.persistence.client_store import set_last_active_agent
from automolt.services.agent_service import AgentService


@click.command("signup")
@click.pass_context
def signup(ctx: click.Context) -> None:
    """Register a new agent on Moltbook."""
    console: Console = ctx.obj["console"]
    agent_service: AgentService = ctx.obj["agent_service"]

    console.print()
    console.print("[bold]Moltbook Agent Signup[/bold]")
    console.print()

    # Step 3-7: Loop until a valid, available handle is provided
    handle = _prompt_for_handle(console, agent_service)

    # Step 8: Prompt for a description
    description = _prompt_for_description(console)

    # Step 9-12: Register the agent and persist configuration
    console.print()
    with console.status("Registering agent on Moltbook..."):
        try:
            config = agent_service.create_agent(handle, description)
        except MoltbookAPIError as exc:
            console.print(f"[bold red]Registration failed:[/bold red] {exc.message}")
            if exc.hint:
                console.print(f"[dim]Hint: {exc.hint}[/dim]")
            ctx.exit(1)
            return

    # Remember the new agent as the client default for lazy session initialization.
    base_path: Path = ctx.obj["base_path"]
    set_last_active_agent(base_path, config.agent.handle)

    # Step 13: Display success message with claim instructions
    console.print()
    console.print(
        Panel(
            f"[bold green]Agent '{config.agent.handle}' registered successfully![/bold green]\n\n"
            f"[bold]API Key:[/bold] {config.agent.api_key}\n"
            f"[bold]Verification Code:[/bold] {config.agent.verification_code}\n\n"
            "[yellow]⚠️  Save your API key! It cannot be retrieved later.[/yellow]\n"
            "[dim]It has been saved under '.agents/{config.agent.handle}/agent.json'[/dim]\n\n"
            f"Please visit this URL to claim and verify your agent:\n"
            f"[link={config.agent.claim_url}][bold cyan]{config.agent.claim_url}[/bold cyan][/link]\n\n"
            "[dim]Once your tweet is detected by Moltbook, your agent's verification status will "
            "change from 'pending_verification' to 'verified' "
            "and the API key becomes fully active for posting.\n\n"
            "After posting your verification tweet, wait ~10 minutes, then run\n"
            "[bold]automolt profile[/bold] to check your verification status.[/dim]",
            title="Registration Complete",
            border_style="green",
        )
    )


def _prompt_for_handle(console: Console, agent_service: AgentService) -> str:
    """Prompt the user for a handle in a loop until an available one is found."""
    while True:
        handle = click.prompt("Enter a handle for your agent")
        handle = handle.strip()

        if not handle:
            console.print("[red]Handle cannot be empty. Please try again.[/red]")
            continue

        if len(handle) > 50:
            console.print("[red]Handle must be 50 characters or fewer.[/red]")
            continue

        with console.status("Checking availability..."):
            try:
                available = agent_service.is_handle_available(handle)
            except MoltbookAPIError as exc:
                console.print(f"[bold red]Error checking availability:[/bold red] {exc.message}")
                if exc.hint:
                    console.print(f"[dim]Hint: {exc.hint}[/dim]")
                continue

        if not available:
            console.print(f"[red]The handle '{handle}' is not available. Please choose a different one.[/red]")
            continue

        console.print(f"[green]Handle '{handle}' is available![/green]")
        return handle


def _prompt_for_description(console: Console) -> str:
    """Prompt the user for an agent description."""
    while True:
        description = click.prompt("Enter a description for your agent")
        description = description.strip()

        if not description:
            console.print("[red]Description cannot be empty. Please try again.[/red]")
            continue

        if len(description) > 500:
            console.print("[red]Description must be 500 characters or fewer.[/red]")
            continue

        return description
