# OPENAI Package Refactor Implementation Plan

## 1) Objective

Refactor `moltbook/services/openai_llm_client.py` to use the official `openai` Python package (Responses API) instead of manual `httpx` transport handling.

This plan is intentionally implementation-ready but **does not apply code changes yet**.

Primary goals:

1. Keep the current stage-level interfaces (`analyze_relevance*`, `generate_action*`) unchanged for callers.
2. Preserve strict structured JSON validation via existing Pydantic models (`AnalysisDecision`, `ActionPlan`).
3. Preserve stable `LLMClientError.reason_code` semantics used by runtime error handling.
4. Remove manual HTTP payload plumbing and manual response tree extraction logic.
5. Use the **Responses API** exclusively for both automation stages:
   - filter stage (`analyze_relevance*`)
   - acting stage (`generate_action*`, the stage that posts/comments)
6. Use the official SDK (`openai`) with Responses API request shape (`client.responses.create(...)` with `text.format.json_schema` and `strict: true`).

---

## 2) Current Baseline (What exists now)

`moltbook/services/openai_llm_client.py` currently includes:

- Direct `httpx.Client` calls to `https://api.openai.com/v1/responses`
- Manual headers and status-code branching
- Manual retries (`MAX_TRANSPORT_ATTEMPTS`)
- Manual output extraction (`_extract_response_content`)
- One repair pass that asks the model to rewrite invalid JSON

This creates unnecessary transport complexity and extra maintenance surface area.

---

## 3) Target Architecture

Replace manual HTTP transport with official SDK client calls:

- Use `from openai import OpenAI`
- **Primary runtime path**: Use `client.responses.create(...)` with explicit structured-output payload:
  - `instructions=system_prompt`
  - `input=user_prompt`
  - `text={"format": {"type": "json_schema", "name": ..., "strict": true, "schema": ...}}`
  - `store=False`
- Read raw text via `response.output_text` for trace/log purposes
- **Keep** local Pydantic validation as a second pass for alias/normalization behavior specific to our models
- Never assume `response.output[0]` is the assistant text; inspect output item types defensively
- Keep all untrusted content in `input` (user message content), never in `instructions`

### Responses API Structured Output — wire-level shape

For Responses API calls, structured output is expressed via the `text` parameter:

```json
{
  "text": {
    "format": {
      "type": "json_schema",
      "name": "<schema_name>",
      "strict": true,
      "schema": { ... }
    }
  }
}
```

The implementation should construct this payload explicitly and call `responses.create()`. This is the canonical path in both skill references and avoids SDK-version ambiguity around helper methods.

### Python SDK canonical pattern

```python
from openai import OpenAI
from pydantic import BaseModel

client = OpenAI()

class CalendarEvent(BaseModel):
    name: str
    date: str
    participants: list[str]

response = client.responses.create(
    model="gpt-4o-mini",
    instructions="Extract the event information.",
    input="Alice and Bob are going to a science fair on Friday.",
    text={
        "format": {
            "type": "json_schema",
            "name": "CalendarEvent",
            "strict": True,
            "schema": CalendarEvent.model_json_schema(),
        }
    },
    store=False,
)
event = CalendarEvent.model_validate_json(response.output_text)
```

**Alternate form (message array):** The skill reference shows an equivalent pattern using `input` as a message array with explicit `developer`/`user` roles instead of `instructions`:

```python
response = client.responses.create(
    model="gpt-4o-mini",
    input=[
        {"role": "developer", "content": "Extract the event information."},
        {"role": "user", "content": "Alice and Bob are going to a science fair on Friday."},
    ],
    text={
        "format": {
            "type": "json_schema",
            "name": "CalendarEvent",
            "strict": True,
            "schema": CalendarEvent.model_json_schema(),
        }
    },
    store=False,
)
```

Both forms produce equivalent model behavior. Our implementation uses the `instructions=` form for cleaner semantics.

Our implementation will follow the `instructions=` pattern with `AnalysisDecision` and `ActionPlan` as local validation models.

**Note on `instructions` vs `developer` role:** The `instructions` parameter is the preferred way to pass system-level content in the Responses API. It is equivalent to placing a `developer` role message at the start of the `input` array, but with cleaner semantics. Note that `instructions` only applies to the current request — it does not persist across chained responses via `previous_response_id`. The existing code uses `"role": "system"` which is the legacy Chat Completions convention — the Responses API uses `"developer"` as the system-priority role. By using `instructions`, we avoid both the legacy role name issue and the verbosity of message-array construction.

