"""Business logic for automation scheduler orchestration and lifecycle."""

from __future__ import annotations

import json
import logging
import os
import re
import signal
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TextIO

from automolt.constants import CLI_NAME
from automolt.models.agent import AgentConfig
from automolt.models.scheduler import (
    AutomationRunMode,
    AutomationRuntimeStatus,
    AutomationStatusReport,
    TickAgentResult,
    TickReport,
    TickResultStatus,
)
from automolt.persistence import agent_store, scheduler_store
from automolt.persistence.scheduler_store import RuntimeSchedulerState
from automolt.services.automation_service import AutomationService, HeartbeatExecutionOptions

logger = logging.getLogger(__name__)

MINIMUM_INTERVAL_SECONDS = 60
HANDLE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,50}$")
INVALID_OPENAI_API_KEY_MESSAGE = f"Invalid OpenAI API key. Run '{CLI_NAME} automation setup' to update your provider config."
MISSING_OPENAI_API_KEY_MESSAGE = f"Missing OpenAI API key. Run '{CLI_NAME} automation setup' to complete automation setup."


def _map_runtime_value_error(exc: ValueError) -> tuple[str, str]:
    """Map expected runtime ValueError failures to stable reason/message pairs."""
    raw_message = str(exc).strip()
    if not raw_message:
        return "execution-failed", "Automation heartbeat execution failed."

    normalized = raw_message.lower()
    if "openai authentication failed" in normalized:
        return "provider-auth-failed", INVALID_OPENAI_API_KEY_MESSAGE

    if "openai api key is required" in normalized:
        return "missing-provider-config", MISSING_OPENAI_API_KEY_MESSAGE

    return "execution-failed", raw_message


@dataclass(frozen=True)
class RuntimeStopResult:
    """Result of stopping automation runtime for one handle."""

    handle: str
    was_running: bool
    mode: AutomationRunMode | None
    stopped_at: datetime | None
    run_duration_seconds: float | None
    cycle_count: int
    terminated_pid: int | None
    process_terminated: bool
    launchd_unloaded: bool
    launchd_removed: bool


@dataclass(frozen=True)
class RuntimeStartResult:
    """Result of starting automation runtime for one handle."""

    handle: str
    mode: AutomationRunMode
    started_at: datetime
    launchd_label: str | None = None
    plist_path: Path | None = None
    stdout_log_path: Path | None = None
    stderr_log_path: Path | None = None


@dataclass(frozen=True)
class LaunchdInstallResult:
    """Result of installing a launchd LaunchAgent scheduler."""

    handle: str
    label: str
    plist_path: Path
    interval_seconds: int
    program_arguments: list[str]
    stdout_log_path: Path
    stderr_log_path: Path


@dataclass(frozen=True)
class LaunchdStatusResult:
    """Resolved status details for a launchd LaunchAgent scheduler."""

    label: str
    plist_path: Path
    exists: bool
    loaded: bool = False
    interval_seconds: int | None = None
    program_arguments: list[str] | None = None
    stdout_log_path: Path | None = None
    stderr_log_path: Path | None = None


