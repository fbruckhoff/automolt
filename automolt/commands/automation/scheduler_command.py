"""Command handlers for automation runtime and monitoring operations."""

from __future__ import annotations

import math
import signal
import time
from datetime import datetime, timezone
from pathlib import Path
from types import FrameType
from typing import Callable, TextIO

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn, TimeRemainingColumn
from rich.status import Status
from rich.table import Table

from automolt.commands.agent_targeting import resolve_target_handle as resolve_agent_target_handle
from automolt.constants import CLI_NAME
from automolt.models.scheduler import AutomationRuntimeStatus, AutomationStatusReport, TickReport, TickResultStatus
from automolt.services.automation_service import HeartbeatEvent, HeartbeatEventType, HeartbeatExecutionOptions
from automolt.services.scheduler_service import SchedulerService


class _HeartbeatMonitorRenderer:
    """Render heartbeat phase events in a compact rich terminal format."""

    def __init__(self, console: Console):
        self._console = console
        self._search_status: Status | None = None
        self._analysis_status: Status | None = None

    def emit(self, event: HeartbeatEvent) -> None:
        """Render one heartbeat event to the terminal."""
        if event.event_type == HeartbeatEventType.SEARCH_STARTED:
            self._start_search(event)
            return

        if event.event_type == HeartbeatEventType.SEARCH_COMPLETED:
            self._stop_search()
            search_query = event.search_query or ""
            self._console.print(f'[green]Search complete[/green] query="{search_query}" new_posts={event.discovered_posts} new_comments={event.discovered_comments}')
            return

        if event.event_type == HeartbeatEventType.ANALYSIS_STARTED:
            self._start_analysis(event)
            return

        if event.event_type == HeartbeatEventType.ANALYSIS_COMPLETED:
            self._stop_analysis()
            dot = "[green]●[/green]" if event.is_relevant else "[red]●[/red]"
            verdict = "passed" if event.is_relevant else "filtered"
            rationale = event.relevance_rationale or "no rationale"
            self._console.print(f"{dot} item={event.item_id} {verdict} rationale={rationale}")
            return

        if event.event_type == HeartbeatEventType.ACTION_DRY_RUN:
            self._console.print("[yellow]--dry active: no post/comment was submitted to Moltbook.[/yellow]")
            self._render_action_payload(event, title="Would post/comment (--dry)", style="yellow")
            return

        if event.event_type == HeartbeatEventType.ACTION_POSTED:
            self._render_action_payload(event, title="Posted automation comment", style="green")

    def close(self) -> None:
        """Stop any active spinner statuses."""
        self._stop_search()
        self._stop_analysis()

    def _start_search(self, event: HeartbeatEvent) -> None:
        self._stop_search()
        search_query = event.search_query or ""
        self._search_status = self._console.status(f'Searching Moltbook for "{search_query}"...')
        self._search_status.start()

    def _start_analysis(self, event: HeartbeatEvent) -> None:
        self._stop_analysis()
        item_label = event.item_id or "unknown"
        self._analysis_status = self._console.status(f"Analyzing item {item_label}...")
        self._analysis_status.start()

    def _stop_search(self) -> None:
        if self._search_status is None:
            return

        self._search_status.stop()
        self._search_status = None

    def _stop_analysis(self) -> None:
        if self._analysis_status is None:
            return

        self._analysis_status.stop()
        self._analysis_status = None

    def _render_action_payload(self, event: HeartbeatEvent, *, title: str, style: str) -> None:
        response_text = event.response_text or ""
        self._console.print(Panel(response_text, title=title, border_style=style, expand=False))
        if event.target_url:
            self._console.print(f"[dim]Target URL:[/dim] {event.target_url}")

        if not event.upvote_requested:
            return

        if event.upvote_target_type and event.upvote_target_id:
            self._console.print(f"[dim]Upvote target:[/dim] {event.upvote_target_type} {event.upvote_target_id}")

        if event.dry_run:
            self._console.print("[yellow]Would upvote this acted item (--dry).[/yellow]")
            return

        if event.upvote_message:
            self._console.print(f"[green]Upvote result:[/green] {event.upvote_message}")
            return

        self._console.print("[yellow]Upvote requested, but no success message was returned.[/yellow]")