### No `openai_structured` package

There exists a third-party package `openai_structured` that adds schema utilities on top of the SDK. We **do not need it** because the official `openai` SDK already supports Responses API structured outputs via `text.format`.

### Only Responses API models supported

The CLI shall **only** support models that are compatible with the Responses API. Other OpenAI models (legacy chat-completions-only models) will not be supported. The `automation setup` flow will enforce this (see §15).

---

## 4) Files In Scope

### Must change

1. `moltbook/services/openai_llm_client.py`
2. `moltbook/services/llm_provider_service.py`
3. `moltbook/commands/automation/setup_command.py`
4. `moltbook/services/automation_service.py` (update `_build_stage_prompt_payload` at line 764 — log serialization to reflect `instructions` instead of `"system"` role message)
5. `pyproject.toml`
6. `uv.lock` (regenerated by dependency sync)
7. `docs/AUTOMATION.md` (LLM transport details)
8. `README.md` (tech stack wording for automation LLM calls)
9. `moltbook/data/models.json` (Responses API model compatibility registry + fallback catalog)

### New test files (no `tests/` directory exists yet)

10. `tests/services/test_openai_llm_client.py` **(new)**
11. `tests/services/test_llm_provider_service.py` **(new)**
12. `tests/commands/automation/test_setup_command.py` **(new)**

### Expected no behavioral changes required in callers

- `moltbook/services/llm_execution_service.py`

This should continue working if `OpenAILLMClient` public methods and reason codes are preserved.

---

## 5) Dependency & Packaging Changes

## 5.1 Add official OpenAI SDK

Update `pyproject.toml` dependencies to include:

- `openai` — latest stable release compatible with the project Python baseline

Recommended pin format: `"openai>=1.40.0"` (or newer floor validated during implementation).

The SDK requires **Python 3.9+**. Project baseline is `>=3.14.3`, which is fine.

## 5.2 Do NOT add `openai_structured`

The third-party `openai_structured` package is not needed. The official SDK already supports structured outputs through `responses.create()` with strict `text.format.json_schema`.

## 5.3 Keep `httpx`

Do **not** remove `httpx` from project dependencies right now because Moltbook REST API client (`moltbook/api/client.py`) still uses it.

## 5.4 Add pytest for new unit tests

This plan adds new test files, so ensure `pytest` exists in development dependencies.

Update `[dependency-groups].dev` to include:

- `pytest` (latest stable)

## 5.5 Lockfile update

After implementation, regenerate lock metadata so environments resolve deterministically.

---

## 6) Detailed Refactor Plan: `openai_llm_client.py`

## 6.1 Imports and constants

- Remove direct `httpx` import from this file.
- Add OpenAI SDK imports:
  - `from openai import OpenAI`
  - SDK exception classes: `AuthenticationError`, `APITimeoutError`, `APIConnectionError`, `RateLimitError`, `APIStatusError`, `OpenAIError`
- Keep `json`, `logging`, `dataclass`, `ValidationError`, models, and `LLMClientError`.

Keep:

- `DEFAULT_TIMEOUT_SECONDS`
- `StructuredCompletionResult`

Remove:

- `OPENAI_RESPONSES_URL`
- `MAX_TRANSPORT_ATTEMPTS`
- Any helper methods only needed by raw HTTP transport.

## 6.2 Keep public methods stable

No signature changes for:

- `analyze_relevance(...)`
- `analyze_relevance_with_trace(...)`
- `generate_action(...)`
- `generate_action_with_trace(...)`

This avoids ripple effects in `LLMExecutionService`.

## 6.3 Simplify `_request_structured_completion`

Refactor `_request_structured_completion` to:

1. Create the SDK client via `_create_openai_client(api_key)`.
2. Build strict JSON schema text format from `response_model.model_json_schema()`.
3. Call `client.responses.create(...)` with:
   - `model=model`
   - `instructions=system_prompt`
   - `input=user_prompt` (single string)
   - `text={"format": {"type": "json_schema", "name": ..., "strict": True, "schema": ...}}`
   - `max_output_tokens=max_output_tokens`
   - `store=False`
4. Check `response.status` for failed/incomplete first (see below).
5. Detect refusal by iterating `response.output` for message content items of type `refusal`.
6. Read `response.output_text` — raw response text for trace logging.
7. Run local Pydantic validation via `_parse_json_content(response.output_text, response_model)` to enforce alias/normalization behavior.
8. Return `StructuredCompletionResult(parsed_output=..., raw_response=response.output_text)`.

