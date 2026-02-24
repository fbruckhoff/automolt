"""Pydantic models for scheduler tick execution and reporting."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TickResultStatus(str, Enum):
    """Status values for one handle processed during a scheduler tick."""

    EXECUTED = "executed"
    SKIPPED = "skipped"
    ERROR = "error"
    WOULD_EXECUTE = "would_execute"


class AutomationRunMode(str, Enum):
    """Supported runtime modes for an automation run."""

    FOREGROUND = "foreground"
    BACKGROUND = "background"


class AutomationRuntimeStatus(str, Enum):
    """Overall runtime status for one handle."""

    RUNNING = "running"
    STOPPED = "stopped"


class TickAgentResult(BaseModel):
    """Result of scheduler processing for one agent handle."""

    handle: str
    status: TickResultStatus
    reason: str | None = None
    error: str | None = None
    next_due_at: datetime | None = None


class TickReport(BaseModel):
    """Aggregate result from a single scheduler tick pass."""

    started_at: datetime
    completed_at: datetime
    requested_handle: str | None = None
    force: bool = False
    dry_run: bool = False
    processed: int = 0
    executed: int = 0
    skipped: int = 0
    errors: int = 0
    results: list[TickAgentResult] = Field(default_factory=list)


class AutomationStatusReport(BaseModel):
    """Structured runtime status summary for one handle."""

    handle: str
    status: AutomationRuntimeStatus
    mode: AutomationRunMode | None = None
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    run_duration_seconds: float | None = None
    cycle_count: int = 0
    last_cycle_at: datetime | None = None
    next_due_at: datetime | None = None
