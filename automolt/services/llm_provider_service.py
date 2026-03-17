"""Catalog and validation helpers for automation LLM providers and models."""

from __future__ import annotations

import json
import logging
from hashlib import sha256
from pathlib import Path

from openai import OpenAI, OpenAIError

from automolt.models.agent import AutomationStage
from automolt.models.llm_provider import LLMProvider

logger = logging.getLogger(__name__)

DEFAULT_OPENAI_RESPONSES_ALLOW_PREFIXES: tuple[str, ...] = (
    "gpt-5",
    "gpt-5.1",
    "gpt-5.2",
    "gpt-4o",
    "gpt-4.1",
    "o4",
    "o3",
    "o1",
)

DEFAULT_OPENAI_FALLBACK_MODELS: tuple[str, ...] = (
    "gpt-5",
    "gpt-5-mini",
    "gpt-4o-mini",
    "gpt-4.1-mini",
    "o4-mini",
)

DEFAULT_OPENAI_RESPONSES_DENY_SUBSTRINGS: tuple[str, ...] = (
    "audio",
    "realtime",
    "transcribe",
    "tts",
    "embedding",
    "moderation",
)

DEFAULT_STAGE_MODELS: dict[AutomationStage, str] = {
    AutomationStage.ANALYSIS: "gpt-4o-mini",
    AutomationStage.ACTION: "gpt-4o-mini",
    AutomationStage.SUBMOLT_PLANNER: "gpt-4o-mini",
}