### Design decision: remove model-based repair pass

Delete the current repair-request fallback. On invalid JSON or schema mismatch, raise:

- `LLMClientError(..., reason_code="provider-invalid-json")`

This reduces hidden second calls and simplifies observability/cost expectations. With strict `text.format.json_schema` enforcement, invalid JSON should be extremely rare.

### Handling refusals

When the model refuses a request for safety reasons, the Responses API returns a content item with `"type": "refusal"` instead of `"type": "output_text"`. The raw wire shape looks like:

```json
{
  "output": [{
    "type": "message",
    "role": "assistant",
    "content": [
      {
        "type": "refusal",
        "refusal": "I'm sorry, I cannot assist with that request."
      }
    ]
  }]
}
```

**Important:** The `output` array can contain reasoning items, tool calls, and messages. Never assume `output[0]` is the message — with reasoning models (GPT-5, o-series), `output[0]` is typically a `reasoning` item.

Refusal detection strategy:

1. Iterate `response.output` to find items with `type == "message"`.
2. For each message item, inspect its `content` list and detect `{"type": "refusal", ...}`.
3. If refusal content exists, raise `provider-refusal`.

On detection, raise:

- `LLMClientError(..., reason_code="provider-refusal")`

### Handling incomplete responses

When the model's output is truncated, the Responses API returns `response.status == "incomplete"` with a reason in `response.incomplete_details.reason`. Known reasons:

- `"max_output_tokens"` — output hit the `max_output_tokens` limit
- `"content_filter"` — output was filtered for safety

In either case, output should be treated as incomplete and must be rejected before refusal/content parsing:

```python
if response.status == "incomplete":
    reason = getattr(response.incomplete_details, "reason", "unknown")
    raise LLMClientError(
        f"OpenAI response was incomplete (reason: {reason}).",
        reason_code="provider-incomplete-response",
    )
```

`provider-incomplete-response` is a **new** reason code. Callers that do not explicitly handle it will fall through to generic error handling.

### Handling failed responses

The Responses API can also return `response.status == "failed"` with error details in `response.error` (containing `code` and `message` fields). Known error codes include `server_error`, `rate_limit_exceeded`, `invalid_prompt`, and various image-related errors.

The implementation should check for `"failed"` status before checking for incomplete/refusal:

```python
if response.status == "failed":
    error_code = getattr(response.error, "code", "unknown")
    error_msg = getattr(response.error, "message", "")
    raise LLMClientError(
        f"OpenAI response failed (code: {error_code}): {error_msg}",
        reason_code="provider-request-failed",
    )
```

**Note:** The full set of possible `response.status` values is: `"queued"`, `"in_progress"`, `"completed"`, `"failed"`, `"cancelled"`, `"incomplete"`. For synchronous non-streaming calls, only `"completed"`, `"failed"`, and `"incomplete"` are expected in the returned response.

## 6.4 Add small internal helper (recommended)

Add `_create_openai_client(api_key: str) -> OpenAI` helper to centralize:

- API key injection
- timeout configuration
- retry behavior: **set `max_retries=1`**

The SDK default is `max_retries=2` (3 total attempts). The current manual implementation uses `MAX_TRANSPORT_ATTEMPTS = 2` (2 total attempts: 1 original + 1 retry). To preserve equivalent behavior, explicitly set `max_retries=1` (2 total attempts). The SDK automatically retries on connection errors, 408, 409, 429, and ≥500 status codes with short exponential backoff.

## 6.5 Remove obsolete helpers

Delete:

- `_send_completion_request(...)`
- `_extract_response_content(...)`

Keep:

- `_parse_json_content(...)` (for local alias/normalization validation pass)

## 6.6 Error mapping contract (must remain stable)

Map SDK exceptions to existing reason codes so automation runtime behavior remains unchanged:

1. Authentication failure
   - Exception: `openai.AuthenticationError`
   - Reason code: `openai-auth-failed`
2. Timeout
   - Exception: `openai.APITimeoutError`
   - Reason code: `provider-timeout`
3. Network / connection
   - Exception: `openai.APIConnectionError`
   - Reason code: `provider-network`
4. Rate limit
   - Exception: `openai.RateLimitError`
   - Reason code: `provider-rate-limited`
5. 5xx provider errors
   - Exception: `openai.APIStatusError` with `status_code >= 500`
   - Reason code: `provider-server-error`
6. Other non-success provider status
   - Exception: `openai.APIStatusError` (non-5xx)
   - Reason code: `provider-http-error`
