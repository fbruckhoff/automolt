"""Pydantic models for LLM provider enums and provider config schemas."""

from enum import Enum

from pydantic import AliasChoices, BaseModel, Field, field_validator

DEFAULT_OPENAI_MAX_OUTPUT_TOKENS = 1500


class LLMProvider(str, Enum):
    """Supported LLM providers for automation stages."""

    OPENAI = "openai"


class OpenAIProviderConfig(BaseModel):
    """Global OpenAI provider configuration used by automation stages."""

    api_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
        description="OpenAI API key used by automation LLM stages.",
        repr=False,
    )
    max_output_tokens: int = Field(
        default=DEFAULT_OPENAI_MAX_OUTPUT_TOKENS,
        ge=1,
        le=100_000,
        description="Hard max output token cutoff for OpenAI Responses API calls.",
    )

    @field_validator("api_key", mode="before")
    @classmethod
    def normalize_api_key(cls, value: str | None) -> str | None:
        """Normalize OpenAI API key input by trimming whitespace."""
        if value is None:
            return None
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value

    @field_validator("max_output_tokens", mode="before")
    @classmethod
    def normalize_max_output_tokens(cls, value: int | str | None) -> int:
        """Normalize max_output_tokens and fallback to default when blank."""
        if value is None:
            return DEFAULT_OPENAI_MAX_OUTPUT_TOKENS

        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                return DEFAULT_OPENAI_MAX_OUTPUT_TOKENS
            return int(normalized)

        return int(value)


class LLMProviderConfig(BaseModel):
    """Provider config registry shared across all local agents."""

    openai: OpenAIProviderConfig = Field(
        default_factory=OpenAIProviderConfig,
        validation_alias=AliasChoices("openai", "openapi"),
        serialization_alias="openapi",
    )
