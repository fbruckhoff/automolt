"""Helpers for session-aware agent handle targeting in CLI commands."""

from __future__ import annotations

from pathlib import Path

from automolt.persistence.client_store import get_last_active_agent, set_last_active_agent
from automolt.persistence.session_store import get_session_active_agent, set_session_active_agent, sweep_stale_sessions


def resolve_target_handle(base_path: Path, explicit_handle: str | None) -> str | None:
    """Resolve command target handle using explicit, session, then remembered fallback.

    Resolution order:
    1) explicit --handle
    2) session active_agent from .sessions/<PPID>.json
    3) lazy initialize session active_agent from client.json:last_active_agent

    Returns:
        Resolved handle, or None when no target can be resolved.

    Raises:
        FileNotFoundError: If client.json does not exist and no explicit/session handle is available.
        ValueError: If explicit handle is empty/whitespace or session config is corrupted.
    """
    if explicit_handle is not None:
        normalized_handle = explicit_handle.strip()
        if not normalized_handle:
            raise ValueError("Handle cannot be empty.")
        return normalized_handle

    sweep_stale_sessions(base_path)

    session_handle = get_session_active_agent(base_path)
    if session_handle:
        return session_handle

    last_active_handle = get_last_active_agent(base_path)
    if not last_active_handle:
        return None

    set_session_active_agent(base_path, last_active_handle)
    return last_active_handle


def set_selected_agent(base_path: Path, handle: str) -> None:
    """Persist selected agent to both session active_agent and client last_active_agent."""
    normalized_handle = handle.strip()
    if not normalized_handle:
        raise ValueError("Handle cannot be empty.")

    set_session_active_agent(base_path, normalized_handle)
    set_last_active_agent(base_path, normalized_handle)
