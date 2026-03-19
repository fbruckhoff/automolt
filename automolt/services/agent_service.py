"""Business logic for agent identity and authentication.

Handles signup flow: checking handle availability, registering agents
via the Moltbook API, and persisting agent configuration locally.
"""

from pathlib import Path

from automolt.api.client import MoltbookAPIError, MoltbookClient
from automolt.models.agent import (
    Agent,
    AgentConfig,
    AgentRegistrationResponse,
    VerificationStatus,
)
from automolt.persistence.agent_store import (
    agent_exists_locally,
    load_agent_config,
    save_agent_config,
)


class AgentService:
    """Service for agent-related operations like signup."""

    def __init__(self, api_client: MoltbookClient, base_path: Path):
        self._api = api_client
        self._base_path = base_path

    def is_handle_available(self, handle: str) -> bool:
        """Check whether a handle is available on Moltbook.

        Also checks for a local agent with the same handle.

        Returns:
            True if the handle is available both remotely and locally.
        """
        if agent_exists_locally(self._base_path, handle):
            return False

        return self._api.check_username_availability(handle)

    def create_agent(self, handle: str, description: str) -> AgentConfig:
        """Register a new agent and persist its configuration locally.

        Args:
            handle: The desired agent name.
            description: A description of the agent.

        Returns:
            The persisted AgentConfig.

        Raises:
            MoltbookAPIError: If the API registration fails or returns an unexpected response.
        """
        raw_response = self._api.register_agent(handle, description)

        if "agent" not in raw_response:
            raise MoltbookAPIError(message="Unexpected API response: missing 'agent' key")

        registration = AgentRegistrationResponse.model_validate(raw_response["agent"])

        config = AgentConfig(
            agent=Agent(
                handle=handle,
                description=description,
                api_key=registration.api_key,
                claim_url=registration.claim_url,
                verification_code=registration.verification_code,
            ),
        )

        save_agent_config(self._base_path, config)

        return config

    def get_agent_status(self, handle: str) -> AgentConfig:
        """Fetch the verification status from the API and update the local config.

        Args:
            handle: The agent's handle (username).

        Returns:
            The updated AgentConfig with the latest verification_status.

        Raises:
            MoltbookAPIError: If the API request fails.
            FileNotFoundError: If the agent config does not exist locally.
            ValueError: If the local agent config is corrupted.
        """
        config = load_agent_config(self._base_path, handle)

        if not config.agent.api_key:
            return config

        status = self._api.get_agent_status(config.agent.api_key)
        # Map API status string to enum
        if status == "verified":
            config.agent.verification_status = VerificationStatus.VERIFIED
        else:
            config.agent.verification_status = VerificationStatus.PENDING
        save_agent_config(self._base_path, config)

        return config

    def update_description(self, handle: str, new_description: str) -> AgentConfig:
        """Update an agent's description both remotely and locally.

        Performs a safe merge: only the description field is updated,
        preserving all other local fields (api_key, etc.).

        Args:
            handle: The agent's handle.
            new_description: The new description (1-500 characters).

        Returns:
            The updated AgentConfig.

        Raises:
            MoltbookAPIError: If the API update fails or agent has no API key.
            FileNotFoundError: If the agent config does not exist locally.
        """
        config = load_agent_config(self._base_path, handle)

        if not config.agent.api_key:
            raise MoltbookAPIError(message="Agent must be claimed before updating description.")

        self._api.update_agent_description(config.agent.api_key, new_description)

        # Safe merge: only update description
        config.agent.description = new_description
        save_agent_config(self._base_path, config)

        return config

    def get_profile(self, handle: str) -> AgentConfig:
        """Fetch the full profile from the API and safe-merge into local config.

        Extracts x_handle from the owner object, karma, follower/following
        counts, is_active, created_at, and last_active.
        Preserves all existing local fields (api_key, claim_url, etc.).

        Args:
            handle: The agent's handle (username).

        Returns:
            The updated AgentConfig with merged profile data.

        Raises:
            MoltbookAPIError: If the API request fails.
            FileNotFoundError: If the agent config does not exist locally.
            ValueError: If the local agent config is corrupted.
        """
        config = load_agent_config(self._base_path, handle)

        if not config.agent.api_key:
            return config

        data = self._api.get_my_profile(config.agent.api_key)
        agent_data = data.get("agent", {})

        # Map API verification status
        is_claimed = agent_data.get("is_claimed", False)
        if is_claimed:
            config.agent.verification_status = VerificationStatus.VERIFIED
        else:
            config.agent.verification_status = VerificationStatus.PENDING

        # Safe merge: update only API-sourced fields when the API provides a
        # non-None value.
        owner = agent_data.get("owner") or {}
        if owner.get("x_handle") is not None:
            config.agent.x_handle = owner["x_handle"]
        if agent_data.get("karma") is not None:
            config.agent.karma = agent_data["karma"]
        if agent_data.get("follower_count") is not None:
            config.agent.follower_count = agent_data["follower_count"]
        if agent_data.get("following_count") is not None:
            config.agent.following_count = agent_data["following_count"]
        if agent_data.get("is_active") is not None:
            config.agent.is_active = agent_data["is_active"]
        if agent_data.get("created_at") is not None:
            config.agent.created_at = agent_data["created_at"]
        if agent_data.get("last_active") is not None:
            config.agent.last_active = agent_data["last_active"]

        # Also sync description from API in case it was changed externally
        if agent_data.get("description"):
            config.agent.description = agent_data["description"]

        save_agent_config(self._base_path, config)

        return config
