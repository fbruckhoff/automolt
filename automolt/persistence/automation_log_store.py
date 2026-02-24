"""Persistence helpers for per-item automation LLM prompt/response logs."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from automolt.persistence import agent_store

LOG_FILENAME_ITEM_ID_PATTERN = re.compile(r"[^A-Za-z0-9._-]")
LOG_RESPONSE_SEPARATOR = "\n\n// ---------- RESPONSE ----------\n\n"


def get_logs_dir(base_path: Path, handle: str) -> Path:
    """Return the per-agent automation logs directory path."""
    return agent_store.get_agent_dir(base_path, handle) / "logs"


def write_stage_log(
    base_path: Path,
    handle: str,
    *,
    item_id: str,
    stage: str,
    prompt_payload: str,
    response_payload: str,
    logged_at: datetime | None = None,
) -> Path:
    """Write one stage prompt/response log file for an automation queue item.

    The file content is exactly prompt payload + required separator + response payload.
    """
    timestamp = logged_at or datetime.now(timezone.utc)
    logs_dir = get_logs_dir(base_path, handle)
    logs_dir.mkdir(parents=True, exist_ok=True)

    safe_item_id = LOG_FILENAME_ITEM_ID_PATTERN.sub("_", item_id)
    timestamp_prefix = timestamp.strftime("%Y-%m-%d-%H-%M")
    filename = f"{timestamp_prefix}-{safe_item_id}-{stage}-log.md"
    target_path = logs_dir / filename

    file_content = f"{prompt_payload}{LOG_RESPONSE_SEPARATOR}{response_payload}"
    target_path.write_text(file_content, encoding="utf-8")
    return target_path
