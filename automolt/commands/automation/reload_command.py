"""Command handler for `automolt automation reload`."""

from pathlib import Path

import click
from rich.console import Console

from automolt.commands.agent_targeting import resolve_target_handle
from automolt.constants import CLI_NAME
from automolt.services.automation_service import AutomationService


@click.command("reload")
@click.option(
    "--handle",
    type=str,
    default=None,
    help="Agent handle to reload. Defaults to session active agent.",
)
@click.pass_context
def reload_command(ctx: click.Context, handle: str | None) -> None:
    """Force refresh BEHAVIOR_SUBMOLT.md policy for a target agent."""
    console: Console = ctx.obj["console"]
    base_path: Path = ctx.obj["base_path"]
    automation_service: AutomationService = ctx.obj["automation_service"]

    target_handle = _resolve_target_handle(base_path, console, ctx, handle)
    if target_handle is None:
        return

    try:
        policy = automation_service.reload_submolt_policy(target_handle)
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        ctx.exit(1)
        return

    topic_policy = policy.topic_policy or "none"
    allowed_topics = ", ".join(policy.allowed_topics) if policy.allowed_topics else "none"
    name_prefix = policy.name_prefix or "none"
    console.print(f"[green]Reloaded BEHAVIOR_SUBMOLT.md for '{target_handle}'.[/green]")
    console.print(f"[dim]enabled={policy.enabled} interval_hours={policy.interval_hours} max_creations_per_day={policy.max_creations_per_day}[/dim]")
    console.print(f"[dim]topic_policy={topic_policy} allowed_topics={allowed_topics} name_prefix={name_prefix}[/dim]")


def _resolve_target_handle(
    base_path: Path,
    console: Console,
    ctx: click.Context,
    explicit_handle: str | None,
) -> str | None:
    """Resolve target handle using explicit/session targeting semantics."""
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
