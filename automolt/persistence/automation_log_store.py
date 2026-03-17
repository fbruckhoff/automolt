"""Persistence helpers for per-item automation LLM prompt/response logs."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from automolt.persistence import agent_store

LOG_FILENAME_ITEM_ID_PATTERN = re.compile(r"[^A-Za-z0-9._-]")
LOG_RESPONSE_SEPARATOR = "\n\n// ---------- RESPONSE ----------\n\n"
AUTOMATION_EVENTS_LOG_FILENAME = "automation-events.jsonl"


class AutomationEventStatus(str, Enum):
    """Persistence status values for automation events."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class AutomationEvent:
    """Typed automation event record persisted in the log store."""

    event_id: str
    event_type: str
    source_trigger: str
    status: AutomationEventStatus
    created_at_utc: datetime
    submolt_name: str | None = None
    post_id: str | None = None
    source_item_id: str | None = None
    error_summary: str | None = None


def get_logs_dir(base_path: Path, handle: str) -> Path:
    """Return the per-agent automation logs directory path."""
    return agent_store.get_agent_dir(base_path, handle) / "logs"


def get_events_log_path(base_path: Path, handle: str) -> Path:
    """Return path to per-agent automation events log file."""
    return get_logs_dir(base_path, handle) / AUTOMATION_EVENTS_LOG_FILENAME


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


def write_automation_event(
    base_path: Path,
    handle: str,
    *,
    event_type: str,
    source_trigger: str,
    status: AutomationEventStatus,
    created_at_utc: datetime | None = None,
    submolt_name: str | None = None,
    post_id: str | None = None,
    source_item_id: str | None = None,
    error_summary: str | None = None,
) -> AutomationEvent:
    """Append one typed automation event to persistent JSONL storage."""
    created_at = created_at_utc or datetime.now(timezone.utc)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    else:
        created_at = created_at.astimezone(timezone.utc)

    event = AutomationEvent(
        event_id=str(uuid.uuid4()),
        event_type=event_type,
        source_trigger=source_trigger,
        status=status,
        created_at_utc=created_at,
        submolt_name=submolt_name,
        post_id=post_id,
        source_item_id=source_item_id,
        error_summary=error_summary,
    )
    payload = {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "source_trigger": event.source_trigger,
        "status": event.status.value,
        "created_at_utc": event.created_at_utc.isoformat(),
        "submolt_name": event.submolt_name,
        "post_id": event.post_id,
        "source_item_id": event.source_item_id,
        "error_summary": event.error_summary,
    }

    events_path = get_events_log_path(base_path, handle)
    events_path.parent.mkdir(parents=True, exist_ok=True)
    with events_path.open("a", encoding="utf-8") as event_file:
        event_file.write(json.dumps(payload, separators=(",", ":")))
        event_file.write("\n")

    return event


def list_automation_events(base_path: Path, handle: str, *, limit: int | None = None) -> list[AutomationEvent]:
    """Return automation events ordered newest-first from the JSONL log."""
    events_path = get_events_log_path(base_path, handle)
    if not events_path.is_file():
        return []

    parsed_events: list[AutomationEvent] = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        normalized = line.strip()
        if not normalized:
            continue

        try:
            payload = json.loads(normalized)
            created_at = datetime.fromisoformat(payload["created_at_utc"])
            status = AutomationEventStatus(payload["status"])
            parsed_events.append(
                AutomationEvent(
                    event_id=str(payload["event_id"]),
                    event_type=str(payload["event_type"]),
                    source_trigger=str(payload["source_trigger"]),
                    status=status,
                    created_at_utc=created_at,
                    submolt_name=payload.get("submolt_name"),
                    post_id=payload.get("post_id"),
                    source_item_id=payload.get("source_item_id"),
                    error_summary=payload.get("error_summary"),
                )
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue

    parsed_events.sort(key=lambda event: event.created_at_utc, reverse=True)
    if limit is None:
        return parsed_events
    return parsed_events[:limit]


def get_last_successful_submolt_creation(base_path: Path, handle: str) -> AutomationEvent | None:
    """Return the latest successful `create_submolt` automation event."""
    for event in list_automation_events(base_path, handle):
        if event.event_type == "create_submolt" and event.status == AutomationEventStatus.SUCCESS:
            return event
    return None


def count_successful_submolt_creations_since(base_path: Path, handle: str, since_utc: datetime) -> int:
    """Count successful submolt creation events since a UTC timestamp."""
    if since_utc.tzinfo is None:
        normalized_since = since_utc.replace(tzinfo=timezone.utc)
    else:
        normalized_since = since_utc.astimezone(timezone.utc)

    count = 0
    for event in list_automation_events(base_path, handle):
        if event.event_type != "create_submolt" or event.status != AutomationEventStatus.SUCCESS:
            continue
        event_created_at = event.created_at_utc
        if event_created_at.tzinfo is None:
            event_created_at = event_created_at.replace(tzinfo=timezone.utc)
        if event_created_at >= normalized_since:
            count += 1
    return count


def has_successful_submolt_name(base_path: Path, handle: str, submolt_name: str) -> bool:
    """Return True when a successful create event exists for a submolt name."""
    normalized_name = submolt_name.strip().lower()
    if not normalized_name:
        return False

    for event in list_automation_events(base_path, handle):
        if event.event_type != "create_submolt" or event.status != AutomationEventStatus.SUCCESS:
            continue
        candidate_name = (event.submolt_name or "").strip().lower()
        if candidate_name == normalized_name:
            return True
    return False