7. Empty output text
    - Condition: `response.output_text` missing/blank
    - Reason code: `provider-empty-response`
8. Failed response
    - Condition: `response.status == "failed"` (covers `server_error`, `rate_limit_exceeded`, `invalid_prompt`, and other API-level failures)
    - Reason code: `provider-request-failed`
9. Incomplete response (output truncated or filtered)
    - Condition: `response.status == "incomplete"` (covers `max_output_tokens`, `content_filter`, and any future reasons)
    - Reason code: `provider-incomplete-response` **(new)**
10. Model refusal
    - Iterate `response.output` for `type == "message"` items and check each message `content` entry for `type == "refusal"`
    - Reason code: `provider-refusal` **(new)**
11. Invalid JSON / model validation failure
     - Exception: `json.JSONDecodeError` or `ValidationError`
     - Reason code: `provider-invalid-json`
12. Unknown provider failure fallback
     - Exception: `openai.OpenAIError` or generic base error
     - Reason code: `provider-request-failed`

Message text can be modernized, but reason codes must stay stable. `provider-refusal` and `provider-incomplete-response` are **new** reason codes that callers should handle gracefully (treat as non-actionable content / retriable conditions respectively).

**Check order:** The implementation must check response status in the following order: (1) `"failed"`, (2) `"incomplete"`, (3) refusal, (4) empty output, (5) parse/validate. This ensures status-level conditions are caught before content-level inspection.

## 6.7 Logging expectations

- Keep warning logs for invalid JSON validation failures.
- Do not log API key.
- Keep messages actionable and concise for CLI logs.
- **Log request IDs**: Log `response._request_id` on successful responses (in trace output) and `exc.request_id` on SDK exception catches. Request IDs are essential for debugging API issues with OpenAI support.
- **Update `_build_stage_prompt_payload` in `automation_service.py`**: The current log payload serialization at line 764 uses `"role": "system"`. Since the refactor switches to `instructions=system_prompt`, the log payload format should be updated to reflect the actual call shape (i.e., log `instructions` + `input` separately, not as a fake messages array).

---

## 7) Structured Output Contract

## 7.1 Schema generation

The implementation generates JSON schema via `response_model.model_json_schema()` and sends it through `text.format`:

```json
"text": {
  "format": {
    "type": "json_schema",
    "name": "<schema_name>",
    "strict": true,
    "schema": { ... derived from model.model_json_schema() ... }
  }
}
```

Our request builder must ensure the schema shape complies with strict-mode requirements:
- Root schema is an object (not root `anyOf`)
- `additionalProperties: false` where required
- Required fields are explicit

`AnalysisDecision` and `ActionPlan` are already close to this shape; verify final payload before merge.

### Pydantic constraint compatibility with strict mode

**Pre-merge verification (required):**

OpenAI's strict JSON schema mode documents exactly which JSON Schema keywords are supported per type. For strings, only `pattern` and `format` are listed as supported properties in the constraint table. `minLength` and `maxLength` are **not in the supported properties list** per the [Structured Outputs supported schemas documentation](https://developers.openai.com/api/docs/guides/structured-outputs/#supported-schemas). However, the contradiction exists at multiple levels:

1. The official documentation's own code example uses `"minLength": 1` in a strict-mode schema.
2. Our own `openai-api` skill's `structured-outputs.md` reference file uses `"minLength": 1` in its raw JSON schema example (Basic Usage section).
3. Number constraints (`minimum`, `maximum`) and array constraints (`minItems`, `maxItems`) are documented as supported, but the equivalent string constraints are not listed.

This ambiguity means empirical verification is required — do not assume rejection or acceptance.

Our models use `min_length` and `max_length` on the following fields:

| Model | Field | Constraint |
|---|---|---|
| `AnalysisDecision` | `relevance_rationale` | `min_length=1, max_length=120` |
| `ActionPlan` | `reply_content` | `max_length=4000` |
| `ActionPlan` | `reason` | `min_length=1, max_length=500` |

Depending on SDK/runtime behavior, these keywords may pass through as-is. If the API rejects them, sanitize only the outbound schema payload while retaining local Pydantic validation constraints.

**Verification steps (§13 step 1):**

