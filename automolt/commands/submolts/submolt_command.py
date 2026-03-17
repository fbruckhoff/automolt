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
from automolt.services.post_service import PostService
from automolt.services.submolt_service import SubmoltService

SUBMOLT_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SUBMOLT_NAME_MIN_LENGTH = 2
SUBMOLT_NAME_MAX_LENGTH = 30


@click.group("submolt", invoke_without_command=True)
@click.option(
    "--handle",
    type=str,
    default=None,
    help="Agent handle to use. Defaults to session active agent.",
)
@click.pass_context
def submolt(ctx: click.Context, handle: str | None) -> None:
    """Manage submolts (communities) on Moltbook."""
    del handle
    if ctx.invoked_subcommand is not None:
        return
    click.echo(ctx.get_help())


@submolt.command("create")
@click.option(
    "--name",
    required=True,
    help="URL-safe submolt name (lowercase, hyphens allowed).",
)
@click.option(
    "--display-name",
    required=True,
    help="Human-readable submolt name.",
)
@click.option(
    "--description",
    default=None,
    help="Optional description of the submolt.",
)
@click.option(
    "--allow-crypto",
    is_flag=True,
    default=False,
    help="Allow cryptocurrency-related content in this submolt.",
)
@click.option(
    "--handle",
    type=str,
    default=None,
    help="Agent handle to use. Defaults to session active agent.",
)
@click.pass_context
def create(ctx: click.Context, name: str, display_name: str, description: str | None, allow_crypto: bool, handle: str | None) -> None:
    """Create a new submolt (community) on Moltbook."""
    console: Console = ctx.obj["console"]
    submolt_service: SubmoltService = ctx.obj["submolt_service"]

    try:
        normalized_name = _normalize_submolt_name(name)
        normalized_display_name = _require_non_empty(display_name, "Display name")
        normalized_description = _normalize_optional_text(description)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        ctx.exit(1)
        return

    config = _load_target_agent_config(ctx, console, handle, "creating a submolt")
    if config is None:
        return

    with console.status("Creating submolt..."):
        try:
            result = submolt_service.create_submolt(
                config.agent.api_key,
                normalized_name,
                normalized_display_name,
                normalized_description,
                allow_crypto=allow_crypto,
            )
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            ctx.exit(1)
            return
        except MoltbookAPIError as exc:
            console.print(f"[bold red]Failed to create submolt:[/bold red] {exc.message}")
            if exc.hint:
                console.print(f"[dim]Hint: {exc.hint}[/dim]")
            ctx.exit(1)
            return

    description_text = result.description or "[dim]Not provided[/dim]"
    allow_crypto_text = "Yes" if result.allow_crypto else "No"
    verification_note = "[dim]Verification completed automatically before publishing.[/dim]\n\n" if result.verification_completed else ""

    console.print()
    console.print(
        Panel(
            f"[bold green]Submolt '{result.display_name}' created![/bold green]\n\n"
            f"{verification_note}"
            f"[bold]Name:[/bold] {result.name}\n"
            f"[bold]Display Name:[/bold] {result.display_name}\n"
            f"[bold]Description:[/bold] {description_text}\n"
            f"[bold]Allow Crypto:[/bold] {allow_crypto_text}\n"
            f"[bold]Owner:[/bold] {result.owner}\n"
            f"[bold]Subscribers:[/bold] {result.subscriber_count}\n\n"
            "[dim]You are automatically subscribed as the owner.[/dim]",
            title=f"Submolt Created — {result.name}",
            border_style="green",
        )
    )


