"""Provider-neutral interfaces and exceptions for automation LLM clients."""

from __future__ import annotations

from typing import Protocol, TypeAlias

from pydantic import BaseModel

from automolt.models.llm import ActionPlan, AnalysisDecision


class LLMClientError(Exception):
    """Raised when an LLM provider request fails.

    Attributes:
        reason_code: Stable machine-readable reason identifier.
    """

    def __init__(self, message: str, reason_code: str):
        self.reason_code = reason_code
        super().__init__(message)


LLMResponseModel: TypeAlias = type[BaseModel]


class BaseLLMClient(Protocol):
    """Protocol that all provider-specific LLM clients must implement."""

    def analyze_relevance(
        self,
        *,
        model: str,
        api_key: str,
        system_prompt: str,
        user_prompt: str,
    ) -> AnalysisDecision:
        """Run analysis-stage relevance classification."""

    def generate_action(
        self,
        *,
        model: str,
        api_key: str,
        system_prompt: str,
        user_prompt: str,
    ) -> ActionPlan:
        """Run action-stage reply planning."""
