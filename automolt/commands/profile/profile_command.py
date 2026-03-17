"""Command handler for the 'profile' command group.

Displays the active agent's profile information, checks verification
status, and provides the set-avatar and update-description subcommands.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel

from automolt.api.client import MoltbookAPIError
from automolt.commands.agent_targeting import resolve_target_handle
from automolt.commands.profile.update_description_command import update_description
from automolt.constants import CLI_NAME
from automolt.models.agent import Agent, AgentConfig, VerificationStatus
from automolt.services.agent_service import AgentService


def _resolve_target_handle(
    base_path: Path,
    console: Console,
    ctx: click.Context,
    explicit_handle: str | None,
) -> Optional[str]:
    """Resolve command target handle using session-aware semantics.

    Args:
        base_path: The base path of the automolt client
        console: Rich console for output
        ctx: Click context for exit handling
        explicit_handle: Optional --handle override

    Returns:
        The target agent handle, or None if not set
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


def _resolve_parent_profile_handle(ctx: click.Context) -> str | None:
    """Return --handle passed to parent 'profile' group, if available."""
    if ctx.parent is None:
        return None

    parent_handle = ctx.parent.params.get("handle")
    if isinstance(parent_handle, str):
        return parent_handle

    return None


def _fetch_agent_config(active_handle: str, agent_service: AgentService, console: Console) -> "AgentConfig":
    """Fetch agent configuration from API with fallback logic.

    Args:
        active_handle: The agent's handle
        agent_service: Service for agent operations
        console: Rich console for output

    Returns:
        The agent configuration

    Raises:
        SystemExit: If API calls fail
    """
    try:
        return agent_service.get_profile(active_handle)
    except FileNotFoundError:
        console.print(f"[red]Agent '{active_handle}' not found locally. The agent directory may have been removed.[/red]")
        raise click.ClickException("Agent not found locally")
    except ValueError:
        console.print(f"[red]Agent config for '{active_handle}' is corrupted. Try removing the agent directory and signing up again.[/red]")
        raise click.ClickException("Corrupted agent configuration")
    except MoltbookAPIError:
        # Fallback to status endpoint for unclaimed agents
        try:
            return agent_service.get_agent_status(active_handle)
        except MoltbookAPIError as exc:
            console.print(f"[bold red]Failed to check status:[/bold red] {exc.message}")
            if exc.hint:
                console.print(f"[dim]Hint: {exc.hint}[/dim]")
            raise click.ClickException("Failed to fetch agent status")


def _build_profile_text(agent: "Agent") -> str:
    """Build the profile display text.

    Args:
        agent: The agent object

    Returns:
        Formatted profile text
    """
    is_claimed = agent.verification_status == VerificationStatus.VERIFIED

    status_display = "[bold green]Verified[/bold green]" if is_claimed else "[bold yellow]Pending Verification[/bold yellow]"

    profile_url = f"https://www.moltbook.com/u/{agent.handle}"
    profile_text = f"[bold]Handle:[/bold] {agent.handle}\n[bold]Description:[/bold] {agent.description}\n[bold]Profile:[/bold] [link={profile_url}]{profile_url}[/link]\n"

    # Avatar info
    if agent.avatar_url:
        profile_text += f"[bold]Avatar:[/bold] [link={agent.avatar_url}]{agent.avatar_url}[/link]\n"
    else:
        profile_text += f"[bold]Avatar:[/bold] [dim]Not set. Run '[bold]{CLI_NAME} profile set-avatar[/bold]' to upload one.[/dim]\n"

    profile_text += f"[bold]Verification Status:[/bold] {status_display}"

    # Twitter handle used for verification
    if agent.x_handle:
        profile_text += f"\n[bold]X (Twitter):[/bold] @{agent.x_handle}"

    # Karma and social counts
    if agent.karma is not None:
        profile_text += f"\n[bold]Karma:[/bold] {agent.karma}"
    if agent.follower_count is not None:
        profile_text += f"\n[bold]Followers:[/bold] {agent.follower_count}"
    if agent.following_count is not None:
        profile_text += f"\n[bold]Following:[/bold] {agent.following_count}"

    # Suspension warning
    if agent.is_active is False:
        profile_text += "\n[bold]Status:[/bold] [bold red]SUSPENDED[/bold red]"

    # Timestamps
    if agent.created_at:
        profile_text += f"\n[bold]Created:[/bold] {_format_timestamp(agent.created_at)}"
    if agent.last_active:
        profile_text += f"\n[bold]Last Active:[/bold] {_format_timestamp(agent.last_active)}"

    # Verification instructions if not yet claimed
    if not is_claimed:
        profile_text += (
            "\n\n[dim]Your agent has not been verified yet. "
            "Follow these steps to complete verification:\n\n"
            "1) Visit the Claim URL below\n"
            f"[/dim][link={agent.claim_url}][bold cyan]{agent.claim_url}[/bold cyan][/link][dim]\n\n"
            "2) Post a tweet with the verification code provided below\n"
            f"[/dim][bold]{agent.verification_code}[/bold][dim]\n\n"
            "3) Wait ~10 minutes for Moltbook to detect your tweet\n\n"
            f"4) Run '[bold]{CLI_NAME} profile[/bold]' again to check your status[/dim]"
        )

    return profile_text