1. Install the `openai` SDK.
2. Run `AnalysisDecision.model_json_schema()` and `ActionPlan.model_json_schema()` in a Python REPL to inspect the raw Pydantic-generated schemas and confirm `minLength`/`maxLength` are present.
3. Create a throwaway script that calls `client.responses.create(...)` with these schemas against the API and inspect whether the call succeeds or returns a schema validation error.
4. If the SDK does **not** strip `minLength`/`maxLength` and the API rejects them, implement a `_strip_unsupported_constraints(schema: dict) -> dict` helper that recursively removes `minLength` and `maxLength` from all string property definitions in the generated schema before sending it to the API.
5. Regardless of outcome, retain these constraints in the local Pydantic validation pass (`_parse_json_content`) which always runs after the SDK response.

### `AliasChoices` behavior

`AnalysisDecision.relevance_rationale` uses `validation_alias=AliasChoices("relevance_rationale", "reason")`. This is a **validation-time** feature and does not affect the generated JSON schema. The generated schema will use the Python field name (`relevance_rationale`), while the `reason` alias remains useful in local validation for backward compatibility.

### `Optional` fields (`str | None`)

`ActionPlan.reply_content` is typed as `str | None`. In strict mode, this is correctly represented as `"type": ["string", "null"]` in the generated JSON schema, and the field is still included in `required`. This is the documented pattern for optional values in strict mode. **Verify** during implementation that `model_json_schema()` for `ActionPlan` produces this expected shape.

## 7.2 Validation layering

Even though the SDK validates against the JSON schema, keep **local Pydantic validation** for:

- Normalized text trimming behavior (`field_validator` with `mode="before"`)
- Alias behavior (`relevance_rationale` / `reason`)
- `min_length`/`max_length` enforcement (may not be enforced by the API)
- Deterministic local validation errors
- Consistency with current error/reason-code contract

The implementation should use `response.output_text` → `_parse_json_content()` as the authoritative parse.

## 7.3 Raw response preservation

Continue persisting returned response text in `StructuredCompletionResult.raw_response` because automation stage logs currently depend on this. Use `response.output_text` for this value.

---

## 8) Documentation Updates

## 8.1 `docs/AUTOMATION.md`

The current `docs/AUTOMATION.md` §9.3 contains several pre-existing inaccuracies that do not match the current code:

- States `response_format: {"type": "json_object"}` — actual code uses `text.format.json_schema` (Responses API structured output format).
- Mentions "stage temperatures (analysis low, action moderate)" — no temperature parameter exists in the current `openai_llm_client.py`.
- Mentions "pre-parsing defensive markdown fence stripping" — no such logic exists in the current code.

Update the entire §9.3 section to accurately describe the new architecture:

- Replace all manual endpoint/httpx references with official SDK usage.
- Replace manual `_extract_response_content` narrative with `response.output_text` plus defensive `response.output` inspection for refusal handling.
- Remove mention of repair retry (now removed).
- Remove the three inaccurate claims listed above.
- Document the structured output shape: `text.format.json_schema` with `strict: true`.
- Document the `responses.create()` pattern used in runtime.
- Document use of `instructions=system_prompt` instead of inline system/developer role messages.
- Document `store=False` for one-shot automation calls.
- Document dynamic model listing behavior (see §15).
- Note that the current code was also missing `"strict": true` in its format payload — this is fixed by the SDK refactor.

## 8.2 `README.md`

Clarify tech stack distinction:

- `httpx` remains for Moltbook REST API client
- `openai` SDK is used for automation LLM Responses API calls
- Structured outputs use strict `text.format.json_schema` plus local Pydantic validation

---

## 9) Test Plan (required for implementation phase)

Create/adjust unit tests to cover:

1. **Successful analysis parse**
   - Mock `responses.create` returning valid `output_text`
   - Assert `AnalysisDecision` parsed correctly
2. **Successful action parse**
   - Assert `ActionPlan` parse path
3. **Empty output mapping**
   - Blank `output_text` → `provider-empty-response`
4. **Invalid JSON mapping**
   - Malformed JSON → `provider-invalid-json`
5. **Validation failure mapping**
   - Well-formed JSON but schema mismatch → `provider-invalid-json`
6. **Refusal mapping**
   - Response output contains message item with refusal content type → `provider-refusal`
7. **Incomplete response mapping**
   - `response.status == "incomplete"` with `incomplete_details.reason == "max_output_tokens"` → `provider-incomplete-response`
   - `response.status == "incomplete"` with `incomplete_details.reason == "content_filter"` → `provider-incomplete-response`
8. **Auth mapping**
   - `openai.AuthenticationError` → `openai-auth-failed`
9. **Timeout mapping**
   - `openai.APITimeoutError` → `provider-timeout`
10. **Connection mapping**
    - `openai.APIConnectionError` → `provider-network`