@click.command("tick")
@click.option(
    "--handle",
    type=str,
    default=None,
    help="Agent handle to tick immediately. Defaults to session active agent.",
)
@click.option(
    "--dry",
    "dry_run",
    is_flag=True,
    help="Show what would run without executing heartbeat cycles.",
)
@click.option(
    "--respect-schedule",
    is_flag=True,
    hidden=True,
    help="Internal flag used by launchd to keep due-time checks enabled.",
)
@click.pass_context
def tick(ctx: click.Context, handle: str | None, dry_run: bool, respect_schedule: bool) -> None:
    """Run one automation heartbeat cycle for a target agent.

    By default this command immediately triggers a heartbeat cycle for testing.
    Internal launchd-driven ticks set --respect-schedule to keep due-time checks.
    """
    console: Console = ctx.obj["console"]
    base_path: Path = ctx.obj["base_path"]
    scheduler_service: SchedulerService = ctx.obj["scheduler_service"]

    target_handle = _resolve_target_handle(console, base_path, ctx, handle)
    if target_handle is None:
        return

    force = not respect_schedule
    preserve_schedule = force and not dry_run

    try:
        report = scheduler_service.run_tick(
            handle=target_handle,
            force=force,
            dry_run=dry_run,
            preserve_schedule=preserve_schedule,
        )
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        ctx.exit(1)
        return

    if report.processed == 0:
        console.print(f"[yellow]No local agents found. Run '{CLI_NAME} signup' first.[/yellow]")
        return

    _print_tick_report(console, report)


@click.command("start")
@click.option(
    "--handle",
    type=str,
    default=None,
    help="Agent handle to run in foreground. Defaults to session active agent.",
)
@click.option(
    "--background",
    is_flag=True,
    help="Run automation via launchd in the background.",
)
@click.option(
    "--dry",
    is_flag=True,
    help="Simulate actions without posting comments. Generated reply text is still shown.",
)
@click.pass_context
def start(ctx: click.Context, handle: str | None, background: bool, dry: bool) -> None:
    """Start automation for a target agent.

    Foreground mode keeps the process attached to this terminal and streams live
    progress. Background mode installs and loads a LaunchAgent.
    """
    console: Console = ctx.obj["console"]
    base_path: Path = ctx.obj["base_path"]
    scheduler_service: SchedulerService = ctx.obj["scheduler_service"]

    target_handle = _resolve_target_handle(console, base_path, ctx, handle)
    if target_handle is None:
        return

    try:
        scheduler_service.ensure_automation_is_configured(target_handle)
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        ctx.exit(1)
        return

    if background and dry:
        console.print("[red]--dry is supported only in foreground mode.[/red]")
        ctx.exit(1)
        return

    if background:
        _start_background_mode(console, ctx, scheduler_service, target_handle)
        return

    lock_file: TextIO | None = None
    heartbeat_renderer = _HeartbeatMonitorRenderer(console)
    previous_sigint: Callable[[int, FrameType | None], None] | int | None = None
    previous_sigterm: Callable[[int, FrameType | None], None] | int | None = None
    stop_requested = False

    def _handle_termination_signal(signum: int, _frame: FrameType | None) -> None:
        nonlocal stop_requested
        stop_requested = True
        signal_name = signal.Signals(signum).name
        console.print(f"\n[yellow]Received {signal_name}. Stopping scheduler...[/yellow]")

    try:
        lock_file = scheduler_service.start_runtime_scheduler(target_handle)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        ctx.exit(1)
        return

    try:
        initial_report = scheduler_service.run_tick(
            handle=target_handle,
            force=True,
            dry_run=False,
            preserve_schedule=False,
            heartbeat_options=HeartbeatExecutionOptions(
                dry_run_actions=dry,
                observer=heartbeat_renderer.emit,
            ),
        )
        if initial_report.executed == 0:
            _print_tick_report(console, initial_report)
            ctx.exit(1)
            return

        previous_sigint = signal.getsignal(signal.SIGINT)
        previous_sigterm = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGINT, _handle_termination_signal)
        signal.signal(signal.SIGTERM, _handle_termination_signal)

        mode_detail = "dry" if dry else "live"
        console.print(f"[green]Automation started for '{target_handle}' in foreground mode ({mode_detail}).[/green]")
        console.print("[dim]Keep this terminal open. Closing it will terminate automation.[/dim]")
        if dry:
            console.print("[yellow]Dry mode enabled: actions are simulated and never posted.[/yellow]")
        _print_tick_report(console, initial_report)

        _monitor_runtime_loop(
            console=console,
            scheduler_service=scheduler_service,
            handle=target_handle,
            execute_ticks=True,
            dry_run_actions=dry,
            heartbeat_renderer=heartbeat_renderer,
            should_stop=lambda: stop_requested,
        )
    finally:
        if previous_sigint is not None:
            signal.signal(signal.SIGINT, previous_sigint)
        if previous_sigterm is not None:
            signal.signal(signal.SIGTERM, previous_sigterm)

        if lock_file is not None:
            scheduler_service.finalize_runtime_scheduler(target_handle, lock_file)

        heartbeat_renderer.close()

        console.print(f"[green]Automation stopped for '{target_handle}'.[/green]")


