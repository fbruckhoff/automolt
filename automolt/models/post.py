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


class PostAuthor(BaseModel):
    """Author metadata within a post response."""

    name: str


class PostSubmolt(BaseModel):
    """Submolt metadata within a post response."""

    name: str
    display_name: str | None = None


class PostCreateResponse(BaseModel):
    """Parsed response from the Moltbook create-post API."""

    id: str
    title: str = Field(min_length=1)
    content: str | None = None
    url: str | None = None
    type: str | None = None
    author: PostAuthor | None = None
    submolt: PostSubmolt | None = None
    created_at: str | None = None
    verification_completed: bool = False
