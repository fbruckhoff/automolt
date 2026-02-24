"""File I/O for per-terminal session state in .sessions/<PPID>.json."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from pydantic import BaseModel

SESSIONS_DIR_NAME = ".sessions"


class SessionConfig(BaseModel):
    """Session-level targeting state for one terminal parent process."""

    active_agent: str | None = None


def get_sessions_dir(base_path: Path) -> Path:
    """Return the .sessions directory path."""
    return base_path / SESSIONS_DIR_NAME


def ensure_sessions_dir(base_path: Path) -> Path:
    """Create .sessions directory when missing and return its path."""
    sessions_dir = get_sessions_dir(base_path)
    sessions_dir.mkdir(parents=True, exist_ok=True)
    return sessions_dir


def get_session_config_path(base_path: Path, ppid: int | None = None) -> Path:
    """Return the session file path for a PPID."""
    return get_sessions_dir(base_path) / f"{_resolve_ppid(ppid)}.json"


def load_session_config(base_path: Path, ppid: int | None = None) -> SessionConfig:
    """Load one session config file.

    Raises:
        FileNotFoundError: If the session file does not exist.
        ValueError: If session file JSON is invalid.
    """
    config_path = get_session_config_path(base_path, ppid)
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        return SessionConfig.model_validate(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"Corrupted session config at '{config_path}': {exc}") from exc


def save_session_config(base_path: Path, config: SessionConfig, ppid: int | None = None) -> Path:
    """Save one session config file atomically."""
    ensure_sessions_dir(base_path)
    config_path = get_session_config_path(base_path, ppid)
    content = json.dumps(config.model_dump(mode="json"), indent=2) + "\n"

    fd, tmp_path = tempfile.mkstemp(dir=config_path.parent, suffix=".tmp", prefix="session_")
    try:
        with open(fd, "w", encoding="utf-8") as f:
            f.write(content)
        Path(tmp_path).replace(config_path)
        try:
            os.chmod(config_path, 0o600)
        except OSError:
            pass
    except BaseException:
        Path(tmp_path).unlink(missing_ok=True)
        raise

    return config_path


def get_session_active_agent(base_path: Path, ppid: int | None = None) -> str | None:
    """Return the session active_agent for a PPID, or None when absent."""
    try:
        config = load_session_config(base_path, ppid)
    except FileNotFoundError:
        return None

    if config.active_agent is None:
        return None

    normalized_handle = config.active_agent.strip()
    if not normalized_handle:
        return None

    return normalized_handle


def set_session_active_agent(base_path: Path, handle: str, ppid: int | None = None) -> None:
    """Persist active_agent for a session PPID."""
    normalized_handle = handle.strip()
    if not normalized_handle:
        raise ValueError("Handle cannot be empty.")

    save_session_config(base_path, SessionConfig(active_agent=normalized_handle), ppid)


def sweep_stale_sessions(base_path: Path) -> int:
    """Delete stale .sessions/<PPID>.json files and return removed count."""
    sessions_dir = get_sessions_dir(base_path)
    if not sessions_dir.exists() or not sessions_dir.is_dir():
        return 0

    removed_count = 0
    for session_file in sessions_dir.glob("*.json"):
        if not session_file.is_file():
            continue

        ppid_value = _parse_session_ppid(session_file)
        if ppid_value is None:
            continue

        if _is_process_alive(ppid_value):
            continue

        session_file.unlink(missing_ok=True)
        removed_count += 1

    return removed_count


def _resolve_ppid(ppid: int | None) -> int:
    """Resolve caller PPID when not explicitly provided."""
    if ppid is None:
        ppid = os.getppid()

    if ppid <= 0:
        raise ValueError("Session PPID must be a positive integer.")

    return ppid


def _parse_session_ppid(session_file: Path) -> int | None:
    """Parse a numeric PPID from a .sessions file name."""
    ppid_text = session_file.stem
    if not ppid_text.isdigit():
        return None

    return int(ppid_text)


def _is_process_alive(pid: int) -> bool:
    """Return whether a process ID currently exists on this host."""
    if pid <= 0:
        return False

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False

    return True
