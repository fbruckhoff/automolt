"""Business logic for submolt (community) operations.

Handles creating submolts via the Moltbook API.
"""

from automolt.api.client import MoltbookAPIError, MoltbookClient
from automolt.models.submolt import SubmoltCreateResponse
from automolt.services.content_verification_service import ContentVerificationService


class SubmoltService:
    """Service for submolt-related operations."""

    def __init__(self, api_client: MoltbookClient):
        self._api = api_client
        self._verification = ContentVerificationService(api_client)

    def create_submolt(self, api_key: str, name: str, display_name: str, description: str | None = None, allow_crypto: bool = False) -> SubmoltCreateResponse:
        """Create a new submolt on Moltbook.

        Args:
            api_key: The agent's API key for authentication.
            name: URL-friendly name (lowercase, alphanumeric, hyphens only).
            display_name: Human-readable display name.
            description: What the submolt is about.
            allow_crypto: Whether cryptocurrency content is allowed.

        Returns:
            The parsed SubmoltCreateResponse.

        Raises:
            MoltbookAPIError: If the API call fails or returns unexpected data.
        """
        normalized_name = name.strip()
        normalized_display_name = display_name.strip()
        normalized_description = description.strip() if description is not None else None

        if not normalized_name:
            raise ValueError("Submolt name cannot be empty.")
        if not normalized_display_name:
            raise ValueError("Display name cannot be empty.")

        raw_response = self._api.create_submolt(
            api_key,
            normalized_name,
            normalized_display_name,
            normalized_description,
            allow_crypto=allow_crypto,
        )
        raw_response, verification_completed = self._verification.verify_if_required(api_key, raw_response, "submolt")

        if "submolt" not in raw_response:
            raise MoltbookAPIError(message="Unexpected API response: missing 'submolt' key")

        submolt_payload = dict(raw_response["submolt"])
        submolt_payload["verification_completed"] = verification_completed
        return SubmoltCreateResponse.model_validate(submolt_payload)
