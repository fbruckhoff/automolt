"""Stage-aware LLM execution router for automation analysis and action calls."""

from __future__ import annotations

from dataclasses import dataclass

from automolt.models.agent import AgentConfig, AutomationStage, StageLLMConfig
from automolt.models.llm import ActionPlan, AnalysisDecision
from automolt.models.llm_provider import LLMProvider, LLMProviderConfig
from automolt.services.base_llm_client import LLMClientError
from automolt.services.llm_provider_service import LLMProviderService
from automolt.services.openai_llm_client import OpenAILLMClient, StructuredCompletionResult


@dataclass(frozen=True)
class StageExecutionResult:
    """Parsed stage output together with the raw provider response text."""

    parsed_output: AnalysisDecision | ActionPlan
    raw_response: str


class LLMExecutionService:
    """Resolve configured providers and execute stage-specific LLM requests."""

    def __init__(self):
        self._provider_service = LLMProviderService()
        self._openai_client = OpenAILLMClient()

    def analyze(
        self,
        *,
        config: AgentConfig,
        provider_config: LLMProviderConfig,
        system_prompt: str,
        user_prompt: str,
    ) -> StageExecutionResult:
        """Run the analysis stage LLM call for one queue item."""
        return self._run_stage(
            stage=AutomationStage.ANALYSIS,
            stage_config=config.automation.llm.analysis,
            provider_config=provider_config,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

    def generate_action(
        self,
        *,
        config: AgentConfig,
        provider_config: LLMProviderConfig,
        system_prompt: str,
        user_prompt: str,
    ) -> StageExecutionResult:
        """Run the action stage LLM call for one queue item."""
        return self._run_stage(
            stage=AutomationStage.ACTION,
            stage_config=config.automation.llm.action,
            provider_config=provider_config,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

    def _run_stage(
        self,
        *,
        stage: AutomationStage,
        stage_config: StageLLMConfig,
        provider_config: LLMProviderConfig,
        system_prompt: str,
        user_prompt: str,
    ) -> StageExecutionResult:
        """Dispatch one stage call to the configured provider client."""
        self._provider_service.validate_stage_model(stage_config.provider, stage_config.model)

        if stage_config.provider != LLMProvider.OPENAI:
            raise LLMClientError(
                f"Provider '{stage_config.provider.value}' is not supported for runtime execution.",
                reason_code="provider-not-supported",
            )

        api_key = provider_config.openai.api_key
        if not api_key:
            raise LLMClientError(
                "OpenAI API key is required for the selected stage provider.",
                reason_code="missing-provider-config",
            )

        max_output_tokens = provider_config.openai.max_output_tokens

        if stage == AutomationStage.ANALYSIS:
            completion_result = self._openai_client.analyze_relevance_with_trace(
                model=stage_config.model,
                api_key=api_key,
                max_output_tokens=max_output_tokens,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            return self._to_stage_execution_result(completion_result)

        completion_result = self._openai_client.generate_action_with_trace(
            model=stage_config.model,
            api_key=api_key,
            max_output_tokens=max_output_tokens,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        return self._to_stage_execution_result(completion_result)

    def _to_stage_execution_result(self, result: StructuredCompletionResult) -> StageExecutionResult:
        """Map provider completion results to service-level stage results."""
        return StageExecutionResult(
            parsed_output=result.parsed_output,
            raw_response=result.raw_response,
        )