@click.command("stop")
@click.option(
    "--handle",
    type=str,
    default=None,
    help="Agent handle to stop. Defaults to session active agent.",
)
@click.option(
    "--background",
    is_flag=True,
    help="Optional compatibility flag. Stop always unloads/removes LaunchAgent if present.",
)
@click.pass_context
def stop(ctx: click.Context, handle: str | None, background: bool) -> None:
    """Stop automation for a target agent."""
    del background  # Flag is accepted for UX symmetry; stop behavior is always comprehensive.

    console: Console = ctx.obj["console"]
    base_path: Path = ctx.obj["base_path"]
    scheduler_service: SchedulerService = ctx.obj["scheduler_service"]

    target_handle = _resolve_target_handle(console, base_path, ctx, handle)
    if target_handle is None:
        return

    try:
        result = scheduler_service.stop_runtime_scheduler(target_handle)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        ctx.exit(1)
        return

    if not result.was_running and not result.launchd_removed and not result.launchd_unloaded:
        console.print(f"[yellow]Automation is already stopped for '{target_handle}'.[/yellow]")
        return

    console.print(f"[green]Automation stopped for '{target_handle}'.[/green]")
    if result.mode is not None:
        console.print(f"[dim]Previous mode:[/dim] {result.mode.value}")
    if result.terminated_pid is not None:
        termination_text = "terminated" if result.process_terminated else "already exited"
        console.print(f"[dim]Process:[/dim] pid {result.terminated_pid} ({termination_text})")
    if result.stopped_at is not None:
        console.print(f"[dim]Stopped at:[/dim] {_format_timestamp(result.stopped_at)}")
    if result.run_duration_seconds is not None:
        console.print(f"[dim]Run duration:[/dim] {_format_duration(result.run_duration_seconds)}")
    console.print(f"[dim]Cycle count:[/dim] {result.cycle_count}")
    if result.launchd_unloaded or result.launchd_removed:
        console.print("[dim]LaunchAgent scheduler was unloaded and removed.[/dim]")


