"""Pydantic models for automation queue items."""

from datetime import datetime

from pydantic import BaseModel, Field


class QueueItem(BaseModel):
    """A single item in the automation queue, mapped from the SQLite queue table."""

    item_id: str
    item_type: str = Field(description="Either 'post' or 'comment'")
    post_id: str | None = Field(default=None, description="Parent post ID. For post items, usually equals item_id.")
    submolt_name: str | None = None
    author_name: str | None = None
    analyzed: bool = False
    is_relevant: bool = False
    relevance_rationale: str | None = None
    replied_item_id: str | None = None
    created_at: datetime
