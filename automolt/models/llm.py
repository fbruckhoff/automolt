"""Pydantic models for automation LLM stage outputs."""

from pydantic import AliasChoices, BaseModel, Field, field_validator


class AnalysisDecision(BaseModel):
    """Structured relevance-classification output from analysis stage."""

    is_relevant: bool
    relevance_rationale: str = Field(
        min_length=1,
        max_length=120,
        validation_alias=AliasChoices("relevance_rationale", "reason"),
    )

    @field_validator("relevance_rationale", mode="before")
    @classmethod
    def normalize_relevance_rationale(cls, value: str) -> str:
        """Normalize analysis reason text before validation."""
        if isinstance(value, str):
            return value.strip()[:120]
        return value


class ActionPlan(BaseModel):
    """Structured action-stage output describing reply text and upvote intent."""

    reply_text: str = Field(
        min_length=1,
        max_length=4000,
        validation_alias=AliasChoices("reply_text", "reply_content"),
    )
    upvote: bool = False

    @field_validator("reply_text", mode="before")
    @classmethod
    def normalize_reply_text(cls, value: str) -> str:
        """Normalize reply text by trimming whitespace before validation."""
        if isinstance(value, str):
            normalized = value.strip()
            return normalized
        return value