class SchedulerService:
    """Service responsible for scheduler tick orchestration and lifecycle controls."""

    def __init__(self, automation_service: AutomationService, base_path: Path):
        self._automation_service = automation_service
        self._base_path = base_path

    def validate_handle_exists(self, handle: str) -> str:
        """Validate one handle value and ensure local agent config exists."""
        normalized_handle = self._validate_handle(handle)
        if not agent_store.agent_exists_locally(self._base_path, normalized_handle):
            raise FileNotFoundError(f"Agent '{normalized_handle}' not found locally.")

        return normalized_handle

    def is_due(self, config: AgentConfig, now: datetime) -> bool:
        """Return whether an agent automation cycle is currently due.

        Args:
            config: Agent configuration loaded from disk.
            now: Current timestamp in UTC.

        Returns:
            True if the scheduler should execute for this agent, otherwise False.
        """
        due, _, _ = self.evaluate_due(config, now)
        return due

    def evaluate_due(self, config: AgentConfig, now: datetime) -> tuple[bool, str | None, datetime | None]:
        """Evaluate due state with an explanatory reason and next due timestamp."""
        if not config.automation.enabled:
            return False, "automation-disabled", None

        if not config.agent.api_key:
            return False, "missing-api-key", None

        last_heartbeat_at = config.automation.last_heartbeat_at
        if last_heartbeat_at is None:
            return True, "never-ran", now

        if last_heartbeat_at.tzinfo is None:
            last_heartbeat_at = last_heartbeat_at.replace(tzinfo=timezone.utc)
        else:
            last_heartbeat_at = last_heartbeat_at.astimezone(timezone.utc)

        interval_seconds = max(config.automation.interval_seconds, MINIMUM_INTERVAL_SECONDS)
        next_due_at = last_heartbeat_at + timedelta(seconds=interval_seconds)
        if now >= next_due_at:
            return True, "interval-elapsed", next_due_at

        return False, "not-due", next_due_at

    def run_tick(
        self,
        handle: str,
        force: bool,
        dry_run: bool,
        preserve_schedule: bool = False,
        heartbeat_options: HeartbeatExecutionOptions | None = None,
    ) -> TickReport:
        """Execute one scheduler tick for a single validated handle.

        Args:
            handle: Specific agent handle to process.
            force: If True, skip due-time checks.
            dry_run: If True, compute actions without executing heartbeat cycles.
            preserve_schedule: If True, restore last_heartbeat_at after execution
                when the handle is currently running automation. This allows manual
                testing ticks without shifting scheduler cadence.
            heartbeat_options: Optional per-cycle execution options passed to
                AutomationService.execute_heartbeat_cycle().

        Returns:
            A structured TickReport for one target handle.

        Raises:
            ValueError: If handle validation fails.
            FileNotFoundError: If handle does not exist locally.
        """
        started_at = datetime.now(timezone.utc)
        candidate_handle = self.validate_handle_exists(handle)
        candidate_handles = [candidate_handle]

        report = TickReport(
            started_at=started_at,
            completed_at=started_at,
            requested_handle=handle,
            force=force,
            dry_run=dry_run,
        )

        for candidate_handle in candidate_handles:
            report.processed += 1

            try:
                config = agent_store.load_agent_config(self._base_path, candidate_handle)
            except (FileNotFoundError, ValueError) as exc:
                report.errors += 1
                report.results.append(
                    TickAgentResult(
                        handle=candidate_handle,
                        status=TickResultStatus.ERROR,
                        reason="load-config-failed",
                        error=str(exc),
                    )
                )
                logger.exception("Scheduler tick failed to load config for handle '%s'.", candidate_handle)
                continue

            now = datetime.now(timezone.utc)
            due, due_reason, next_due_at = self.evaluate_due(config, now)

            if due_reason in {"automation-disabled", "missing-api-key"}:
                report.skipped += 1
                report.results.append(
                    TickAgentResult(
                        handle=candidate_handle,
                        status=TickResultStatus.SKIPPED,
                        reason=due_reason,
                        next_due_at=next_due_at,
                    )
                )
                continue

            if not force and not due:
                report.skipped += 1
                report.results.append(
                    TickAgentResult(
                        handle=candidate_handle,
                        status=TickResultStatus.SKIPPED,
                        reason=due_reason,
                        next_due_at=next_due_at,
                    )
                )
                continue

            try:
                self._automation_service.validate_runtime_llm_prerequisites(config)
            except ValueError as exc:
                report.errors += 1
                report.results.append(
                    TickAgentResult(
                        handle=candidate_handle,
                        status=TickResultStatus.ERROR,
                        reason="setup-incomplete",
                        error=str(exc),
                    )
                )
                logger.warning(
                    "Scheduler tick failed for '%s' due to incomplete automation setup: %s",
                    candidate_handle,
                    exc,
                )
                continue

            if dry_run:
                report.results.append(
                    TickAgentResult(
                        handle=candidate_handle,
                        status=TickResultStatus.WOULD_EXECUTE,
                        reason="forced" if force else due_reason,
                        next_due_at=next_due_at,
                    )
                )
                continue

            running_before_cycle = False
            previous_last_heartbeat_at = config.automation.last_heartbeat_at
            if preserve_schedule:
                running_before_cycle = self.is_automation_running(candidate_handle)

            try:
                self._automation_service.execute_heartbeat_cycle(candidate_handle, options=heartbeat_options)
            except ValueError as exc:
                reason_code, user_message = _map_runtime_value_error(exc)
                report.errors += 1
                report.results.append(
                    TickAgentResult(
                        handle=candidate_handle,
                        status=TickResultStatus.ERROR,
                        reason=reason_code,
                        error=user_message,
                    )
                )
                if reason_code not in {"provider-auth-failed", "missing-provider-config"}:
                    logger.warning(
                        "Scheduler heartbeat execution failed for handle '%s': %s",
                        candidate_handle,
                        user_message,
                    )
                continue
            except Exception as exc:  # noqa: BLE001
                report.errors += 1
                report.results.append(
                    TickAgentResult(
                        handle=candidate_handle,
                        status=TickResultStatus.ERROR,
                        reason="execution-failed",
                        error=str(exc),
                    )
                )
                logger.exception("Scheduler heartbeat execution failed for handle '%s'.", candidate_handle)
                continue

            if preserve_schedule and running_before_cycle:
                try:
                    self._restore_last_heartbeat_at(candidate_handle, previous_last_heartbeat_at)
                except FileNotFoundError, ValueError:
                    logger.exception(
                        "Failed to restore last_heartbeat_at for manual tick on '%s'.",
                        candidate_handle,
                    )

            self._increment_cycle_count_if_running(candidate_handle)

            report.executed += 1
            report.results.append(
                TickAgentResult(
                    handle=candidate_handle,
                    status=TickResultStatus.EXECUTED,
                    reason="forced" if force else due_reason,
                )
            )

        report.completed_at = datetime.now(timezone.utc)
        return report

    def get_effective_interval_seconds(self, handle: str) -> int:
        """Return the effective interval for a handle, enforcing safety floor."""
        normalized_handle = self._validate_handle(handle)
        config = agent_store.load_agent_config(self._base_path, normalized_handle)
        return max(config.automation.interval_seconds, MINIMUM_INTERVAL_SECONDS)

    def ensure_automation_is_configured(self, handle: str) -> AgentConfig:
        """Validate that automation setup has completed for a handle."""
        normalized_handle = self._validate_handle(handle)
        if not agent_store.agent_exists_locally(self._base_path, normalized_handle):
            raise FileNotFoundError(f"Agent '{normalized_handle}' not found locally.")

        config = agent_store.load_agent_config(self._base_path, normalized_handle)
        if not config.automation.enabled or not config.automation.search_query:
            raise ValueError(f"Automation is not configured for '{normalized_handle}'. Run '{CLI_NAME} automation setup' first.")

        if not config.agent.api_key:
            raise ValueError(f"Agent '{normalized_handle}' is missing an API key. Run '{CLI_NAME} signup' again for this agent.")

        self._automation_service.validate_runtime_llm_prerequisites(config)

        return config

    def get_automation_status(self, handle: str) -> AutomationStatusReport:
        """Return runtime status details for one handle."""
        normalized_handle = self._validate_handle(handle)
        state = self._read_runtime_state_safe(normalized_handle)
        if state is None:
            return AutomationStatusReport(handle=normalized_handle, status=AutomationRuntimeStatus.STOPPED)

        state = self._reconcile_runtime_state(normalized_handle, state)
        run_status = AutomationRuntimeStatus.RUNNING if state.running else AutomationRuntimeStatus.STOPPED
        mode = self._parse_run_mode(state.mode)

        run_duration_seconds = state.last_run_duration_seconds
        if state.running and state.started_at is not None:
            started_at = self._normalize_datetime(state.started_at)
            if started_at is not None:
                run_duration_seconds = max((datetime.now(timezone.utc) - started_at).total_seconds(), 0.0)

        next_due_at: datetime | None = None
        if state.running:
            next_due_at = self._compute_next_due_at(normalized_handle, state)

        return AutomationStatusReport(
            handle=normalized_handle,
            status=run_status,
            mode=mode,
            started_at=state.started_at,
            stopped_at=state.stopped_at,
            run_duration_seconds=run_duration_seconds,
            cycle_count=state.cycle_count,
            last_cycle_at=state.last_cycle_at,
            next_due_at=next_due_at,
        )

    def is_automation_running(self, handle: str) -> bool:
        """Return whether automation is currently running for one handle."""
        status = self.get_automation_status(handle)
        return status.status == AutomationRuntimeStatus.RUNNING

    def start_runtime_scheduler(self, handle: str) -> TextIO:
        """Prepare runtime state and lock for a foreground scheduler process."""
        normalized_handle = self._validate_handle(handle)
        self.ensure_automation_is_configured(normalized_handle)

        if self.is_automation_running(normalized_handle):
            raise RuntimeError(f"Automation is already running for '{normalized_handle}'.")

        launchd_label = self.default_launchd_label(normalized_handle)
        try:
            if scheduler_store.is_launch_agent_loaded(launchd_label):
                raise RuntimeError(f"Automation is already running for '{normalized_handle}'.")
        except FileNotFoundError:
            # Foreground start can still proceed when launchctl is unavailable.
            pass

        lock_file = scheduler_store.acquire_runtime_lock(self._base_path, normalized_handle)
        if lock_file is None:
            raise RuntimeError(f"Automation is already running for '{normalized_handle}'.")

        state = RuntimeSchedulerState(
            handle=normalized_handle,
            mode=AutomationRunMode.FOREGROUND.value,
            running=True,
            pid=os.getpid(),
            started_at=datetime.now(timezone.utc),
            stopped_at=None,
            last_run_duration_seconds=None,
            cycle_count=0,
            last_cycle_at=None,
            launchd_label=self.default_launchd_label(normalized_handle),
        )
        scheduler_store.write_runtime_state(self._base_path, state)
        return lock_file

    def start_background_scheduler(self, handle: str) -> RuntimeStartResult:
        """Start background automation via launchd for one handle."""
        normalized_handle = self._validate_handle(handle)
        self.ensure_automation_is_configured(normalized_handle)

        if self.is_automation_running(normalized_handle):
            raise RuntimeError(f"Automation is already running for '{normalized_handle}'.")

        resolved_label = self.default_launchd_label(normalized_handle)
        try:
            if scheduler_store.is_launch_agent_loaded(resolved_label):
                raise RuntimeError(f"Automation is already running for '{normalized_handle}'.")
        except FileNotFoundError as exc:
            raise RuntimeError("launchctl is not available on this system.") from exc

        # Launchd triggers are a polling mechanism; due-time enforcement still
        # happens in run_tick(). Using the full heartbeat interval here can
        # cause missed cycles when launchd fires slightly before due time.
        launchd_result = self.install_launchd_scheduler(
            handle=normalized_handle,
            interval_seconds=MINIMUM_INTERVAL_SECONDS,
            label=resolved_label,
            overwrite=True,
        )

        try:
            scheduler_store.load_launch_agent(launchd_result.plist_path)
        except FileNotFoundError as exc:
            raise RuntimeError("launchctl is not available on this system.") from exc

        verification = self.get_launchd_scheduler_status(launchd_result.label)
        if not verification.exists or not verification.loaded:
            raise RuntimeError(f"LaunchAgent installation verification failed for '{normalized_handle}'.")

        started_at = datetime.now(timezone.utc)
        state = RuntimeSchedulerState(
            handle=normalized_handle,
            mode=AutomationRunMode.BACKGROUND.value,
            running=True,
            pid=None,
            started_at=started_at,
            stopped_at=None,
            last_run_duration_seconds=None,
            cycle_count=0,
            last_cycle_at=None,
            launchd_label=launchd_result.label,
        )
        scheduler_store.write_runtime_state(self._base_path, state)

        return RuntimeStartResult(
            handle=normalized_handle,
            mode=AutomationRunMode.BACKGROUND,
            started_at=started_at,
            launchd_label=launchd_result.label,
            plist_path=launchd_result.plist_path,
            stdout_log_path=launchd_result.stdout_log_path,
            stderr_log_path=launchd_result.stderr_log_path,
        )

    def finalize_runtime_scheduler(self, handle: str, lock_file: TextIO) -> None:
        """Cleanup runtime scheduler state and release lock for a handle."""
        normalized_handle = self._validate_handle(handle)
        stopped_at = datetime.now(timezone.utc)

        try:
            state = self._read_runtime_state_safe(normalized_handle)
            if state is None:
                state = RuntimeSchedulerState(
                    handle=normalized_handle,
                    mode=AutomationRunMode.FOREGROUND.value,
                    running=False,
                    pid=None,
                    started_at=None,
                    stopped_at=stopped_at,
                    last_run_duration_seconds=None,
                    cycle_count=0,
                    last_cycle_at=None,
                    launchd_label=self.default_launchd_label(normalized_handle),
                )
                scheduler_store.write_runtime_state(self._base_path, state)
            elif state.running:
                self._write_stopped_state(normalized_handle, state, stopped_at)
        finally:
            scheduler_store.release_runtime_lock(lock_file)

    def stop_runtime_scheduler(self, handle: str) -> RuntimeStopResult:
        """Stop automation runtime and uninstall any launchd scheduler for one handle."""
        normalized_handle = self._validate_handle(handle)
        state = self._read_runtime_state_safe(normalized_handle)
        if state is not None:
            state = self._reconcile_runtime_state(normalized_handle, state)

        terminated_pid: int | None = None
        process_terminated = False
        was_running = state.running if state is not None else False
        run_mode = self._parse_run_mode(state.mode) if state is not None else None

        if state is not None and state.running and run_mode == AutomationRunMode.FOREGROUND and state.pid is not None:
            terminated_pid = state.pid
            if terminated_pid == os.getpid():
                process_terminated = False
            elif scheduler_store.is_process_running(terminated_pid):
                process_terminated = self._terminate_process(terminated_pid)

        launchd_label = self.default_launchd_label(normalized_handle)
        if state is not None and state.launchd_label:
            launchd_label = state.launchd_label

        launchd_unloaded = False
        launchd_removed = False
        plist_path = scheduler_store.get_launch_agent_path(launchd_label)
        if plist_path.exists():
            try:
                scheduler_store.unload_launch_agent(plist_path)
                launchd_unloaded = True
            except RuntimeError:
                logger.exception("Failed to unload LaunchAgent '%s'.", launchd_label)

            launchd_removed = scheduler_store.remove_launch_agent_plist(plist_path)

        stopped_at: datetime | None = None
        run_duration_seconds: float | None = None
        cycle_count = state.cycle_count if state is not None else 0

        if state is not None:
            if state.running or launchd_unloaded or launchd_removed:
                stopped_state = self._write_stopped_state(
                    normalized_handle,
                    state,
                    datetime.now(timezone.utc),
                    launchd_label=launchd_label,
                )
                stopped_at = stopped_state.stopped_at
                run_duration_seconds = stopped_state.last_run_duration_seconds
                run_mode = self._parse_run_mode(stopped_state.mode)
                cycle_count = stopped_state.cycle_count
            else:
                stopped_at = state.stopped_at
                run_duration_seconds = state.last_run_duration_seconds
        elif launchd_unloaded or launchd_removed:
            stopped_at = datetime.now(timezone.utc)
            run_mode = AutomationRunMode.BACKGROUND
            scheduler_store.write_runtime_state(
                self._base_path,
                RuntimeSchedulerState(
                    handle=normalized_handle,
                    mode=AutomationRunMode.BACKGROUND.value,
                    running=False,
                    pid=None,
                    started_at=None,
                    stopped_at=stopped_at,
                    last_run_duration_seconds=None,
                    cycle_count=0,
                    last_cycle_at=None,
                    launchd_label=launchd_label,
                ),
            )

        return RuntimeStopResult(
            handle=normalized_handle,
            was_running=was_running,
            mode=run_mode,
            stopped_at=stopped_at,
            run_duration_seconds=run_duration_seconds,
            cycle_count=cycle_count,
            terminated_pid=terminated_pid,
            process_terminated=process_terminated,
            launchd_unloaded=launchd_unloaded,
            launchd_removed=launchd_removed,
        )

    def default_launchd_label(self, handle: str) -> str:
        """Build a deterministic default launchd label for a handle."""
        normalized_handle = self._validate_handle(handle)
        return f"{scheduler_store.DEFAULT_LAUNCHD_LABEL_PREFIX}.{normalized_handle.lower()}"

    def install_launchd_scheduler(
        self,
        handle: str,
        interval_seconds: int,
        label: str | None,
        overwrite: bool,
    ) -> LaunchdInstallResult:
        """Install a launchd plist for periodic tick execution."""
        normalized_handle = self._validate_handle(handle)
        if not agent_store.agent_exists_locally(self._base_path, normalized_handle):
            raise FileNotFoundError(f"Agent '{normalized_handle}' not found locally.")

        resolved_label = label.strip() if label else self.default_launchd_label(normalized_handle)
        resolved_interval = max(interval_seconds, MINIMUM_INTERVAL_SECONDS)

        log_dir = scheduler_store.ensure_scheduler_log_directory(self._base_path, normalized_handle)
        stdout_log_path = log_dir / f"{resolved_label}.out.log"
        stderr_log_path = log_dir / f"{resolved_label}.err.log"

        program_arguments = scheduler_store.resolve_cli_program_arguments()
        program_arguments.extend(["automation", "tick", "--handle", normalized_handle, "--respect-schedule"])

        plist_bytes = scheduler_store.build_launch_agent_plist_bytes(
            label=resolved_label,
            start_interval_seconds=resolved_interval,
            program_arguments=program_arguments,
            working_directory=self._base_path,
            stdout_log_path=stdout_log_path,
            stderr_log_path=stderr_log_path,
        )

        plist_path = scheduler_store.get_launch_agent_path(resolved_label)
        scheduler_store.write_launch_agent_plist(plist_path, plist_bytes, overwrite=overwrite)

        return LaunchdInstallResult(
            handle=normalized_handle,
            label=resolved_label,
            plist_path=plist_path,
            interval_seconds=resolved_interval,
            program_arguments=program_arguments,
            stdout_log_path=stdout_log_path,
            stderr_log_path=stderr_log_path,
        )

    def uninstall_launchd_scheduler(self, label: str) -> bool:
        """Remove a launchd plist for a scheduler label."""
        resolved_label = label.strip()
        plist_path = scheduler_store.get_launch_agent_path(resolved_label)
        return scheduler_store.remove_launch_agent_plist(plist_path)

    def get_launchd_scheduler_status(self, label: str) -> LaunchdStatusResult:
        """Return status information for a launchd scheduler label."""
        resolved_label = label.strip()
        plist_path = scheduler_store.get_launch_agent_path(resolved_label)
        plist_data = scheduler_store.read_launch_agent_plist(plist_path)

        if plist_data is None:
            return LaunchdStatusResult(label=resolved_label, plist_path=plist_path, exists=False)

        loaded = False
        try:
            loaded = scheduler_store.is_launch_agent_loaded(resolved_label)
        except FileNotFoundError:
            loaded = False

        program_arguments_raw = plist_data.get("ProgramArguments")
        if isinstance(program_arguments_raw, list):
            program_arguments = [str(part) for part in program_arguments_raw]
        else:
            program_arguments = None

        stdout_raw = plist_data.get("StandardOutPath")
        stderr_raw = plist_data.get("StandardErrorPath")

        return LaunchdStatusResult(
            label=resolved_label,
            plist_path=plist_path,
            exists=True,
            loaded=loaded,
            interval_seconds=int(plist_data.get("StartInterval")) if plist_data.get("StartInterval") is not None else None,
            program_arguments=program_arguments,
            stdout_log_path=Path(stdout_raw) if isinstance(stdout_raw, str) else None,
            stderr_log_path=Path(stderr_raw) if isinstance(stderr_raw, str) else None,
        )

    def _read_runtime_state_safe(self, handle: str) -> RuntimeSchedulerState | None:
        """Read runtime state and clear corrupted payloads."""
        try:
            return scheduler_store.read_runtime_state(self._base_path, handle)
        except json.JSONDecodeError, KeyError, TypeError, ValueError:
            scheduler_store.clear_runtime_state(self._base_path, handle)
            return None

    def _reconcile_runtime_state(self, handle: str, state: RuntimeSchedulerState) -> RuntimeSchedulerState:
        """Normalize stale runtime state to stopped when backing process is gone."""
        if not state.running:
            return state

        mode = self._parse_run_mode(state.mode)
        now = datetime.now(timezone.utc)

        if mode == AutomationRunMode.FOREGROUND:
            if state.pid is None or not scheduler_store.is_process_running(state.pid):
                return self._write_stopped_state(handle, state, now)
            return state

        if mode == AutomationRunMode.BACKGROUND:
            launchd_label = state.launchd_label or self.default_launchd_label(handle)
            launchd_status = self.get_launchd_scheduler_status(launchd_label)
            if not launchd_status.exists or not launchd_status.loaded:
                return self._write_stopped_state(handle, state, now, launchd_label=launchd_label)

            if state.launchd_label != launchd_label:
                synced_state = RuntimeSchedulerState(
                    handle=state.handle,
                    mode=state.mode,
                    running=state.running,
                    pid=state.pid,
                    started_at=state.started_at,
                    stopped_at=state.stopped_at,
                    last_run_duration_seconds=state.last_run_duration_seconds,
                    cycle_count=state.cycle_count,
                    last_cycle_at=state.last_cycle_at,
                    launchd_label=launchd_label,
                )
                scheduler_store.write_runtime_state(self._base_path, synced_state)
                return synced_state

            return state

        return state

    def _write_stopped_state(
        self,
        handle: str,
        state: RuntimeSchedulerState,
        stopped_at: datetime,
        launchd_label: str | None = None,
    ) -> RuntimeSchedulerState:
        """Persist stopped runtime state and return the stored object."""
        normalized_started_at = self._normalize_datetime(state.started_at)
        normalized_last_cycle_at = self._normalize_datetime(state.last_cycle_at)

        run_duration_seconds: float | None = state.last_run_duration_seconds
        if normalized_started_at is not None:
            run_duration_seconds = max((stopped_at - normalized_started_at).total_seconds(), 0.0)

        stopped_state = RuntimeSchedulerState(
            handle=handle,
            mode=state.mode,
            running=False,
            pid=None,
            started_at=normalized_started_at,
            stopped_at=stopped_at,
            last_run_duration_seconds=run_duration_seconds,
            cycle_count=state.cycle_count,
            last_cycle_at=normalized_last_cycle_at,
            launchd_label=launchd_label if launchd_label is not None else state.launchd_label,
        )
        scheduler_store.write_runtime_state(self._base_path, stopped_state)
        return stopped_state

    def _compute_next_due_at(self, handle: str, state: RuntimeSchedulerState) -> datetime | None:
        """Compute the next expected due time for a running automation state."""
        if not state.running:
            return None

        if state.last_cycle_at is None:
            return datetime.now(timezone.utc)

        try:
            interval_seconds = self.get_effective_interval_seconds(handle)
        except FileNotFoundError, ValueError:
            return None

        last_cycle_at = self._normalize_datetime(state.last_cycle_at)
        if last_cycle_at is None:
            return None

        return last_cycle_at + timedelta(seconds=interval_seconds)

    def _increment_cycle_count_if_running(self, handle: str) -> None:
        """Increment in-run cycle count for a handle if runtime is active."""
        state = self._read_runtime_state_safe(handle)
        if state is None:
            return

        state = self._reconcile_runtime_state(handle, state)
        if not state.running:
            return

        updated_state = RuntimeSchedulerState(
            handle=state.handle,
            mode=state.mode,
            running=state.running,
            pid=state.pid,
            started_at=state.started_at,
            stopped_at=state.stopped_at,
            last_run_duration_seconds=state.last_run_duration_seconds,
            cycle_count=state.cycle_count + 1,
            last_cycle_at=datetime.now(timezone.utc),
            launchd_label=state.launchd_label,
        )
        scheduler_store.write_runtime_state(self._base_path, updated_state)

    def _restore_last_heartbeat_at(self, handle: str, previous_last_heartbeat_at: datetime | None) -> None:
        """Restore last_heartbeat_at after manual tick to preserve scheduler cadence."""
        config = agent_store.load_agent_config(self._base_path, handle)
        config.automation.last_heartbeat_at = previous_last_heartbeat_at
        agent_store.save_agent_config(self._base_path, config)

    def _terminate_process(self, pid: int) -> bool:
        """Terminate a process with TERM then KILL fallback."""
        if not scheduler_store.is_process_running(pid):
            return False

        try:
            scheduler_store.terminate_process(pid, signal.SIGTERM)
        except ProcessLookupError:
            logger.debug("Process '%s' exited before SIGTERM.", pid)
            return True

        terminated = scheduler_store.wait_for_process_exit(pid)
        if terminated:
            return True

        try:
            scheduler_store.terminate_process(pid, signal.SIGKILL)
        except ProcessLookupError:
            logger.debug("Process '%s' exited before SIGKILL.", pid)
            return True

        return scheduler_store.wait_for_process_exit(pid)

    def _parse_run_mode(self, mode: str) -> AutomationRunMode | None:
        """Parse runtime mode string into enum if known."""
        try:
            return AutomationRunMode(mode)
        except ValueError:
            return None

    def _normalize_datetime(self, value: datetime | None) -> datetime | None:
        """Normalize datetimes to UTC."""
        if value is None:
            return None

        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)

        return value.astimezone(timezone.utc)

    def _validate_handle(self, handle: str) -> str:
        """Validate and normalize a scheduler handle value."""
        normalized_handle = handle.strip()
        if not normalized_handle:
            raise ValueError("Handle cannot be empty.")

        if not HANDLE_PATTERN.fullmatch(normalized_handle):
            raise ValueError("Handle contains invalid characters. Allowed: letters, numbers, underscore, and hyphen.")

        return normalized_handle
