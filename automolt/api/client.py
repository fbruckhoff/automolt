"""HTTP client for communicating with the Moltbook API."""

from typing import Any

import httpx

BASE_URL = "https://www.moltbook.com/api/v1"
NOT_FOUND_STATUS = 404


class MoltbookAPIError(Exception):
    """Raised when the Moltbook API returns an error response."""

    def __init__(self, message: str, hint: str | None = None, status_code: int | None = None):
        self.message = message
        self.hint = hint
        self.status_code = status_code
        super().__init__(message)

    def __repr__(self) -> str:
        return f"MoltbookAPIError(message={self.message!r}, status_code={self.status_code})"


class MoltbookClient:
    """Synchronous HTTP client for the Moltbook REST API.

    Attributes:
        base_url: The base URL for all API requests.
        timeout: Request timeout in seconds.
    """

    def __init__(self, base_url: str = BASE_URL, timeout: float = 30.0):
        self.base_url = base_url
        self.timeout = timeout
        self._http = httpx.Client(base_url=base_url, timeout=timeout)

    def __enter__(self) -> "MoltbookClient":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def __del__(self) -> None:
        """Fallback resource cleanup."""
        if hasattr(self, "_http") and self._http:
            self._http.close()

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._http.close()

    def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        """Parse a JSON response and raise on API-level errors."""
        try:
            data = response.json()
        except ValueError:
            raise MoltbookAPIError(
                message=f"Unexpected response (HTTP {response.status_code})",
                status_code=response.status_code,
            )

        if not response.is_success:
            error_msg = data.get("error") or data.get("message") or f"HTTP {response.status_code}"
            hint = data.get("hint")
            raise MoltbookAPIError(message=error_msg, hint=hint, status_code=response.status_code)

        if isinstance(data, dict) and data.get("success") is False:
            raise MoltbookAPIError(
                message=data.get("error", "Unknown API error"),
                hint=data.get("hint"),
            )

        return data

    def _handle_http_error(self, exc: httpx.HTTPError) -> MoltbookAPIError:
        """Convert HTTP errors to MoltbookAPIError with consistent formatting."""
        return MoltbookAPIError(message="Failed to connect to Moltbook API. Please check your internet connection.")

    def _auth_headers(self, api_key: str) -> dict[str, str]:
        """Create authorization headers for API requests."""
        return {"Authorization": f"Bearer {api_key}"}

    def check_username_availability(self, handle: str) -> bool:
        """Check whether a handle (username) is available on Moltbook.

        Uses the public profile endpoint. If the agent exists, the name is
        taken. If the API returns a 404 or agent-not-found error, the name
        is available.

        Returns:
            True if the handle is available, False if it is already taken.
        """
        try:
            response = self._http.get("/agents/profile", params={"name": handle})

            if response.status_code == NOT_FOUND_STATUS:
                return True

            self._handle_response(response)

            # Any successful response with agent data means the name is taken
            return False
        except httpx.HTTPError as exc:
            raise self._handle_http_error(exc) from exc

    def get_agent_status(self, api_key: str) -> str:
        """Check the claim/verification status of an agent.

        Args:
            api_key: The agent's API key for authentication.

        Returns:
            The status string (e.g. "pending_claim" or "claimed").

        Raises:
            MoltbookAPIError: If the request fails.
        """
        try:
            response = self._http.get("/agents/status", headers=self._auth_headers(api_key))
            data = self._handle_response(response)
            return data["status"]
        except httpx.HTTPError as exc:
            raise self._handle_http_error(exc) from exc

    def update_agent_description(self, api_key: str, description: str) -> dict[str, Any]:
        """Update the agent's description via PATCH /agents/me.

        Args:
            api_key: The agent's API key for authentication.
            description: New description (1-500 characters).

        Returns:
            The raw JSON response dict containing the updated agent data.

        Raises:
            MoltbookAPIError: If the update fails.
        """
        payload = {"description": description}
        try:
            response = self._http.patch("/agents/me", headers=self._auth_headers(api_key), json=payload)
            return self._handle_response(response)
        except httpx.HTTPError as exc:
            raise self._handle_http_error(exc) from exc

    def get_my_profile(self, api_key: str) -> dict[str, Any]:
        """Fetch the authenticated agent's full profile via GET /agents/me.

        Args:
            api_key: The agent's API key for authentication.

        Returns:
            The raw JSON response dict containing agent profile data
            including owner info, karma, follower counts, etc.

        Raises:
            MoltbookAPIError: If the request fails.
        """
        try:
            response = self._http.get("/agents/me", headers=self._auth_headers(api_key))
            return self._handle_response(response)
        except httpx.HTTPError as exc:
            raise self._handle_http_error(exc) from exc

    def create_submolt(self, api_key: str, name: str, display_name: str, description: str | None = None, allow_crypto: bool = False) -> dict[str, Any]:
        """Create a new submolt (community) via POST /submolts.

        Args:
            api_key: The agent's API key for authentication.
            name: URL-friendly name (lowercase, no spaces).
            display_name: Human-readable display name.
            description: What the submolt is about.
            allow_crypto: Whether cryptocurrency content is allowed.

        Returns:
            The raw JSON response dict containing the submolt data.

        Raises:
            MoltbookAPIError: If creation fails.
        """
        payload: dict[str, Any] = {
            "name": name,
            "display_name": display_name,
            "allow_crypto": allow_crypto,
        }
        if description is not None:
            payload["description"] = description
        try:
            response = self._http.post("/submolts", headers=self._auth_headers(api_key), json=payload)
            return self._handle_response(response)
        except httpx.HTTPError as exc:
            raise self._handle_http_error(exc) from exc

    def create_post(self, api_key: str, submolt_name: str, title: str, content: str | None = None, url: str | None = None) -> dict[str, Any]:
        """Create a new post via POST /posts.

        Args:
            api_key: The agent's API key for authentication.
            submolt_name: The target submolt name.
            title: The post title.
            content: Optional text body for a text post.
            url: Optional link URL for a link post.

        Returns:
            The raw JSON response dict containing the post data.

        Raises:
            MoltbookAPIError: If creation fails.
        """
        payload: dict[str, Any] = {
            "submolt_name": submolt_name,
            "title": title,
        }
        if content is not None:
            payload["content"] = content
            payload["type"] = "text"
        if url is not None:
            payload["url"] = url
            payload["type"] = "link"

        try:
            response = self._http.post("/posts", headers=self._auth_headers(api_key), json=payload)
            return self._handle_response(response)
        except httpx.HTTPError as exc:
            raise self._handle_http_error(exc) from exc

    def verify_content(self, api_key: str, verification_code: str, answer: str) -> dict[str, Any]:
        """Submit a verification answer via POST /verify.

        Args:
            api_key: The agent's API key for authentication.
            verification_code: Verification code from a pending content response.
            answer: Computed numeric answer formatted as text.

        Returns:
            The raw verification response payload.

        Raises:
            MoltbookAPIError: If verification fails.
        """
        payload = {"verification_code": verification_code, "answer": answer}
        try:
            response = self._http.post("/verify", headers=self._auth_headers(api_key), json=payload)
            return self._handle_response(response)
        except httpx.HTTPError as exc:
            raise self._handle_http_error(exc) from exc

    def get_post(self, api_key: str, post_id: str) -> dict[str, Any]:
        """Fetch a single post by ID via GET /posts/{post_id}.

        Args:
            api_key: The agent's API key for authentication.
            post_id: The ID of the post to retrieve.

        Returns:
            The raw JSON response dict containing the post data.

        Raises:
            MoltbookAPIError: If the request fails.
        """
        try:
            response = self._http.get(f"/posts/{post_id}", headers=self._auth_headers(api_key))
            return self._handle_response(response)
        except httpx.HTTPError as exc:
            raise self._handle_http_error(exc) from exc

    def get_comments(self, api_key: str, post_id: str) -> dict[str, Any]:
        """Fetch comments on a post via GET /posts/{post_id}/comments.

        Args:
            api_key: The agent's API key for authentication.
            post_id: The ID of the post whose comments to retrieve.

        Returns:
            The raw JSON response dict containing the comments.

        Raises:
            MoltbookAPIError: If the request fails.
        """
        try:
            response = self._http.get(
                f"/posts/{post_id}/comments",
                headers=self._auth_headers(api_key),
                params={"limit": 200},
            )
            return self._handle_response(response)
        except httpx.HTTPError as exc:
            raise self._handle_http_error(exc) from exc

    def search(self, api_key: str, query: str, search_type: str = "all", limit: int = 50) -> dict[str, Any]:
        """Perform a semantic search via GET /search.

        Args:
            api_key: The agent's API key for authentication.
            query: Natural language search query (max 500 chars).
            search_type: What to search: 'posts', 'comments', or 'all'.
            limit: Max results to return (default 50, max 50).

        Returns:
            The raw JSON response dict containing search results.

        Raises:
            MoltbookAPIError: If the search fails.
        """
        params = {"q": query, "type": search_type, "limit": limit}
        try:
            response = self._http.get("/search", headers=self._auth_headers(api_key), params=params)
            return self._handle_response(response)
        except httpx.HTTPError as exc:
            raise self._handle_http_error(exc) from exc

    def add_comment(self, api_key: str, post_id: str, content: str, parent_id: str | None = None) -> dict[str, Any]:
        """Add a comment to a post via POST /posts/{post_id}/comments.

        Args:
            api_key: The agent's API key for authentication.
            post_id: The ID of the post to comment on.
            content: The comment text.
            parent_id: Optional parent comment ID for threaded replies.

        Returns:
            The raw JSON response dict containing the created comment.

        Raises:
            MoltbookAPIError: If the comment fails.
        """
        payload: dict[str, str] = {"content": content}
        if parent_id is not None:
            payload["parent_id"] = parent_id
        try:
            response = self._http.post(f"/posts/{post_id}/comments", headers=self._auth_headers(api_key), json=payload)
            return self._handle_response(response)
        except httpx.HTTPError as exc:
            raise self._handle_http_error(exc) from exc

    def upvote_post(self, api_key: str, post_id: str) -> dict[str, Any]:
        """Upvote a post via POST /posts/{post_id}/upvote.

        Args:
            api_key: The agent's API key for authentication.
            post_id: The ID of the post to upvote.

        Returns:
            The raw JSON response dict for the upvote operation.

        Raises:
            MoltbookAPIError: If the upvote fails.
        """
        try:
            response = self._http.post(
                f"/posts/{post_id}/upvote",
                headers=self._auth_headers(api_key),
            )
            return self._handle_response(response)
        except httpx.HTTPError as exc:
            raise self._handle_http_error(exc) from exc

    def upvote_comment(self, api_key: str, comment_id: str) -> dict[str, Any]:
        """Upvote a comment via POST /comments/{comment_id}/upvote.

        Args:
            api_key: The agent's API key for authentication.
            comment_id: The ID of the comment to upvote.

        Returns:
            The raw JSON response dict for the upvote operation.

        Raises:
            MoltbookAPIError: If the upvote fails.
        """
        try:
            response = self._http.post(
                f"/comments/{comment_id}/upvote",
                headers=self._auth_headers(api_key),
            )
            return self._handle_response(response)
        except httpx.HTTPError as exc:
            raise self._handle_http_error(exc) from exc

    def register_agent(self, handle: str, description: str) -> dict[str, Any]:
        """Register a new agent on Moltbook.

        Args:
            handle: The desired agent name (1-50 characters).
            description: Agent description (1-500 characters).

        Returns:
            The raw JSON response dict from the API containing agent credentials.

        Raises:
            MoltbookAPIError: If registration fails.
        """
        payload = {"name": handle, "description": description}
        try:
            response = self._http.post("/agents/register", json=payload)
            return self._handle_response(response)
        except httpx.HTTPError as exc:
            raise self._handle_http_error(exc) from exc
