"""Persistence helpers for scheduler runtime state and launchd plist files."""

from __future__ import annotations

import fcntl
import json
import os
import plistlib
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

from automolt.constants import CLI_NAME
from automolt.persistence import agent_store

RUNTIME_STATE_FILENAME = "scheduler_state.json"
RUNTIME_LOCK_FILENAME = "scheduler.lock"
DEFAULT_LAUNCHD_LABEL_PREFIX = "com.automolt.automation"


def _scheduler_runtime_dir(base_path: Path, handle: str) -> Path:
    """Return the scheduler runtime directory for one handle."""
    return agent_store.get_agent_dir(base_path, handle) / "scheduler"


def get_runtime_state_path(base_path: Path, handle: str) -> Path:
    """Return the scheduler runtime state file path for one handle."""
    return _scheduler_runtime_dir(base_path, handle) / RUNTIME_STATE_FILENAME


def get_runtime_lock_path(base_path: Path, handle: str) -> Path:
    """Return the scheduler runtime lock file path for one handle."""
    return _scheduler_runtime_dir(base_path, handle) / RUNTIME_LOCK_FILENAME


@dataclass(frozen=True)
class RuntimeSchedulerState:
    """Runtime state data persisted for one automation handle."""

    handle: str
    mode: str
    running: bool
    pid: int | None
    started_at: datetime | None
    stopped_at: datetime | None
    last_run_duration_seconds: float | None
    cycle_count: int
    last_cycle_at: datetime | None
    launchd_label: str | None


def _serialize_datetime(value: datetime | None) -> str | None:
    """Serialize a datetime to UTC ISO-8601 string."""
    if value is None:
        return None

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)

    return value.isoformat()


def _parse_datetime(value: Any) -> datetime | None:
    """Parse an ISO-8601 datetime payload field into UTC datetime."""
    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError("Datetime value must be an ISO-8601 string.")

    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)

    return parsed


def read_runtime_state(base_path: Path, handle: str) -> RuntimeSchedulerState | None:
    """Read scheduler runtime state for a handle if present."""
    state_path = get_runtime_state_path(base_path, handle)
    if not state_path.exists():
        return None

    raw = json.loads(state_path.read_text(encoding="utf-8"))
    pid_raw = raw.get("pid")
    if pid_raw is None:
        pid = None
    else:
        pid = int(pid_raw)

    launchd_label_raw = raw.get("launchd_label")
    launchd_label = str(launchd_label_raw) if isinstance(launchd_label_raw, str) else None

    return RuntimeSchedulerState(
        handle=str(raw["handle"]),
        mode=str(raw.get("mode", "foreground")),
        running=bool(raw.get("running", False)),
        pid=pid,
        started_at=_parse_datetime(raw.get("started_at")),
        stopped_at=_parse_datetime(raw.get("stopped_at")),
        last_run_duration_seconds=(float(raw["last_run_duration_seconds"]) if raw.get("last_run_duration_seconds") is not None else None),
        cycle_count=int(raw.get("cycle_count", 0)),
        last_cycle_at=_parse_datetime(raw.get("last_cycle_at")),
        launchd_label=launchd_label,
    )


def write_runtime_state(base_path: Path, state: RuntimeSchedulerState) -> Path:
    """Persist scheduler runtime state for a handle."""
    state_path = get_runtime_state_path(base_path, state.handle)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "handle": state.handle,
        "mode": state.mode,
        "running": state.running,
        "pid": state.pid,
        "started_at": _serialize_datetime(state.started_at),
        "stopped_at": _serialize_datetime(state.stopped_at),
        "last_run_duration_seconds": state.last_run_duration_seconds,
        "cycle_count": state.cycle_count,
        "last_cycle_at": _serialize_datetime(state.last_cycle_at),
        "launchd_label": state.launchd_label,
    }
    state_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return state_path


def clear_runtime_state(base_path: Path, handle: str) -> None:
    """Delete scheduler runtime state for a handle if it exists."""
    get_runtime_state_path(base_path, handle).unlink(missing_ok=True)


def acquire_runtime_lock(base_path: Path, handle: str) -> TextIO | None:
    """Acquire an exclusive non-blocking lock for one handle.

    Returns:
        An open file handle holding the lock, or None if already locked.
    """
    lock_path = get_runtime_lock_path(base_path, handle)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = lock_path.open("a+", encoding="utf-8")

    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock_file.close()
        return None

    return lock_file