11. **Rate-limit mapping**
    - `openai.RateLimitError` → `provider-rate-limited`
12. **Status error mapping**
    - 5xx → `provider-server-error`
    - non-5xx status → `provider-http-error`
13. **Generic fallback mapping**
    - Unexpected `openai.OpenAIError` → `provider-request-failed`
14. **No hidden second call**
    - Assert one `responses.create` call for invalid JSON path (repair flow removed)
15. **Dynamic model listing**
    - Mock `client.models.list()` and verify Responses API–compatible filtering
16. **Model catalog fallback**
    - Simulate `client.models.list()` failure and verify fallback to `moltbook/data/models.json`
17. **Setup UI stage selectors**
    - Verify both provider and model selection are rendered/handled via Rich radio-style choices per stage

Use mocking; no live network tests.

---

## 10) Backward-Compatibility Requirements

1. `OpenAILLMClient` public methods remain unchanged.
2. `StructuredCompletionResult` shape remains unchanged.
3. All `reason_code` values currently consumed by runtime remain available.
4. `provider-refusal` and `provider-incomplete-response` are **new** reason codes; callers that do not handle them will fall through to generic error handling.
5. No changes required to:
   - provider config schema in `client.json`
   - stage routing in `agent.json`
6. **Setup command UX changes**: provider and model selection for each stage both use Rich radio-style selection (see §15). Model choices are fetched dynamically when possible.
7. **`BaseLLMClient` protocol deviation (pre-existing)**: The `BaseLLMClient` protocol in `base_llm_client.py` does not include `max_output_tokens` in its method signatures, but `OpenAILLMClient` requires it. This is a pre-existing mismatch not introduced by this refactor. A follow-up task may reconcile the protocol.

---

## 11) Risks & Mitigations

1. **SDK parameter-shape drift**
   - Mitigation: pin SDK version floor and align implementation/tests to the selected `responses.create()` request/response shape.
2. **Behavioral change from removing repair pass**
   - Mitigation: strict `text.format.json_schema` is enforced at the API level; invalid JSON should be extremely rare. Retain clear `provider-invalid-json` reason; monitor logs.
3. **Error-class mismatch across SDK versions**
   - Mitigation: map using official exception hierarchy for minimum pinned version; include generic fallback.
4. **Loss of raw response detail**
   - Mitigation: always store `response.output_text` into `raw_response`.
5. **Dynamic model listing depends on API availability**
   - Mitigation: cache model list during setup session. If the API call fails, fall back to provider entries from `moltbook/data/models.json` (see §15.6).
6. **Refusal and incomplete-response handling is new**
   - Mitigation: new `provider-refusal` and `provider-incomplete-response` reason codes with clear semantics; callers that don't explicitly handle them will treat them as generic failures.
7. **Pydantic `min_length`/`max_length` constraints are NOT in OpenAI's supported string properties for strict mode**
   - Only `pattern` and `format` are documented as supported string constraints. Our models use `min_length`/`max_length` on `relevance_rationale`, `reason`, and `reply_content`. If the SDK passes these through and the API rejects them, the entire refactor is blocked until a schema-stripping helper is implemented.
   - Mitigation: this is a **blocking pre-check** (§13 step 1). Verify before writing any other refactored code. If needed, implement `_strip_unsupported_constraints()` to remove `minLength`/`maxLength` from generated schemas. Local Pydantic validation always enforces these constraints regardless.
8. **Incomplete responses from `max_output_tokens` truncation or `content_filter`**
   - Mitigation: detect `response.status == "incomplete"` before parsing and raise a distinct `provider-incomplete-response` error with the specific reason included in the message. This gives callers a clear signal regardless of the incomplete cause.
9. **Existing code is missing `"strict": true` in format payload**
    - The current `_send_completion_request` (lines 214-220) builds the `text.format` dict without `"strict": true`. This means the current implementation is not actually using strict schema enforcement. The SDK refactor fixes this by explicitly setting `"strict": true` in the `responses.create()` payload.
    - Mitigation: this is a pre-existing bug fixed by this refactor. No separate remediation needed.
10. **models.json registry can become stale**
    - Mitigation: maintain `moltbook/data/models.json` as a reviewed compatibility registry and prefer live `models.list()` results whenever available.

---

## 12) Acceptance Criteria

Implementation is complete when all are true:

