"""Business logic for semantic search operations.

Handles searching posts and comments via the Moltbook API.
"""

import logging
from typing import Any

from automolt.api.client import MoltbookAPIError, MoltbookClient
from automolt.models.search_result import SearchResponse, SearchResult

logger = logging.getLogger(__name__)
MIN_SEARCH_QUERY_LENGTH = 3
MAX_SEARCH_QUERY_LENGTH = 500


class SearchService:
    """Service for semantic search operations."""

    def __init__(self, api_client: MoltbookClient):
        self._api = api_client

    def search(self, api_key: str, query: str, search_type: str = "all", limit: int = 50) -> SearchResponse:
        """Perform a semantic search across Moltbook content.

        Args:
            api_key: The agent's API key for authentication.
            query: Natural language search query (max 500 chars).
            search_type: What to search: 'posts', 'comments', or 'all'.
            limit: Max results to return (default 50, max 50).

        Returns:
            The parsed SearchResponse containing ranked results.

        Raises:
            MoltbookAPIError: If the API call fails.
            ValueError: If query is shorter than 3 or exceeds 500 characters.
        """
        normalized_query = query.strip()
        if len(normalized_query) < MIN_SEARCH_QUERY_LENGTH:
            raise ValueError(f"Search query must be at least {MIN_SEARCH_QUERY_LENGTH} characters.")

        if len(normalized_query) > MAX_SEARCH_QUERY_LENGTH:
            raise ValueError(f"Search query must be {MAX_SEARCH_QUERY_LENGTH} characters or fewer.")

        if limit < 1 or limit > 50:
            raise ValueError("Limit must be between 1 and 50.")

        raw_response = self._api.search(api_key, normalized_query, search_type, limit)
        return SearchResponse.model_validate(raw_response)

    def get_full_content(self, api_key: str, result: SearchResult) -> str | None:
        """Fetch the full text content for a search result.

        For posts, fetches the post directly. For comments, fetches all
        comments on the parent post and locates the matching comment.

        Args:
            api_key: The agent's API key for authentication.
            result: A single search result to fetch full content for.

        Returns:
            The full content string, or None if retrieval fails.
        """
        try:
            if result.type == "post":
                return self._get_post_content(api_key, result.post_id)
            if result.type == "comment":
                return self._get_comment_content(api_key, result.post_id, result.id)
        except MoltbookAPIError as exc:
            logger.debug("Failed to fetch full content for %s %s: %s", result.type, result.id, exc.message)
        return None

    def get_queue_item_author_name(
        self,
        api_key: str,
        item_type: str,
        item_id: str,
        post_id: str,
    ) -> str | None:
        """Resolve author name for a queue item using canonical API payloads."""
        try:
            if item_type == "post":
                return self._get_post_author_name(api_key, post_id)

            if item_type == "comment":
                return self._get_comment_author_name(api_key, post_id, item_id)
        except MoltbookAPIError as exc:
            logger.debug("Failed to fetch queue item author for %s %s: %s", item_type, item_id, exc.message)

        return None

    def get_queue_item_content(
        self,
        api_key: str,
        item_type: str,
        item_id: str,
        post_id: str | None,
    ) -> str | None:
        """Fetch full content for an automation queue item.

        Args:
            api_key: The agent's API key for authentication.
            item_type: Queue item type ('post' or 'comment').
            item_id: Queue item ID (post ID for posts, comment ID for comments).
            post_id: Parent post ID for comments. For posts, may equal item_id.

        Returns:
            Full content text if available; otherwise None.
        """
        try:
            if item_type == "post":
                resolved_post_id = post_id or item_id
                return self._get_post_content(api_key, resolved_post_id)

            if item_type == "comment":
                if not post_id:
                    return None
                return self._get_comment_content(api_key, post_id, item_id)
        except MoltbookAPIError as exc:
            logger.debug("Failed to fetch queue item content for %s %s: %s", item_type, item_id, exc.message)

        return None

    def _get_post_content(self, api_key: str, post_id: str) -> str | None:
        """Fetch full content for a single post."""
        data = self._api.get_post(api_key, post_id)
        # Response may wrap post in a "post" key or return it at top level
        post = data.get("post", data)
        return post.get("content")

    def _get_post_author_name(self, api_key: str, post_id: str) -> str | None:
        """Fetch author name for a single post."""
        data = self._api.get_post(api_key, post_id)
        post = data.get("post", data)
        author = post.get("author", {}) if isinstance(post, dict) else {}
        if isinstance(author, dict):
            name = author.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()
        return None

    def _get_comment_content(self, api_key: str, post_id: str, comment_id: str) -> str | None:
        """Fetch full content for a comment by searching the comment tree."""
        data = self._api.get_comments(api_key, post_id)
        comments = data.get("comments", [])
        return _find_comment_in_tree(comments, comment_id)

    def _get_comment_author_name(self, api_key: str, post_id: str, comment_id: str) -> str | None:
        """Fetch author name for a comment by searching the comment tree."""
        data = self._api.get_comments(api_key, post_id)
        comments = data.get("comments", [])
        return _find_comment_author_in_tree(comments, comment_id)


def _find_comment_in_tree(comments: list[dict[str, Any]], comment_id: str) -> str | None:
    """Recursively search a nested comment tree for a comment by ID.

    Args:
        comments: List of comment dicts, each potentially containing a 'replies' list.
        comment_id: The ID of the comment to find.

    Returns:
        The comment's content string, or None if not found.
    """
    for comment in comments:
        if comment.get("id") == comment_id:
            return comment.get("content")
        replies = comment.get("replies", [])
        if replies:
            found = _find_comment_in_tree(replies, comment_id)
            if found is not None:
                return found
    return None


def _find_comment_author_in_tree(comments: list[dict[str, Any]], comment_id: str) -> str | None:
    """Recursively search a nested comment tree for a comment author by ID."""
    for comment in comments:
        if comment.get("id") == comment_id:
            author = comment.get("author", {})
            if isinstance(author, dict):
                name = author.get("name")
                if isinstance(name, str) and name.strip():
                    return name.strip()
            return None
        replies = comment.get("replies", [])
        if replies:
            found = _find_comment_author_in_tree(replies, comment_id)
            if found is not None:
                return found
    return None