@click.command("status")
@click.option(
    "--handle",
    type=str,
    default=None,
    help="Agent handle to inspect. Defaults to session active agent.",
)
@click.pass_context
def status(ctx: click.Context, handle: str | None) -> None:
    """Show the automation status for a target agent."""
    console: Console = ctx.obj["console"]
    base_path: Path = ctx.obj["base_path"]
    scheduler_service: SchedulerService = ctx.obj["scheduler_service"]

    target_handle = _resolve_target_handle(console, base_path, ctx, handle)
    if target_handle is None:
        return

    try:
        scheduler_service.ensure_automation_is_configured(target_handle)
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        ctx.exit(1)
        return

    report = scheduler_service.get_automation_status(target_handle)
    _print_status_report(console, report)


@click.command("monitor")
@click.option(
    "--handle",
    type=str,
    default=None,
    help="Agent handle to monitor. Defaults to session active agent.",
)
@click.pass_context
def monitor(ctx: click.Context, handle: str | None) -> None:
    """Monitor the automation runloop for a target agent."""
    console: Console = ctx.obj["console"]
    base_path: Path = ctx.obj["base_path"]
    scheduler_service: SchedulerService = ctx.obj["scheduler_service"]

    target_handle = _resolve_target_handle(console, base_path, ctx, handle)
    if target_handle is None:
        return

    report = scheduler_service.get_automation_status(target_handle)
    if report.status != AutomationRuntimeStatus.RUNNING:
        console.print(f"[yellow]Automation is currently not running for '{target_handle}'.[/yellow]")
        _print_status_report(console, report)
        return

    stop_requested = False

    def _handle_termination_signal(signum: int, _frame: FrameType | None) -> None:
        nonlocal stop_requested
        stop_requested = True
        signal_name = signal.Signals(signum).name
        console.print(f"\n[yellow]Received {signal_name}. Stopping monitor...[/yellow]")

    previous_sigint = signal.getsignal(signal.SIGINT)
    previous_sigterm = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGINT, _handle_termination_signal)
    signal.signal(signal.SIGTERM, _handle_termination_signal)

    console.print(f"[green]Monitoring automation for '{target_handle}'.[/green]")

    try:
        _monitor_runtime_loop(
            console=console,
            scheduler_service=scheduler_service,
            handle=target_handle,
            execute_ticks=False,
            dry_run_actions=False,
            heartbeat_renderer=None,
            should_stop=lambda: stop_requested,
        )
    finally:
        signal.signal(signal.SIGINT, previous_sigint)
        signal.signal(signal.SIGTERM, previous_sigterm)


def _resolve_target_handle(
    console: Console,
    base_path: Path,
    ctx: click.Context,
    explicit_handle: str | None,
) -> str | None:
    """Resolve command target handle using session-aware semantics."""

    try:
        target_handle = resolve_agent_target_handle(base_path, explicit_handle)
    except FileNotFoundError:
        console.print(f"[red]No client.json found. Run '{CLI_NAME} init' first.[/red]")
        ctx.exit(1)
        return None
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        ctx.exit(1)
        return None

    if not target_handle:
        console.print(f"[red]No target agent selected. Use '{CLI_NAME} agents', run '{CLI_NAME} signup', or pass --handle.[/red]")
        ctx.exit(1)
        return None

    return target_handle