1. `openai_llm_client.py` no longer performs manual HTTP POST transport.
2. Official OpenAI SDK `responses.create()` is used for Responses API requests with strict `text.format.json_schema`.
3. SDK calls use `instructions=system_prompt` instead of inline system/developer role messages.
4. SDK calls use `store=False` for one-shot automation calls.
5. Manual response tree extraction helper is removed.
6. Manual repair-retry JSON rewrite flow is removed.
7. Existing runtime reason-code semantics are preserved; new `provider-refusal` and `provider-incomplete-response` codes added.
8. Refusal detection iterates `response.output` message content and never relies on fragile `output[0].content[0]` indexing.
9. Incomplete response detection covers both `max_output_tokens` and `content_filter` reasons.
10. Request IDs are logged on success (`response._request_id`) and failure (`exc.request_id`).
11. `automation_service.py` `_build_stage_prompt_payload` updated to reflect actual call shape.
12. Stage logs still contain prompt payload and raw response payload text.
13. Unit tests cover success + exception + refusal + incomplete-response mapping paths listed above.
14. Docs (`README.md`, `docs/AUTOMATION.md`) accurately describe the new architecture.
15. `automation setup` presents provider selection via Rich radio-style UI for each stage.
16. `automation setup` presents model selection via Rich radio-style UI for each stage.
17. `automation setup` fetches available Responses API–compatible models dynamically from the OpenAI API via `openai` SDK when possible.
18. If dynamic model fetch is unavailable, setup falls back to `moltbook/data/models.json`.
19. `pyproject.toml` includes `openai` and does **not** include `openai_structured`.
20. Pydantic model strict-schema compatibility is verified (wire payload inspected for unsupported `minLength`/`maxLength` keywords).

---

## 13) Suggested Implementation Sequence (for execution phase)

1. Verify Pydantic strict-schema compatibility (§7.1) and define schema-sanitizing fallback only if required.
2. Add `openai` + `pytest` dependencies in `pyproject.toml` and refresh `uv.lock`.
3. Refactor `openai_llm_client.py` to use `responses.create()` with strict `text.format.json_schema`, preserving public methods and reason-code mapping.
4. Update `automation_service.py` stage prompt log payload shape to `instructions` + `input`.
5. Add `moltbook/data/models.json` as compatibility registry/fallback source.
6. Update `llm_provider_service.py` for dynamic model fetch (`client.models.list()`), compatibility filtering, caching, and `models.json` fallback.
7. Update `setup_command.py` so both provider and model are selected via Rich radio-style UI per stage, with API-key-before-model ordering.
8. Add tests for client mapping, provider model retrieval/fallback, and setup-stage selection UX paths.
9. Update docs (`AUTOMATION.md` §9.3, `README.md`).
10. Run lint/format/tests.
11. Manual smoke: run one dry automation cycle with valid credentials and verify both filter-stage and action-stage logs.

---

## 14) Explicit Non-Goals

1. No provider expansion beyond OpenAI (but provider selection is now radio-style, making future expansion clean).
2. No migration of `moltbook/api/client.py` away from `httpx`.
3. No scheduler or queue semantics changes.
4. No support for models that do not work with the Responses API.
5. No addition of `openai_structured` or similar third-party schema-enforcement packages.
6. No simplification of system prompts in `automation_service.py`. The current `ANALYSIS_SYSTEM_PROMPT` and `ACTION_SYSTEM_PROMPT` include explicit JSON-formatting instructions ("Return ONLY valid minified JSON", "Do NOT use markdown fences") that become redundant when strict `text.format.json_schema` is enforced. However, removing or simplifying these prompts is a separate behavioral change that should be evaluated independently after the SDK refactor is stable.

---

## 15) Setup Flow Changes: Provider Selection & Dynamic Model Listing

### 15.1 Provider selection — Rich radio-style UI (per stage)

**Current behavior**: `_prompt_stage_llm_config` in `setup_command.py` uses `click.prompt` with `click.Choice` to ask the user to type a provider name (currently just "openai").

**New behavior**: Replace with a Rich-rendered radio-style selection UI. The user should see a list of available providers with radio indicators and select one for each stage. Currently, only `OpenAI` is listed.

Implementation approach:
- Use `rich.prompt.Prompt` or a custom Rich panel with numbered choices rendered via `rich.console.Console`.
- Since Rich does not have a built-in radio widget, implement a simple numbered-choice renderer:
  ```
  LLM Provider:
    [1] OpenAI  ← (default)
  ```
  The user enters the number or presses Enter for the default.
- This is applied for both stages independently, so analysis/filter and action/acting can diverge in future without redesign.

### 15.2 Model selection — Rich radio-style UI (per stage)