class LLMProviderService:
    """Provide provider/model catalogs for automation setup and validation."""

    def __init__(self, models_registry_path: Path | None = None):
        self._models_registry_path = models_registry_path or Path(__file__).resolve().parents[1] / "data" / "models.json"
        self._openai_allow_prefixes, self._openai_fallback_models, self._openai_deny_substrings = self._load_openai_model_registry()
        self._openai_models_cache: dict[str, tuple[str, ...]] = {}
        self._last_model_fetch_warning: str | None = None

    def list_supported_providers(self) -> tuple[LLMProvider, ...]:
        """Return providers currently supported by this CLI."""
        return (LLMProvider.OPENAI,)

    def list_provider_values(self) -> tuple[str, ...]:
        """Return provider values suitable for Click choice prompts."""
        return tuple(provider.value for provider in self.list_supported_providers())

    def list_models_for_provider(self, provider: LLMProvider) -> tuple[str, ...]:
        """Return known model names for a provider.

        Args:
            provider: Provider to resolve model names for.

        Returns:
            Tuple of model identifiers.

        Raises:
            ValueError: If provider is not recognized.
        """
        if provider == LLMProvider.OPENAI:
            return self._openai_fallback_models

        raise ValueError(f"Unsupported provider '{provider.value}'.")

    def fetch_available_models(self, api_key: str) -> list[str]:
        """Fetch OpenAI-accessible Responses-compatible models for setup.

        Returns fallback models when remote model listing is unavailable.
        """
        normalized_api_key = api_key.strip()
        if not normalized_api_key:
            raise ValueError("OpenAI API key is required to fetch available models.")

        cache_key = sha256(normalized_api_key.encode("utf-8")).hexdigest()
        cached_models = self._openai_models_cache.get(cache_key)
        if cached_models is not None:
            self._last_model_fetch_warning = None
            return list(cached_models)

        try:
            client = OpenAI(api_key=normalized_api_key)
            fetched_model_ids = [model_id for model_id in (self._extract_model_id(model) for model in client.models.list()) if model_id]
        except OpenAIError as exc:
            warning = "Could not fetch OpenAI model catalog from the API. Using fallback Responses-compatible model defaults."
            logger.warning("%s request_id=%s", warning, getattr(exc, "request_id", None))
            fallback_models = self._with_fetch_warning(warning)
            self._openai_models_cache[cache_key] = fallback_models
            return list(fallback_models)
        except Exception as exc:  # pragma: no cover - defensive guard for unexpected SDK changes
            warning = "Could not fetch OpenAI model catalog due to an unexpected error. Using fallback Responses-compatible model defaults."
            logger.warning("%s error=%s", warning, exc)
            fallback_models = self._with_fetch_warning(warning)
            self._openai_models_cache[cache_key] = fallback_models
            return list(fallback_models)

        compatible_models = self._filter_responses_compatible_models(fetched_model_ids)
        if not compatible_models:
            warning = "OpenAI model catalog returned no Responses-compatible models for this account. Using fallback Responses-compatible model defaults."
            logger.warning(warning)
            fallback_models = self._with_fetch_warning(warning)
            self._openai_models_cache[cache_key] = fallback_models
            return list(fallback_models)

        resolved_models = tuple(compatible_models)
        self._openai_models_cache[cache_key] = resolved_models
        self._last_model_fetch_warning = None
        return list(resolved_models)

    def consume_last_model_fetch_warning(self) -> str | None:
        """Return and clear the latest dynamic model-fetch warning message."""
        warning = self._last_model_fetch_warning
        self._last_model_fetch_warning = None
        return warning

    def default_model_for_stage(self, stage: AutomationStage, provider: LLMProvider) -> str:
        """Return the default model for one stage/provider pair."""
        models = self.list_models_for_provider(provider)
        default_model = DEFAULT_STAGE_MODELS.get(stage, models[0])
        if default_model in models:
            return default_model
        return models[0]

    def validate_stage_model(self, provider: LLMProvider, model: str) -> None:
        """Validate that a model is available for the given provider.

        Args:
            provider: Chosen provider.
            model: Chosen model identifier.

        Raises:
            ValueError: If the model is empty or unsupported.
        """
        normalized_model = model.strip()
        if not normalized_model:
            raise ValueError("Model cannot be empty.")

        if provider == LLMProvider.OPENAI:
            if self._is_responses_compatible_model(normalized_model):
                return
            raise ValueError(f"Model '{normalized_model}' is not supported for provider '{provider.value}'.")

        raise ValueError(f"Unsupported provider '{provider.value}'.")

    def _is_responses_compatible_model(self, model: str) -> bool:
        """Return whether a model id is known to support Responses API usage."""
        normalized_model = model.strip().lower()
        if not normalized_model:
            return False

        if not any(normalized_model.startswith(prefix) for prefix in self._openai_allow_prefixes):
            return False

        return not any(denied in normalized_model for denied in self._openai_deny_substrings)

    def _filter_responses_compatible_models(self, model_ids: list[str]) -> list[str]:
        """Filter and normalize OpenAI model ids to the supported compatibility set."""
        compatible = {model_id.strip() for model_id in model_ids if model_id and self._is_responses_compatible_model(model_id)}
        return sorted(compatible)

    def _extract_model_id(self, model_obj: object) -> str | None:
        """Extract one model id from OpenAI SDK model objects defensively."""
        raw_id = getattr(model_obj, "id", None)
        if isinstance(raw_id, str):
            normalized_id = raw_id.strip()
            return normalized_id or None
        return None

    def _with_fetch_warning(self, warning: str) -> tuple[str, ...]:
        """Store latest fetch warning and return configured fallback model list."""
        self._last_model_fetch_warning = warning
        return self._openai_fallback_models

    def _load_openai_model_registry(self) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
        """Load OpenAI model compatibility config from the JSON registry."""
        default_registry = (
            DEFAULT_OPENAI_RESPONSES_ALLOW_PREFIXES,
            DEFAULT_OPENAI_FALLBACK_MODELS,
            DEFAULT_OPENAI_RESPONSES_DENY_SUBSTRINGS,
        )

        try:
            raw_payload = self._models_registry_path.read_text(encoding="utf-8")
            payload = json.loads(raw_payload)
        except OSError, json.JSONDecodeError:
            logger.warning(
                "Could not load model compatibility registry at '%s'; using built-in defaults.",
                self._models_registry_path,
            )
            return default_registry

        openai_payload = payload.get("openai") if isinstance(payload, dict) else None
        responses_payload = openai_payload.get("responses_api") if isinstance(openai_payload, dict) else None
        if not isinstance(responses_payload, dict):
            logger.warning(
                "Invalid model compatibility registry format at '%s'; using built-in defaults.",
                self._models_registry_path,
            )
            return default_registry

        allow_prefixes = self._normalize_string_tuple(
            responses_payload.get("allow_prefixes"),
            fallback=DEFAULT_OPENAI_RESPONSES_ALLOW_PREFIXES,
        )
        fallback_models = self._normalize_string_tuple(
            responses_payload.get("fallback_models"),
            fallback=DEFAULT_OPENAI_FALLBACK_MODELS,
        )
        deny_substrings = self._normalize_string_tuple(
            responses_payload.get("deny_substrings"),
            fallback=DEFAULT_OPENAI_RESPONSES_DENY_SUBSTRINGS,
        )
        return allow_prefixes, fallback_models, deny_substrings

    def _normalize_string_tuple(self, value: object, fallback: tuple[str, ...]) -> tuple[str, ...]:
        """Normalize JSON-loaded string arrays to deduplicated tuples."""
        if not isinstance(value, list):
            return fallback

        seen: set[str] = set()
        normalized_values: list[str] = []
        for item in value:
            if not isinstance(item, str):
                continue

            normalized_item = item.strip()
            if not normalized_item or normalized_item in seen:
                continue

            seen.add(normalized_item)
            normalized_values.append(normalized_item)

        if not normalized_values:
            return fallback
        return tuple(normalized_values)