def _start_background_mode(
    console: Console,
    ctx: click.Context,
    scheduler_service: SchedulerService,
    handle: str,
) -> None:
    """Start automation in background launchd mode and verify with an immediate tick."""
    try:
        start_result = scheduler_service.start_background_scheduler(handle)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        ctx.exit(1)
        return

    try:
        initial_report = scheduler_service.run_tick(
            handle=handle,
            force=True,
            dry_run=False,
            preserve_schedule=False,
        )
    except (FileNotFoundError, ValueError) as exc:
        scheduler_service.stop_runtime_scheduler(handle)
        console.print(f"[red]Background automation failed verification: {exc}[/red]")
        ctx.exit(1)
        return

    if initial_report.executed == 0:
        scheduler_service.stop_runtime_scheduler(handle)
        console.print(f"[red]Background automation failed verification for '{handle}'. No heartbeat cycle was executed.[/red]")
        _print_tick_report(console, initial_report)
        ctx.exit(1)
        return

    console.print(f"[green]Automation started for '{handle}' in background mode.[/green]")
    if start_result.launchd_label is not None:
        console.print(f"[dim]LaunchAgent label:[/dim] {start_result.launchd_label}")
    if start_result.plist_path is not None:
        console.print(f"[dim]Plist path:[/dim] {start_result.plist_path}")
    if start_result.stdout_log_path is not None:
        console.print(f"[dim]Stdout log:[/dim] {start_result.stdout_log_path}")
    if start_result.stderr_log_path is not None:
        console.print(f"[dim]Stderr log:[/dim] {start_result.stderr_log_path}")

    _print_tick_report(console, initial_report)
    console.print()
    console.print(f"Automation will continue in the background until you run '{CLI_NAME} automation stop'.")
    console.print(f"Use '{CLI_NAME} automation monitor' for live countdown updates.")


def _monitor_runtime_loop(
    console: Console,
    scheduler_service: SchedulerService,
    handle: str,
    execute_ticks: bool,
    dry_run_actions: bool,
    heartbeat_renderer: _HeartbeatMonitorRenderer | None,
    should_stop: Callable[[], bool],
) -> None:
    """Monitor runtime state and optionally execute ticks in-process."""
    while not should_stop():
        status = scheduler_service.get_automation_status(handle)
        if status.status != AutomationRuntimeStatus.RUNNING:
            console.print(f"[yellow]Automation is no longer running for '{handle}'.[/yellow]")
            _print_status_report(console, status)
            return

        try:
            scheduler_service.get_effective_interval_seconds(handle)
        except (FileNotFoundError, ValueError) as exc:
            console.print(f"[red]Cannot continue automation monitor: {exc}[/red]")
            return

        next_due_at = status.next_due_at or datetime.now(timezone.utc)
        remaining_seconds = _seconds_until(next_due_at)
        console.print(f"[dim]Mode={status.mode.value if status.mode else 'unknown'} | cycles={status.cycle_count} | next heartbeat at {_format_timestamp(next_due_at)}[/dim]")

        baseline_cycle_count = status.cycle_count
        if remaining_seconds > 0:
            _countdown_until_next_tick(
                console=console,
                seconds=remaining_seconds,
                should_stop=should_stop,
                should_interrupt=lambda: _runtime_state_changed(
                    scheduler_service,
                    handle,
                    baseline_cycle_count,
                ),
            )

        if should_stop():
            return

        refreshed_status = scheduler_service.get_automation_status(handle)
        if refreshed_status.status != AutomationRuntimeStatus.RUNNING:
            continue

        if not execute_ticks:
            continue

        if refreshed_status.cycle_count != baseline_cycle_count:
            continue

        try:
            report = scheduler_service.run_tick(
                handle=handle,
                force=False,
                dry_run=False,
                preserve_schedule=False,
                heartbeat_options=HeartbeatExecutionOptions(
                    dry_run_actions=dry_run_actions,
                    observer=heartbeat_renderer.emit if heartbeat_renderer else None,
                ),
            )
        except (FileNotFoundError, ValueError) as exc:
            console.print(f"[red]Cannot continue automation runtime: {exc}[/red]")
            return

        _print_tick_report(console, report)

        if report.errors > 0:
            console.print("[yellow]Automation tick completed with errors. See details above.[/yellow]")


def _runtime_state_changed(
    scheduler_service: SchedulerService,
    handle: str,
    baseline_cycle_count: int,
) -> bool:
    """Return True when runtime stopped or cycle count advanced."""
    status = scheduler_service.get_automation_status(handle)
    if status.status != AutomationRuntimeStatus.RUNNING:
        return True

    return status.cycle_count != baseline_cycle_count


