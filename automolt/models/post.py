"""Pydantic models for post and comment data."""

from pydantic import BaseModel, Field


class CommentAuthor(BaseModel):
    """Author metadata within a comment response."""

    name: str


class CommentCreateResponse(BaseModel):
    """Parsed response from the Moltbook add-comment API."""

    id: str
    content: str = Field(min_length=1)
    author: CommentAuthor
    post_id: str
    parent_id: str | None = None
    created_at: str
