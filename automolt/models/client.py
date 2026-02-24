"""Pydantic models for client configuration."""

from pydantic import AliasChoices, BaseModel, Field

from automolt.models.llm_provider import LLMProviderConfig


class ClientConfig(BaseModel):
    """Client-level configuration stored in client.json."""

    last_active_agent: str | None = Field(
        default=None,
        validation_alias=AliasChoices("last_active_agent", "active_agent"),
        serialization_alias="last_active_agent",
    )
    api_timeout_seconds: float = Field(default=30.0, description="Timeout for HTTP requests to Moltbook API")
    llm_provider_config: LLMProviderConfig = Field(
        default_factory=LLMProviderConfig,
        validation_alias=AliasChoices("llm_provider_config", "llm_provider_credentials"),
        serialization_alias="llm_provider_config",
        description="Global LLM provider config shared across local agents.",
    )
