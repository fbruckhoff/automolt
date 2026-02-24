"""Command handler for the 'comment' command.

Adds a comment to a post on Moltbook.
"""

from pathlib import Path

import click
from rich.console import Console

from automolt.api.client import MoltbookAPIError
from automolt.commands.agent_targeting import resolve_target_handle
from automolt.constants import CLI_NAME
from automolt.persistence.agent_store import load_agent_config
from automolt.services.post_service import PostService


@click.command("comment")
@click.option(
    "--handle",
    type=str,
    default=None,
    help="Agent handle to use. Defaults to session active agent.",
)
@click.option("--post-id", required=True, help="The ID of the post to comment on.")
@click.option("--content", required=True, help="The comment text.")
@click.option("--parent-id", default=None, help="Optional parent comment ID for threaded replies.")
@click.pass_context
def comment(ctx: click.Context, handle: str | None, post_id: str, content: str, parent_id: str | None) -> None:
    """Add a comment to a post on Moltbook."""
    console: Console = ctx.obj["console"]
    base_path: Path = ctx.obj["base_path"]
    post_service: PostService = ctx.obj["post_service"]

    # Resolve command target handle using session-aware semantics.
    try:
        active_handle = resolve_target_handle(base_path, handle)
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
        console.print("[red]Agent must be claimed before commenting.[/red]")
        ctx.exit(1)
        return

    # Add comment via API
    with console.status("Posting comment..."):
        try:
            result = post_service.add_comment(config.agent.api_key, post_id, content, parent_id)
        except MoltbookAPIError as exc:
            console.print(f"[bold red]Failed to post comment:[/bold red] {exc.message}")
            if exc.hint:
                console.print(f"[dim]Hint: {exc.hint}[/dim]")
            ctx.exit(1)
            return

    console.print()
    console.print("[bold green]Comment posted successfully![/bold green]")
    console.print(f"[bold]Comment ID:[/bold] {result.id}")
    console.print(f"[bold]Post ID:[/bold] {result.post_id}")
    if result.parent_id:
        console.print(f"[bold]Reply to:[/bold] {result.parent_id}")
    console.print(f"[bold]Content:[/bold] {result.content}")