def _print_status_report(console: Console, report: AutomationStatusReport) -> None:
    """Print an automation status table."""
    table = Table(show_header=False, box=None)
    table.add_row("Agent", report.handle)
    table.add_row("Status", report.status.value)

    if report.status == AutomationRuntimeStatus.RUNNING:
        table.add_row("Mode", report.mode.value if report.mode is not None else "unknown")
        table.add_row("Running since", _format_timestamp(report.started_at))
        table.add_row("Running for", _format_duration(report.run_duration_seconds))
        table.add_row("Heartbeat cycles", str(report.cycle_count))
        table.add_row("Last cycle at", _format_timestamp(report.last_cycle_at))
        table.add_row("Next due at", _format_timestamp(report.next_due_at))
    else:
        if report.stopped_at is not None:
            table.add_row("Stopped at", _format_timestamp(report.stopped_at))
        if report.run_duration_seconds is not None:
            table.add_row("Last run duration", _format_duration(report.run_duration_seconds))
        table.add_row("Last cycle count", str(report.cycle_count))

    console.print(table)


def _resolve_startup_error_message(report: TickReport) -> str | None:
    """Return a high-signal startup error message when one is available."""
    for result in report.results:
        if result.status != TickResultStatus.ERROR:
            continue

        if result.reason == "provider-auth-failed":
            return result.error or "Invalid OpenAI API key."

        if result.reason == "missing-provider-config":
            return result.error or "Missing OpenAI API key."

    return None


def _print_tick_report(console: Console, report: TickReport) -> None:
    """Print a compact scheduler tick summary."""
    if not report.results:
        return

    table = Table(show_header=True)
    table.add_column("Handle")
    table.add_column("Status")
    table.add_column("Reason")

    for result in report.results:
        if result.status == TickResultStatus.ERROR:
            status_display = "[red]failed[/red]"
            reason = result.error or result.reason or "unknown"
            reason = f"[red]{reason}[/red]"
        elif result.status == TickResultStatus.EXECUTED:
            status_display = "[green]completed[/green]"
            reason = result.reason or ""
        elif result.status == TickResultStatus.WOULD_EXECUTE:
            status_display = "[cyan]completed (dry run)[/cyan]"
            reason = result.reason or ""
        else:
            status_display = "[yellow]skipped[/yellow]"
            reason = result.reason or ""

        if result.next_due_at is not None and result.status == TickResultStatus.SKIPPED:
            reason = f"{reason} (next: {result.next_due_at.strftime('%H:%M:%S UTC')})" if reason else reason

        table.add_row(result.handle, status_display, reason)

    console.print(table)


def _countdown_until_next_tick(
    console: Console,
    seconds: int,
    should_stop: Callable[[], bool],
    should_interrupt: Callable[[], bool] | None = None,
) -> None:
    """Show a per-second countdown until the next heartbeat tick."""
    safe_seconds = max(seconds, 1)

    with Progress(
        TextColumn("[dim]Next heartbeat in[/dim]"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("countdown", total=safe_seconds)

        while not progress.finished:
            if should_stop():
                break
            if should_interrupt is not None and should_interrupt():
                break
            time.sleep(1)
            progress.advance(task, 1)


def _format_timestamp(value: datetime | None) -> str:
    """Render timestamps in UTC for terminal output."""
    if value is None:
        return "unknown"

    utc_value = value.astimezone(timezone.utc) if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return utc_value.strftime("%Y-%m-%d %H:%M:%S UTC")


def _format_duration(seconds: float | None) -> str:
    """Render elapsed seconds as a compact human-readable duration."""
    if seconds is None:
        return "unknown"

    total_seconds = max(int(seconds), 0)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _seconds_until(target: datetime) -> int:
    """Return non-negative whole seconds remaining until target time."""
    now = datetime.now(timezone.utc)
    normalized_target = target.astimezone(timezone.utc) if target.tzinfo is not None else target.replace(tzinfo=timezone.utc)
    return max(math.ceil((normalized_target - now).total_seconds()), 0)
