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
    promote_to_submolt: bool = False
    promotion_topic: str | None = Field(
        default=None,
        max_length=120,
        validation_alias=AliasChoices("promotion_topic", "submolt_topic"),
    )

    @field_validator("reply_text", mode="before")
    @classmethod
    def normalize_reply_text(cls, value: str) -> str:
        """Normalize reply text by trimming whitespace before validation."""
        if isinstance(value, str):
            normalized = value.strip()
            return normalized
        return value

    @field_validator("promotion_topic", mode="before")
    @classmethod
    def normalize_promotion_topic(cls, value: str | None) -> str | None:
        """Normalize optional reactive-promotion topic text."""
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value


class SubmoltPlannerPlan(BaseModel):
    """Structured submolt-planner output for autonomous create/post decisions."""

    should_create_submolt: bool
    submolt_name: str | None = Field(default=None, min_length=1, max_length=80)
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    allow_crypto: bool = False
    should_post: bool = False
    post_title: str | None = Field(default=None, min_length=1, max_length=300)
    post_content: str | None = Field(default=None, min_length=1, max_length=4000)
    post_url: str | None = Field(default=None, min_length=1, max_length=2000)
    should_link_in_followup_reply: bool = False
    followup_reply_text: str | None = Field(default=None, min_length=1, max_length=1000)
    decision_rationale: str = Field(min_length=1, max_length=300)

    @field_validator(
        "submolt_name",
        "display_name",
        "description",
        "post_title",
        "post_content",
        "post_url",
        "followup_reply_text",
        "decision_rationale",
        mode="before",
    )
    @classmethod
    def normalize_text_fields(cls, value: str | None) -> str | None:
        """Trim planner text fields before schema validation."""
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value
