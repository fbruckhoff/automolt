"""Pydantic models for Moltbook semantic search results."""

from pydantic import BaseModel, Field


class SearchResultAuthor(BaseModel):
    """Author metadata within a search result."""

    name: str


class SearchResultSubmolt(BaseModel):
    """Submolt metadata within a search result (present on post results)."""

    name: str
    display_name: str


class SearchResultPost(BaseModel):
    """Parent post metadata within a search result (present on comment results)."""

    id: str
    title: str | None = None


class SearchResult(BaseModel):
    """A single search result from the Moltbook semantic search API."""

    id: str
    type: str = Field(description="Either 'post' or 'comment'")
    title: str | None = None
    content: str | None = None
    upvotes: int = 0
    downvotes: int = 0
    similarity: float | None = Field(default=None, ge=0.0, le=1.0)
    author: SearchResultAuthor
    submolt: SearchResultSubmolt | None = None
    post: SearchResultPost | None = None
    post_id: str
    created_at: str | None = None


class SearchResponse(BaseModel):
    """Parsed response from the Moltbook semantic search API."""

    query: str
    type: str
    results: list[SearchResult]
    count: int
