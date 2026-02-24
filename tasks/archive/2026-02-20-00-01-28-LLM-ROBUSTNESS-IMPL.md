# LLM Robustness Implementation Plan

This directive documents the tasks needed to make the automation system's LLM response format handling more robust, minimizing costly fallback retries.

## Tasks

- [ ] **1. Update System Prompts (`moltbook/services/automation_service.py`)**
  - Locate `ANALYSIS_SYSTEM_PROMPT` and `ACTION_SYSTEM_PROMPT` in `moltbook/services/automation_service.py`.
  - Update the prompts to explicitly demand minified JSON and forbid the use of markdown fences or prose:
    ```python
    ANALYSIS_SYSTEM_PROMPT = (
        "You are an analysis classifier. "
        "Return ONLY valid minified JSON with keys: is_relevant (boolean), relevance_rationale (string). "
        "relevance_rationale must be at most 120 characters. "
        "Do NOT use markdown fences (```) and do not include any prose."
    )

    ACTION_SYSTEM_PROMPT = (
        "You are an action planner for social replies. "
        "Return ONLY valid minified JSON with keys: should_reply (boolean), reply_content (string or null), reason (string). "
        "Do NOT use markdown fences (```) and do not include any prose."
    )
    ```

- [ ] **2. Improve Parsing Lenience (`moltbook/services/openai_llm_client.py`)**
  - Update `OpenAILLMClient._parse_json_content` to intelligently strip markdown fences before parsing.
  - Implementation:
    ```python
    def _parse_json_content(
        self,
        content: str,
        response_model: type[AnalysisDecision] | type[ActionPlan],
    ) -> AnalysisDecision | ActionPlan:
        """Parse JSON text and validate against a Pydantic model."""
        # Strip markdown blocks if present
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]  # remove first line (e.g. ```json)
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()        # remove last line (```)

        parsed_data = json.loads(cleaned)
        return response_model.model_validate(parsed_data)
    ```

- [ ] **3. Leverage Native Provider Features (`moltbook/services/openai_llm_client.py`)**
  - Ensure the API is explicitly told to return JSON format to guarantee structure at the API level.
  - Update the `payload` dict inside `OpenAILLMClient._send_completion_request` to include the `response_format` parameter:
    ```python
        payload = {
            "model": model,
            "input": input_text,
            "max_output_tokens": max_output_tokens,
            "temperature": temperature,
            "response_format": {"type": "json_object"}
        }
    ```
