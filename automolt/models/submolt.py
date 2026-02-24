"""Pydantic models for submolt (community) data."""

from pydantic import BaseModel, Field


class SubmoltCreateResponse(BaseModel):
    """Parsed response from the Moltbook submolt creation API."""

    name: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    owner: str
    subscriber_count: int = 0
    post_count: int = 0
    created_at: str