def release_runtime_lock(lock_file: TextIO) -> None:
    """Release and close a runtime lock file handle."""
    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    lock_file.close()


def is_process_running(pid: int) -> bool:
    """Return True if a process exists for the provided PID."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True

    return True


def terminate_process(pid: int, sig: int = signal.SIGTERM) -> None:
    """Send a termination signal to a process ID."""
    os.kill(pid, sig)


def wait_for_process_exit(pid: int, timeout_seconds: float = 8.0, poll_interval_seconds: float = 0.2) -> bool:
    """Wait until a process exits or timeout elapses."""
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        if not is_process_running(pid):
            return True
        time.sleep(poll_interval_seconds)

    return not is_process_running(pid)


def get_launch_agents_dir() -> Path:
    """Return the macOS LaunchAgents directory path."""
    return Path.home() / "Library" / "LaunchAgents"


def get_launch_agent_path(label: str) -> Path:
    """Return the plist path for a LaunchAgent label."""
    return get_launch_agents_dir() / f"{label}.plist"


def ensure_scheduler_log_directory(base_path: Path, handle: str) -> Path:
    """Create and return .agents/<handle>/logs for scheduler logs."""
    log_dir = agent_store.get_agent_dir(base_path, handle) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def resolve_cli_program_arguments() -> list[str]:
    """Resolve an absolute command invocation for launchd ProgramArguments."""
    moltbook_path = shutil.which(CLI_NAME)
    if moltbook_path:
        return [moltbook_path]

    return [sys.executable, "-m", "automolt.main"]


def build_launch_agent_plist_bytes(
    label: str,
    start_interval_seconds: int,
    program_arguments: list[str],
    working_directory: Path,
    stdout_log_path: Path,
    stderr_log_path: Path,
) -> bytes:
    """Build LaunchAgent plist content as XML bytes."""
    payload: dict[str, Any] = {
        "Label": label,
        "ProgramArguments": program_arguments,
        "WorkingDirectory": str(working_directory),
        "RunAtLoad": True,
        "StartInterval": start_interval_seconds,
        "StandardOutPath": str(stdout_log_path),
        "StandardErrorPath": str(stderr_log_path),
    }
    return plistlib.dumps(payload, fmt=plistlib.FMT_XML, sort_keys=True)


def write_launch_agent_plist(plist_path: Path, plist_bytes: bytes, overwrite: bool) -> Path:
    """Write LaunchAgent plist bytes to disk."""
    plist_path.parent.mkdir(parents=True, exist_ok=True)

    if plist_path.exists() and not overwrite:
        raise FileExistsError(f"LaunchAgent already exists at '{plist_path}'.")

    plist_path.write_bytes(plist_bytes)
    return plist_path


def remove_launch_agent_plist(plist_path: Path) -> bool:
    """Remove a LaunchAgent plist file if it exists."""
    if not plist_path.exists():
        return False

    plist_path.unlink()
    return True


def read_launch_agent_plist(plist_path: Path) -> dict[str, Any] | None:
    """Read LaunchAgent plist data if file exists."""
    if not plist_path.exists():
        return None

    with plist_path.open("rb") as plist_file:
        data = plistlib.load(plist_file)

    return data


def load_launch_agent(plist_path: Path) -> None:
    """Load a launchd LaunchAgent plist."""
    if not plist_path.exists():
        raise FileNotFoundError(f"LaunchAgent plist not found at '{plist_path}'.")

    result = subprocess.run(
        ["launchctl", "load", "-w", str(plist_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        details = stderr or stdout or "unknown launchctl error"
        raise RuntimeError(f"Failed to load LaunchAgent '{plist_path}': {details}")


def unload_launch_agent(plist_path: Path) -> None:
    """Unload a launchd LaunchAgent plist."""
    if not plist_path.exists():
        return

    result = subprocess.run(
        ["launchctl", "unload", "-w", str(plist_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip().lower()
        if "could not find specified service" in stderr or "no such process" in stderr:
            return

        stdout = result.stdout.strip()
        details = result.stderr.strip() or stdout or "unknown launchctl error"
        raise RuntimeError(f"Failed to unload LaunchAgent '{plist_path}': {details}")


def is_launch_agent_loaded(label: str) -> bool:
    """Return whether launchd currently reports a loaded job for the label."""
    result = subprocess.run(
        ["launchctl", "list", label],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0
