"""Business logic for submolt (community) operations.

Handles creating submolts via the Moltbook API.
"""

from automolt.api.client import MoltbookAPIError, MoltbookClient
from automolt.models.submolt import SubmoltCreateResponse


class SubmoltService:
    """Service for submolt-related operations."""

    def __init__(self, api_client: MoltbookClient):
        self._api = api_client

    def create_submolt(self, api_key: str, name: str, display_name: str, description: str) -> SubmoltCreateResponse:
        """Create a new submolt on Moltbook.

        Args:
            api_key: The agent's API key for authentication.
            name: URL-friendly name (lowercase, alphanumeric, hyphens only).
            display_name: Human-readable display name.
            description: What the submolt is about.

        Returns:
            The parsed SubmoltCreateResponse.

        Raises:
            MoltbookAPIError: If the API call fails or returns unexpected data.
        """
        raw_response = self._api.create_submolt(api_key, name, display_name, description)

        if "submolt" not in raw_response:
            raise MoltbookAPIError(message="Unexpected API response: missing 'submolt' key")

        return SubmoltCreateResponse.model_validate(raw_response["submolt"])
