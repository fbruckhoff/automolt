"""Command handler for 'automolt automation list'.

Displays items from the local automation queue, optionally filtered by status.
"""

from datetime import datetime, timezone
from pathlib import Path

import click
from rich.console import Console
from rich.rule import Rule

from automolt.commands.agent_targeting import resolve_target_handle
from automolt.constants import CLI_NAME
from automolt.models.automation import QueueItem
from automolt.services.automation_service import AutomationService

STATUS_CHOICES = ("all", "pending-analysis", "pending-action", "acted")
ORDERED_STATUS_GROUPS = ("pending-analysis", "pending-action", "acted")
STATUS_LABELS = {
    "pending-analysis": "Pending Analysis",
    "pending-action": "Pending Action",
    "acted": "Acted",
}


@click.command(name="list")
@click.option(
    "--handle",
    type=str,
    default=None,
    help="Agent handle to inspect. Defaults to session active agent.",
)
@click.option(
    "--status",
    "status",
    type=click.Choice(STATUS_CHOICES),
    default="all",
    help="Filter items by their processing status.",
)
@click.option(
    "--limit",
    default=None,
    type=click.IntRange(min=1),
    help="Maximum number of items to display. Defaults to all items.",
)
@click.pass_context
def list_command(ctx: click.Context, handle: str | None, status: str, limit: int | None) -> None:
    """List automation queue items for the active agent."""
    console: Console = ctx.obj["console"]
    base_path: Path = ctx.obj["base_path"]
    automation_service: AutomationService = ctx.obj["automation_service"]

    console.print(f"[dim]Tip: Run '{CLI_NAME} automation list --help' for more options.[/dim]")

    active_handle = _resolve_target_handle(base_path, console, ctx, handle)
    if active_handle is None:
        return

    try:
        grouped_items = _fetch_grouped_items(automation_service, active_handle, status, limit)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        ctx.exit(1)
        return

    if _all_groups_empty(grouped_items):
        console.print(f"[yellow]{_build_empty_state_message(status, active_handle)}[/yellow]")
        return

    _print_grouped_items(console, grouped_items)


def _fetch_grouped_items(
    automation_service: AutomationService,
    handle: str,
    status: str,
    limit: int | None,
) -> dict[str, list[QueueItem]]:
    """Fetch queue items grouped by status in display order."""
    if status == "all":
        grouped_items: dict[str, list[QueueItem]] = {}
        remaining = limit

        for group_status in ORDERED_STATUS_GROUPS:
            if remaining is not None and remaining <= 0:
                grouped_items[group_status] = []
                continue

            items = automation_service.list_items(handle, group_status, remaining)
            grouped_items[group_status] = items

            if remaining is not None:
                remaining -= len(items)

        return grouped_items

    return {status: automation_service.list_items(handle, status, limit)}


def _all_groups_empty(grouped_items: dict[str, list[QueueItem]]) -> bool:
    """Return True if all status groups are empty."""
    return all(not items for items in grouped_items.values())


def _build_empty_state_message(status: str, handle: str) -> str:
    """Build an empty-state message for a specific status filter."""
    if status == "all":
        return f"No items found across all status types for agent '{handle}'."

    return f"No items found with status '{status}' for agent '{handle}'."


def _print_grouped_items(console: Console, grouped_items: dict[str, list[QueueItem]]) -> None:
    """Render grouped queue items without using panels."""
    has_printed_group = False

    for status in ORDERED_STATUS_GROUPS:
        items = grouped_items.get(status)
        if not items:
            continue

        if has_printed_group:
            console.print(Rule(style="dim"))

        console.print(f"[bold]{STATUS_LABELS[status]}[/bold]")
        console.print()
        _print_status_items(console, items, STATUS_LABELS[status])
        has_printed_group = True


def _print_status_items(console: Console, items: list[QueueItem], status_label: str) -> None:
    """Print all queue items for one status group."""
    for index, item in enumerate(items):
        _print_queue_item(console, item, status_label)
        if index < len(items) - 1:
            console.print(Rule(style="dim"))


def _resolve_target_handle(
    base_path: Path,
    console: Console,
    ctx: click.Context,
    explicit_handle: str | None,
) -> str | None:
    """Resolve command target handle using session-aware semantics."""
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


def _print_queue_item(console: Console, item: QueueItem, status_label: str) -> None:
    """Print one queue item using the dense non-panel list layout."""
    submolt_name = item.submolt_name or "unknown"
    created_at_relative = _format_relative_time(item.created_at)

    console.print(f"[bold cyan]{item.item_id}[/bold cyan] [dim]({item.item_type})[/dim]")
    console.print(f"[magenta]@{submolt_name}[/magenta] • [dim]Detected {created_at_relative}[/dim]")
    console.print(f"[green]Status: {status_label}[/green]")


def _format_relative_time(created_at: datetime) -> str:
    """Convert a datetime into a simple relative age string."""
    if created_at.tzinfo is None:
        created_utc = created_at.replace(tzinfo=timezone.utc)
    else:
        created_utc = created_at.astimezone(timezone.utc)

    now = datetime.now(timezone.utc)
    delta_seconds = max(int((now - created_utc).total_seconds()), 0)

    if delta_seconds < 60:
        return "just now"

    if delta_seconds < 3600:
        minutes = delta_seconds // 60
        unit = "minute" if minutes == 1 else "minutes"
        return f"{minutes} {unit} ago"

    if delta_seconds < 86400:
        hours = delta_seconds // 3600
        unit = "hour" if hours == 1 else "hours"
        return f"{hours} {unit} ago"

    days = delta_seconds // 86400
    unit = "day" if days == 1 else "days"
    return f"{days} {unit} ago"