@click.group("profile", invoke_without_command=True)
@click.option(
    "--handle",
    type=str,
    default=None,
    help="Agent handle to inspect. Defaults to session active agent.",
)
@click.pass_context
def profile(ctx: click.Context, handle: str | None) -> None:
    """Display a target agent profile or manage profile settings."""
    if ctx.invoked_subcommand is not None:
        return

    console: Console = ctx.obj["console"]
    base_path: Path = ctx.obj["base_path"]
    agent_service: AgentService = ctx.obj["agent_service"]

    # Resolve target agent
    active_handle = _resolve_target_handle(base_path, console, ctx, handle)
    if not active_handle:
        return

    # Fetch profile data
    console.print()
    with console.status("Fetching profile..."):
        config = _fetch_agent_config(active_handle, agent_service, console)

    # Display profile
    agent = config.agent
    profile_text = _build_profile_text(agent)
    is_claimed = agent.verification_status == VerificationStatus.VERIFIED

    console.print()
    console.print(
        Panel(
            profile_text,
            title=f"Agent Profile — {agent.handle}",
            border_style="cyan" if is_claimed else "yellow",
        )
    )


def _display_avatar_constraints(console: Console) -> None:
    """Display avatar upload constraints to the user.

    Args:
        console: Rich console for output
    """
    console.print()
    console.print("[bold]Avatar Upload Constraints:[/bold]")
    console.print("  - Max size: 500 KB")
    console.print("  - Formats: JPEG, PNG, GIF, WebP")
    console.print("  - Recommended: Square image (e.g., 512x512)")
    console.print()


def _process_file_path(file_path: str) -> str:
    """Process and normalize the file path input.

    Args:
        file_path: Raw file path input from user

    Returns:
        Normalized absolute file path
    """
    # Handle escaped spaces and other shell escapes
    file_path = file_path.replace("\\ ", " ")
    # Expand user home directory shorthand
    return str(Path(file_path).expanduser().resolve())


def _handle_avatar_upload_errors(exc: Exception, console: Console) -> None:
    """Handle errors during avatar upload.

    Args:
        exc: The exception that occurred
        console: Rich console for output

    Raises:
        SystemExit: Always exits after handling error
    """
    if isinstance(exc, FileNotFoundError):
        console.print(f"[red]{exc}[/red]")
    elif isinstance(exc, ValueError):
        console.print(f"[red]{exc}[/red]")
    elif isinstance(exc, MoltbookAPIError):
        console.print(f"[bold red]Failed to upload avatar:[/bold red] {exc.message}")
        if exc.hint:
            console.print(f"[dim]Hint: {exc.hint}[/dim]")
    else:
        console.print(f"[red]Unexpected error: {exc}[/red]")

    raise click.ClickException("Avatar upload failed")


@profile.command("set-avatar")
@click.option(
    "--handle",
    type=str,
    default=None,
    help="Agent handle to update. Defaults to session active agent.",
)
@click.pass_context
def set_avatar(ctx: click.Context, handle: str | None) -> None:
    """Upload an avatar image for a target agent."""
    console: Console = ctx.obj["console"]
    base_path: Path = ctx.obj["base_path"]
    agent_service: AgentService = ctx.obj["agent_service"]

    inherited_handle = _resolve_parent_profile_handle(ctx)
    effective_handle = handle if handle is not None else inherited_handle

    # Resolve target agent
    active_handle = _resolve_target_handle(base_path, console, ctx, effective_handle)
    if not active_handle:
        return

    # Display constraints
    _display_avatar_constraints(console)

    # Prompt for file path
    file_path = click.prompt("Enter the path to your avatar image").strip()
    file_path = _process_file_path(file_path)

    # Upload avatar
    console.print()
    with console.status("Uploading avatar..."):
        try:
            config = agent_service.set_avatar(active_handle, file_path)
        except Exception as exc:
            _handle_avatar_upload_errors(exc, console)

    console.print(f"[green]Avatar uploaded for '{config.agent.handle}'.[/green]")
    if config.agent.avatar_url:
        console.print(f"[dim]Avatar URL: {config.agent.avatar_url}[/dim]")


profile.add_command(update_description)


def _format_timestamp(iso_timestamp: str) -> str:
    """Format an ISO 8601 timestamp to the user's local timezone and locale."""
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        local_dt = dt.astimezone()
        return local_dt.strftime("%Y-%m-%d %H:%M %Z")
    except ValueError, TypeError:
        return iso_timestamp