**Current behavior**: `_prompt_stage_llm_config` uses `click.prompt(... click.Choice(...))` for model selection.

**New behavior**: model selection must also use Rich radio-style selection, not Click choice prompts.

Implementation approach:
- Reuse the same internal Rich radio helper used for provider selection.
- For each stage:
  1. Render model options as numbered radio entries.
  2. Default to existing stage model if still available.
  3. Accept numeric choice or Enter for default.

### 15.3 Dynamic model listing via OpenAI Models API

**Current behavior**: `llm_provider_service.py` hardcodes `OPENAI_MODELS` as a static tuple.

**New behavior**: During `automation setup`, fetch the list of available models from the OpenAI API and filter to only those compatible with the Responses API.

Implementation:

1. Add a method `LLMProviderService.fetch_available_models(api_key: str) -> list[str]` that:
   - Creates a temporary `OpenAI(api_key=api_key)` client.
   - Calls `client.models.list()` to fetch all models accessible to the user's API key.
   - Filters the returned models to only those known to support the Responses API + structured outputs, using compatibility rules from `moltbook/data/models.json`.
   - Returns a sorted list of model ID strings.

2. The `_collect_llm_configuration` / `_prompt_stage_llm_config` flow in `setup_command.py` should:
   - First prompt for the provider (Rich radio-style, §15.1).
   - Then prompt for the API key (if not yet provided).
   - Then call `fetch_available_models(api_key)` to get the dynamic list.
   - Present the model list to the user via Rich radio-style UI (§15.2).

### 15.4 Compatibility registry and filtering source

Create `moltbook/data/models.json` as the source-of-truth compatibility registry used by setup and provider service.

Example shape:

```json
{
  "openai": {
    "responses_api": {
      "allow_prefixes": [
        "gpt-5",
        "gpt-5.1",
        "gpt-5.2",
        "gpt-4o",
        "gpt-4.1",
        "o4",
        "o3",
        "o1"
      ],
      "fallback_models": [
        "gpt-5",
        "gpt-5-mini",
        "gpt-4o-mini",
        "gpt-4.1-mini",
        "o4-mini"
      ]
    }
  }
}
```

Filtering rule:
- Keep only fetched model IDs whose ID starts with one of the configured `allow_prefixes`.
- Remove duplicates and sort.

### 15.5 Re-ordering: API key before model selection

The current interactive setup flow collects provider + model **before** prompting for the API key. This must be re-ordered so that:

1. Provider is selected (Rich radio-style).
2. API key is collected (needed to call the Models API).
3. Models are fetched dynamically.
4. Model is selected per stage.

This means `_collect_llm_configuration` must be restructured to interleave provider config collection with model selection.

### 15.6 Fallback for API unavailability

If `client.models.list()` fails (network error, invalid key, etc.):
- Log a warning.
- Fall back to `fallback_models` loaded from `moltbook/data/models.json`.
- Inform the user that the model list could not be fetched and they are seeing cached defaults.

If API fetch succeeds but filtering yields no compatible models:
- Fall back to `fallback_models` from `models.json`.
- Display a warning panel explaining why fallback was used.

### 15.7 Files affected

- `moltbook/services/llm_provider_service.py` — add `fetch_available_models()`, filter logic, fallback constants.
- `moltbook/commands/automation/setup_command.py` — Rich radio-style provider + model selection, re-ordered flow, dynamic model list integration.
- `moltbook/data/models.json` — responses-compatibility allowlist + fallback models.
- `moltbook/models/llm_provider.py` — no schema changes needed.

---

## 16) Python Version & SDK Compatibility Summary

| Component | Version |
|---|---|
| Python | `>=3.14.3` (project baseline, unchanged) |
| `openai` SDK | `>=1.40.0` (or newer validated floor; used via `responses.create` + structured outputs) |
| `openai_structured` | **not used** |
| `httpx` | retained for Moltbook REST API client |
| `pydantic` | `>=2.11.1` (unchanged, used by both app models and SDK structured output) |

---

## 17) References

1. [Introducing Structured Outputs in the API — OpenAI](https://openai.com/index/introducing-structured-outputs-in-the-api/)
2. [openai-python — GitHub](https://github.com/openai/openai-python)
3. [Structured model outputs guide — OpenAI API Docs](https://developers.openai.com/api/docs/guides/structured-outputs/)
4. [Responses API structured output discussion — OpenAI Developer Community](https://community.openai.com/t/responses-api-documentation-on-structured-outputs-is-lacking/1356632)