@submolt.command("post")
@click.argument("submolt_name")
@click.option(
    "--title",
    required=True,
    help="Post title.",
)
@click.option(
    "--content",
    default=None,
    help="Text body for a post.",
)
@click.option(
    "--url",
    default=None,
    help="URL for a link post.",
)
@click.option(
    "--handle",
    type=str,
    default=None,
    help="Agent handle to use. Defaults to session active agent.",
)
@click.pass_context
def post(ctx: click.Context, submolt_name: str, title: str, content: str | None, url: str | None, handle: str | None) -> None:
    """Create a post in a target submolt."""
    console: Console = ctx.obj["console"]
    post_service: PostService = ctx.obj["post_service"]

    try:
        normalized_submolt_name = _normalize_submolt_name(submolt_name)
        normalized_title = _require_non_empty(title, "Post title")
        normalized_content = _normalize_optional_text(content)
        normalized_url = _normalize_optional_text(url)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        ctx.exit(1)
        return

    config = _load_target_agent_config(ctx, console, handle, "posting")
    if config is None:
        return

    with console.status("Creating post..."):
        try:
            result = post_service.create_post(
                config.agent.api_key,
                normalized_submolt_name,
                normalized_title,
                content=normalized_content,
                url=normalized_url,
            )
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            ctx.exit(1)
            return
        except MoltbookAPIError as exc:
            console.print(f"[bold red]Failed to create post:[/bold red] {exc.message}")
            if exc.hint:
                console.print(f"[dim]Hint: {exc.hint}[/dim]")
            ctx.exit(1)
            return

    result_submolt_name = result.submolt.name if result.submolt is not None else normalized_submolt_name
    verification_note = "[dim]Verification completed automatically before publishing.[/dim]\n\n" if result.verification_completed else ""

    console.print()
    console.print(
        Panel(
            f"[bold green]Post created successfully![/bold green]\n\n{verification_note}[bold]Post ID:[/bold] {result.id}\n[bold]Submolt:[/bold] {result_submolt_name}\n[bold]Title:[/bold] {result.title}",
            title=f"Post Created — {result.id}",
            border_style="green",
        )
    )


def _load_target_agent_config(
    ctx: click.Context,
    console: Console,
    explicit_handle: str | None,
    action_label: str,
):
    base_path: Path = ctx.obj["base_path"]
    inherited_handle = _resolve_parent_submolt_handle(ctx)
    effective_handle = explicit_handle if explicit_handle is not None else inherited_handle

    try:
        active_handle = resolve_target_handle(base_path, effective_handle)
    except FileNotFoundError:
        console.print(f"[red]No client.json found. Run '{CLI_NAME} init' first.[/red]")
        ctx.exit(1)
        return None
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        ctx.exit(1)
        return None

    if not active_handle:
        console.print(f"[yellow]No target agent selected. Use '{CLI_NAME} agents', run '{CLI_NAME} signup', or pass --handle.[/yellow]")
        return None

    try:
        config = load_agent_config(base_path, active_handle)
    except FileNotFoundError:
        console.print(f"[red]Agent '{active_handle}' not found locally.[/red]")
        ctx.exit(1)
        return None
    except ValueError:
        console.print(f"[red]Agent config for '{active_handle}' is corrupted.[/red]")
        ctx.exit(1)
        return None

    if not config.agent.api_key:
        console.print(f"[red]Agent must be claimed before {action_label}.[/red]")
        ctx.exit(1)
        return None

    return config


def _resolve_parent_submolt_handle(ctx: click.Context) -> str | None:
    """Return --handle passed to parent submolt group, if available."""
    if ctx.parent is None:
        return None

    parent_handle = ctx.parent.params.get("handle")
    if isinstance(parent_handle, str):
        return parent_handle

    return None


def _normalize_submolt_name(name: str) -> str:
    normalized_name = name.strip()

    if not normalized_name:
        raise ValueError("Submolt name cannot be empty.")
    if len(normalized_name) < SUBMOLT_NAME_MIN_LENGTH or len(normalized_name) > SUBMOLT_NAME_MAX_LENGTH:
        raise ValueError("Submolt name must be between 2 and 30 characters.")
    if not SUBMOLT_NAME_PATTERN.match(normalized_name):
        raise ValueError("Submolt name must be lowercase alphanumeric with optional hyphens (for example: 'ai-thoughts').")

    return normalized_name


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None

    normalized_value = value.strip()
    return normalized_value or None


def _require_non_empty(value: str, label: str) -> str:
    normalized_value = value.strip()
    if not normalized_value:
        raise ValueError(f"{label} cannot be empty.")
    return normalized_value
