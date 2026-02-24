"""OpenAI-backed LLM client for automation analysis and action stages."""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    OpenAIError,
    RateLimitError,
)
from pydantic import ValidationError

from automolt.models.llm import ActionPlan, AnalysisDecision
from automolt.services.base_llm_client import LLMClientError

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class StructuredCompletionResult:
    """Parsed stage output plus raw provider response content."""

    parsed_output: AnalysisDecision | ActionPlan
    raw_response: str


class OpenAILLMClient:
    """Execute structured stage calls against OpenAI Responses API."""

    def __init__(self, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS):
        self._timeout_seconds = timeout_seconds

    def analyze_relevance(
        self,
        *,
        model: str,
        api_key: str,
        max_output_tokens: int,
        system_prompt: str,
        user_prompt: str,
    ) -> AnalysisDecision:
        """Run analysis-stage relevance classification."""
        result = self.analyze_relevance_with_trace(
            model=model,
            api_key=api_key,
            max_output_tokens=max_output_tokens,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        return result.parsed_output

    def analyze_relevance_with_trace(
        self,
        *,
        model: str,
        api_key: str,
        max_output_tokens: int,
        system_prompt: str,
        user_prompt: str,
    ) -> StructuredCompletionResult:
        """Run analysis-stage relevance classification and return response trace."""
        return self._request_structured_completion(
            model=model,
            api_key=api_key,
            max_output_tokens=max_output_tokens,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=AnalysisDecision,
        )

    def generate_action(
        self,
        *,
        model: str,
        api_key: str,
        max_output_tokens: int,
        system_prompt: str,
        user_prompt: str,
    ) -> ActionPlan:
        """Run action-stage reply planning."""
        result = self.generate_action_with_trace(
            model=model,
            api_key=api_key,
            max_output_tokens=max_output_tokens,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        return result.parsed_output

    def generate_action_with_trace(
        self,
        *,
        model: str,
        api_key: str,
        max_output_tokens: int,
        system_prompt: str,
        user_prompt: str,
    ) -> StructuredCompletionResult:
        """Run action-stage reply planning and return response trace."""
        return self._request_structured_completion(
            model=model,
            api_key=api_key,
            max_output_tokens=max_output_tokens,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=ActionPlan,
        )

    def _request_structured_completion(
        self,
        *,
        model: str,
        api_key: str,
        max_output_tokens: int,
        system_prompt: str,
        user_prompt: str,
        response_model: type[AnalysisDecision] | type[ActionPlan],
    ) -> StructuredCompletionResult:
        """Request a strict structured response and validate with Pydantic."""
        client = self._create_openai_client(api_key)
        schema = self._normalize_schema_for_strict_mode(response_model.model_json_schema())

        try:
            response = client.responses.create(
                model=model,
                instructions=system_prompt,
                input=user_prompt,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": response_model.__name__,
                        "strict": True,
                        "schema": schema,
                    }
                },
                max_output_tokens=max_output_tokens,
                store=False,
            )
        except AuthenticationError as exc:
            logger.warning("OpenAI authentication failed (request_id=%s).", getattr(exc, "request_id", None))
            raise LLMClientError(
                "OpenAI authentication failed. Check your API key.",
                reason_code="openai-auth-failed",
            ) from exc
        except APITimeoutError as exc:
            logger.warning("OpenAI request timed out (request_id=%s).", getattr(exc, "request_id", None))
            raise LLMClientError(
                "OpenAI request timed out.",
                reason_code="provider-timeout",
            ) from exc
        except APIConnectionError as exc:
            logger.warning("OpenAI connection error (request_id=%s).", getattr(exc, "request_id", None))
            raise LLMClientError(
                "Failed to connect to OpenAI.",
                reason_code="provider-network",
            ) from exc
        except RateLimitError as exc:
            logger.warning("OpenAI rate limit exceeded (request_id=%s).", getattr(exc, "request_id", None))
            raise LLMClientError(
                "OpenAI rate limit exceeded.",
                reason_code="provider-rate-limited",
            ) from exc
        except APIStatusError as exc:
            error_code, error_message = self._extract_status_error_details(exc)
            logger.warning(
                "OpenAI status error status=%s request_id=%s code=%s message=%s",
                exc.status_code,
                getattr(exc, "request_id", None),
                error_code,
                error_message,
            )
            if exc.status_code >= 500:
                raise LLMClientError(
                    "OpenAI server error.",
                    reason_code="provider-server-error",
                ) from exc

            reason_code = self._map_status_error_reason_code(error_code)
            detail_suffix = self._format_status_error_details(error_code, error_message)
            raise LLMClientError(
                f"OpenAI request failed due to a non-success provider status.{detail_suffix}",
                reason_code=reason_code,
            ) from exc
        except OpenAIError as exc:
            logger.warning("OpenAI request failed (request_id=%s).", getattr(exc, "request_id", None))
            raise LLMClientError(
                "OpenAI request failed.",
                reason_code="provider-request-failed",
            ) from exc

        status = getattr(response, "status", "completed")
        if status == "failed":
            error_payload = getattr(response, "error", None)
            error_code = self._read_field(error_payload, "code", "unknown")
            error_message = self._read_field(error_payload, "message", "")
            raise LLMClientError(
                f"OpenAI response failed (code: {error_code}): {error_message}",
                reason_code="provider-request-failed",
            )

        if status == "incomplete":
            incomplete_details = getattr(response, "incomplete_details", None)
            reason = self._read_field(incomplete_details, "reason", "unknown")
            raise LLMClientError(
                f"OpenAI response was incomplete (reason: {reason}).",
                reason_code="provider-incomplete-response",
            )

        if self._response_contains_refusal(response):
            raise LLMClientError(
                "OpenAI refused the request for safety reasons.",
                reason_code="provider-refusal",
            )

        output_text = getattr(response, "output_text", None)
        if not isinstance(output_text, str) or not output_text.strip():
            raise LLMClientError(
                "OpenAI returned an empty response.",
                reason_code="provider-empty-response",
            )

        logger.debug(
            "OpenAI response received for model '%s' (request_id=%s).",
            model,
            getattr(response, "_request_id", None),
        )

        try:
            parsed_output = self._parse_json_content(output_text, response_model)
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning(
                "OpenAI response failed local JSON parsing/validation (request_id=%s).",
                getattr(response, "_request_id", None),
                exc_info=exc,
            )
            raise LLMClientError(
                "OpenAI response could not be parsed as valid JSON for the expected schema.",
                reason_code="provider-invalid-json",
            ) from exc

        return StructuredCompletionResult(
            parsed_output=parsed_output,
            raw_response=output_text,
        )

    def _normalize_schema_for_strict_mode(self, schema: dict[str, Any]) -> dict[str, Any]:
        """Normalize a Pydantic JSON schema to OpenAI strict-mode requirements."""
        normalized_schema = deepcopy(schema)
        self._normalize_schema_node(normalized_schema)
        return normalized_schema

    def _normalize_schema_node(self, node: Any) -> None:
        """Recursively normalize schema nodes for strict structured outputs."""
        if isinstance(node, dict):
            node.pop("default", None)

            properties = node.get("properties")
            if node.get("type") == "object" and isinstance(properties, dict):
                node["required"] = list(properties.keys())
                node["additionalProperties"] = False

            for value in node.values():
                self._normalize_schema_node(value)
            return

        if isinstance(node, list):
            for item in node:
                self._normalize_schema_node(item)

    def _extract_status_error_details(self, exc: APIStatusError) -> tuple[str | None, str | None]:
        """Extract provider error code/message from an APIStatusError payload."""
        response = getattr(exc, "response", None)
        if response is None:
            return None, None

        payload: Any = None
        read_json = getattr(response, "json", None)
        if callable(read_json):
            try:
                payload = read_json()
            except Exception:
                payload = None

        if not isinstance(payload, dict):
            return None, None

        error_payload = payload.get("error")
        if not isinstance(error_payload, dict):
            error_payload = payload

        code = error_payload.get("code")
        message = error_payload.get("message")
        normalized_code = code.strip() if isinstance(code, str) and code.strip() else None
        normalized_message = message.strip() if isinstance(message, str) and message.strip() else None
        return normalized_code, normalized_message

    def _map_status_error_reason_code(self, error_code: str | None) -> str:
        """Map provider status error payloads to stable reason codes."""
        normalized = (error_code or "").strip().lower()
        if normalized in {"context_length_exceeded", "max_input_tokens", "input_too_long"}:
            return "provider-input-too-large"
        if normalized in {"unsupported_model", "model_not_found", "invalid_model", "unsupported_parameter"}:
            return "provider-model-not-supported"
        return "provider-http-error"

    def _format_status_error_details(self, error_code: str | None, error_message: str | None) -> str:
        """Format concise status-error details for user-visible error messages."""
        details: list[str] = []
        if error_code:
            details.append(f"code={error_code}")
        if error_message:
            details.append(f"message={error_message}")
        if not details:
            return ""
        return " (" + "; ".join(details) + ")"

    def _create_openai_client(self, api_key: str) -> OpenAI:
        """Create an OpenAI SDK client with deterministic retry/timeout behavior."""
        return OpenAI(
            api_key=api_key,
            timeout=self._timeout_seconds,
            max_retries=1,
        )

    def _response_contains_refusal(self, response: Any) -> bool:
        """Return True when a response contains refusal content items."""
        output_items = getattr(response, "output", []) or []
        for output_item in output_items:
            if self._read_field(output_item, "type") != "message":
                continue

            for content_item in self._read_field(output_item, "content", []) or []:
                if self._read_field(content_item, "type") == "refusal":
                    return True

        return False

    def _read_field(self, payload: Any, field_name: str, default: Any = None) -> Any:
        """Read one field from a dict-like or object-like SDK payload."""
        if isinstance(payload, dict):
            return payload.get(field_name, default)

        return getattr(payload, field_name, default)

    def _parse_json_content(
        self,
        content: str,
        response_model: type[AnalysisDecision] | type[ActionPlan],
    ) -> AnalysisDecision | ActionPlan:
        """Parse JSON text and validate against a Pydantic model."""
        parsed_data = json.loads(content)
        return response_model.model_validate(parsed_data)
