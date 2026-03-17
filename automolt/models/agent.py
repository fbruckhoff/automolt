"""Pydantic models for agent data and configuration."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from automolt.models.llm_provider import LLMProvider


class VerificationStatus(str, Enum):
    """Enumeration of possible verification status values."""

    PENDING = "pending_verification"
    VERIFIED = "verified"


class AutomationStage(str, Enum):
    """Named LLM-backed stages in the automation pipeline."""

    ANALYSIS = "analysis"
    ACTION = "action"
    SUBMOLT_PLANNER = "submolt_planner"


class Agent(BaseModel):
    """Core agent identity data stored in agent.json."""

    handle: str = Field(min_length=1, max_length=50)
    description: str = Field(min_length=1, max_length=500)

    @field_validator("handle", "description", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        """Strip leading/trailing whitespace before validation."""
        if isinstance(v, str):
            return v.strip()
        return v

    api_key: str | None = None
    claim_url: str | None = None
    verification_code: str | None = None
    verification_status: VerificationStatus = VerificationStatus.PENDING

    # Fields populated from the Moltbook API profile response
    x_handle: str | None = None
    avatar_url: str | None = None
    karma: int | None = None
    follower_count: int | None = None
    following_count: int | None = None
    is_active: bool | None = None
    created_at: str | None = None
    last_active: str | None = None


class StageLLMConfig(BaseModel):
    """LLM provider/model selection for one automation stage."""

    provider: LLMProvider = LLMProvider.OPENAI
    model: str = Field(default="gpt-4o-mini", min_length=1, max_length=200)

    @field_validator("model", mode="before")
    @classmethod
    def normalize_model(cls, value: str) -> str:
        """Normalize model names by trimming whitespace."""
        if isinstance(value, str):
            return value.strip()
        return value


class AutomationLLM(BaseModel):
    """Top-level LLM settings for per-stage provider/model routing."""

    analysis: StageLLMConfig = Field(default_factory=StageLLMConfig)
    action: StageLLMConfig = Field(default_factory=StageLLMConfig)
    submolt_planner: StageLLMConfig = Field(default_factory=StageLLMConfig)


class Automation(BaseModel):
    """Automation configuration for the heartbeat run loop and search targeting."""

    enabled: bool = False
    interval_seconds: int = Field(default=600, description="Seconds between heartbeat cycles")
    last_heartbeat_at: datetime | None = Field(default=None, description="Timestamp of the last completed heartbeat cycle")
    search_query: str | None = Field(default=None, description="Moltbook search query to find relevant discussions")
    cutoff_days: int = Field(default=90, ge=1, description="Days before un-acted items are pruned from the queue")
    llm: AutomationLLM = Field(default_factory=AutomationLLM, description="LLM provider and model configuration per stage")


class AgentConfig(BaseModel):
    """Top-level model representing the agent.json file structure."""

    agent: Agent
    automation: Automation = Field(default_factory=Automation)


class AgentRegistrationResponse(BaseModel):
    """Parsed response from the Moltbook registration API."""

    api_key: str = Field(min_length=1)
    claim_url: str = Field(min_length=1)
    verification_code: str = Field(min_length=1)
