"""Business logic for post and comment operations.

Handles creating comments via the Moltbook API.
"""

from typing import Any

from automolt.api.client import MoltbookAPIError, MoltbookClient
from automolt.models.post import CommentCreateResponse, PostCreateResponse
from automolt.services.content_verification_service import ContentVerificationService


class PostService:
    """Service for post and comment operations."""

    def __init__(self, api_client: MoltbookClient):
        self._api = api_client
        self._verification = ContentVerificationService(api_client)

    def create_post(self, api_key: str, submolt_name: str, title: str, content: str | None = None, url: str | None = None) -> PostCreateResponse:
        """Create a post in a submolt on Moltbook."""
        normalized_submolt_name = submolt_name.strip()
        normalized_title = title.strip()
        normalized_content = content.strip() if content is not None else None
        normalized_url = url.strip() if url is not None else None

        if not normalized_submolt_name:
            raise ValueError("Submolt name cannot be empty.")
        if not normalized_title:
            raise ValueError("Post title cannot be empty.")
        if normalized_content and normalized_url:
            raise ValueError("Post must include either content or url, not both.")
        if not normalized_content and not normalized_url:
            raise ValueError("Post must include content or url.")

        raw_response = self._api.create_post(
            api_key,
            normalized_submolt_name,
            normalized_title,
            content=normalized_content,
            url=normalized_url,
        )
        raw_response, verification_completed = self._verification.verify_if_required(api_key, raw_response, "post")

        if "post" not in raw_response:
            raise MoltbookAPIError(message="Unexpected API response: missing 'post' key")

        post_payload = dict(raw_response["post"])
        post_payload["verification_completed"] = verification_completed
        return PostCreateResponse.model_validate(post_payload)

    def add_comment(self, api_key: str, post_id: str, content: str, parent_id: str | None = None) -> CommentCreateResponse:
        """Add a comment to a post on Moltbook.

        Args:
            api_key: The agent's API key for authentication.
            post_id: The ID of the post to comment on.
            content: The comment text.
            parent_id: Optional parent comment ID for threaded replies.

        Returns:
            The parsed CommentCreateResponse.

        Raises:
            MoltbookAPIError: If the API call fails or returns unexpected data.
        """
        raw_response = self._api.add_comment(api_key, post_id, content, parent_id)

        if "comment" not in raw_response:
            raise MoltbookAPIError(message="Unexpected API response: missing 'comment' key")

        return CommentCreateResponse.model_validate(raw_response["comment"])

    def upvote_post(self, api_key: str, post_id: str) -> dict[str, Any]:
        """Upvote a post on Moltbook.

        Args:
            api_key: The agent's API key for authentication.
            post_id: The ID of the post to upvote.

        Returns:
            The raw API response payload.
        """
        normalized_post_id = post_id.strip()
        if not normalized_post_id:
            raise ValueError("Post ID cannot be empty.")

        response = self._api.upvote_post(api_key, normalized_post_id)
        self._verify_post_upvote_state(api_key, normalized_post_id)
        return response

    def upvote_comment(self, api_key: str, comment_id: str) -> dict[str, Any]:
        """Upvote a comment on Moltbook.

        Args:
            api_key: The agent's API key for authentication.
            comment_id: The ID of the comment to upvote.

        Returns:
            The raw API response payload.
        """
        normalized_comment_id = comment_id.strip()
        if not normalized_comment_id:
            raise ValueError("Comment ID cannot be empty.")

        return self._api.upvote_comment(api_key, normalized_comment_id)

    def upvote_target(self, api_key: str, target_type: str, target_id: str) -> dict[str, Any]:
        """Upvote one target by type.

        Args:
            api_key: The agent's API key for authentication.
            target_type: Either 'post' or 'comment'.
            target_id: The post/comment ID.

        Returns:
            The raw API response payload.

        Raises:
            ValueError: If target_type is unsupported or target_id is empty.
        """
        normalized_target_type = target_type.strip().lower()
        if normalized_target_type == "post":
            return self.upvote_post(api_key, target_id)

        if normalized_target_type == "comment":
            return self.upvote_comment(api_key, target_id)

        raise ValueError("Target type must be 'post' or 'comment'.")

    def evaluate_upvote_response(self, response: dict[str, Any]) -> str | None:
        """Validate one upvote response payload and return normalized message text.

        Raises:
            MoltbookAPIError: If the response indicates vote removal instead of an accepted upvote.
        """
        message = self.extract_upvote_message(response)
        if message and self.is_vote_removed_message(message):
            raise MoltbookAPIError(
                message="Upvote was not accepted by API (response: 'Vote removed').",
                hint="This endpoint toggles votes. Re-run only if you intentionally want to toggle again.",
            )

        return message

    def extract_upvote_message(self, response: dict[str, Any]) -> str | None:
        """Extract one human-readable message from an upvote API response."""
        raw_message = response.get("message")
        if not isinstance(raw_message, str):
            return None

        normalized_message = raw_message.strip()
        return normalized_message or None

    def is_vote_removed_message(self, message: str) -> bool:
        """Return True when a payload message indicates vote removal."""
        normalized_message = message.strip().lower()
        return "vote" in normalized_message and "removed" in normalized_message

    def _verify_post_upvote_state(self, api_key: str, post_id: str) -> None:
        """Validate that a post write leaves final vote state set to upvote.

        The API is treated as source of truth. If `your_vote` is present in the
        post payload and is not `upvote`, we fail fast to avoid reporting false
        success to the operator.
        """
        post_response = self._api.get_post(api_key, post_id)
        post_payload = post_response.get("post", post_response)
        if not isinstance(post_payload, dict):
            return

        raw_vote = post_payload.get("your_vote")
        if raw_vote is None:
            return

        normalized_vote = str(raw_vote).strip().lower()
        if normalized_vote != "upvote":
            raise MoltbookAPIError(
                message="Upvote did not persist: final post vote state is not upvote.",
                hint="Confirm the target ID/handle and try again.",
            )
