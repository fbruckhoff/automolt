# Responses API Reference

The Responses API is the primary interface for generating text with OpenAI models.

## Endpoint

```
POST https://api.openai.com/v1/responses
```

**Authentication:**
```
Authorization: Bearer $OPENAI_API_KEY
```

## Quick Start

```python
from openai import OpenAI
client = OpenAI()

response = client.responses.create(
    model="gpt-5",
    instructions="You are a helpful assistant.",
    input="Hello!"
)
print(response.output_text)
```

**curl with structured output:**
```bash
curl https://api.openai.com/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
    "model": "o4-mini",
    "input": "Classify the sentiment.\n\nTEXT: I love building with this API!",
    "text": {
      "format": {
        "name": "relevance_classifier",
        "type": "json_schema",
        "schema": {
          "type": "object",
          "properties": {
            "is_relevant": { "type": "boolean" },
            "relevance_rationale": { "type": "string" }
          },
          "required": ["is_relevant", "relevance_rationale"],
          "additionalProperties": false
        }
      }
    }
  }'
```

## Request Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `model` | string | Yes | Model ID (e.g. `gpt-5`, `gpt-5.2`, `gpt-5-mini`) |
| `input` | string or array | Yes | A string prompt, or an array of message objects |
| `instructions` | string | No | System-level instructions (takes priority over `input` messages) |
| `store` | boolean | No | Whether to store the response for multi-turn use. Default: `true` |
| `previous_response_id` | string | No | Chain to a previous response for multi-turn conversations |
| `text` | object | No | Text output configuration (format, verbosity) |
| `reasoning` | object | No | Reasoning configuration (effort level) |
| `tools` | array | No | Tools the model can use |
| `tool_choice` | object | No | Control which tools the model may use |
| `prompt` | object | No | Reference a reusable prompt by `id`, `version`, and `variables` |
| `background` | boolean | No | Whether to run the model response in the background |
| `context_management` | array | No | Context management config. Each entry: `{type: "compaction", compact_threshold: <number>}`. Threshold sets token count at which compaction triggers. |
| `conversation` | string or object | No | Conversation ID (string) or `{id: "<conv_id>"}`. Associates the response with a conversation; prior items are prepended to input, and output items are appended after completion. |
| `include` | array | No | Additional fields to include in the response (see values below) |
| `max_output_tokens` | number | No | Upper bound on generated tokens (includes visible output and reasoning tokens) |
| `max_tool_calls` | number | No | Max total built-in tool calls per response (applies across all tools) |
| `metadata` | object | No | Up to 16 key-value pairs (key max 64 chars, value max 512 chars). Useful for structured storage and querying. |
| `parallel_tool_calls` | boolean | No | Whether to allow the model to run tool calls in parallel |
| `prompt_cache_key` | string | No | Cache key for similar requests. Replaces the `user` field for caching. |
| `prompt_cache_retention` | string | No | Cache retention policy: `"in-memory"` (default) or `"24h"` (extended) |
| `safety_identifier` | string | No | Stable hashed user ID (max 64 chars) for policy violation detection |
| `service_tier` | string | No | Processing tier: `"auto"` (default), `"default"`, `"flex"`, `"scale"`, `"priority"` |
| `stream` | boolean | No | If true, stream response via server-sent events |
| `stream_options` | object | No | `{include_obfuscation: bool}` — set false to disable payload-size normalization |
| `temperature` | number | No | Sampling temperature 0–2. Higher = more random. Don't combine with `top_p`. |
| `top_p` | number | No | Nucleus sampling. Considers tokens with top_p probability mass. Alternative to temperature. |
| `top_logprobs` | number | No | Number of most likely tokens (0–20) to return with their log probabilities |
| `truncation` | string | No | `"auto"` (default, truncates oldest input) or `"disabled"` (fails if context exceeded) |
| `user` | string | No | Unique end-user identifier for abuse monitoring |

### `include` Values

| Value | Description |
|---|---|
| `reasoning.encrypted_content` | Encrypted reasoning tokens for stateless multi-turn (ZDR) |
| `file_search_call.results` | File search tool call results |
| `web_search_call.results` | Web search tool call results |
| `web_search_call.action.sources` | Sources from web search tool calls |
| `message.input_image.image_url` | Image URLs from input messages |
| `message.output_text.logprobs` | Logprobs with assistant messages |
| `computer_call_output.output.image_url` | Image URLs from computer call output |
| `code_interpreter_call.outputs` | Outputs of code interpreter tool calls |

### Input Formats

**Simple string:**
```json
{
  "model": "gpt-5",
  "input": "What is the capital of France?"
}
```

**Separate instructions and input:**
```python
response = client.responses.create(
    model="gpt-5",
    instructions="You are a helpful assistant.",
    input="Hello!"
)
print(response.output_text)
```

**Message array:**
```python
response = client.responses.create(
    model="gpt-5",
    input=[
        {"role": "developer", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ]
)
```

The `instructions` parameter is equivalent to placing a `developer` role message at the start of the `input` array, but with cleaner semantics. Note that `instructions` only applies to the current request — it does not persist across chained responses via `previous_response_id`.

### Input Item Types

When `input` is an array, each item can be one of:

| Type | `type` value | Description |
|---|---|---|
| Easy Message | `"message"` (optional) | `{role, content}` — content is string or array of content parts |
| Message | `"message"` | Formal message with `role`, `content` (array of content parts), `status` |
| Output Message | `"message"` | Model output message re-sent as input for multi-turn (role is `"assistant"`) |
| File Search Call | `"file_search_call"` | Previous file search tool call result |
| Computer Tool Call | `"computer_call"` | Previous computer use tool call |
| Computer Call Output | `"computer_call_output"` | Screenshot/output from computer use |
| Function Call Output | `"function_call_output"` | Result from a function call |
| Item Reference | `"item_reference"` | Reference to a previous item by `id` |
| Reasoning | `"reasoning"` | Reasoning item from previous turn |

**Message content parts** (in the `content` array):

| Type | `type` value | Fields |
|---|---|---|
| Text | `"input_text"` | `text` |
| Image | `"input_image"` | `image_url` or `file_id`, `detail` (`"low"`, `"high"`, `"auto"`) |
| File | `"input_file"` | `file_id`, `file_data`, `file_url`, `filename` |

**Message roles:** `"developer"` (highest priority), `"user"`, `"assistant"`, `"system"` (legacy, use `"developer"`)

### Output Content Types

Output messages have `content` arrays with:

| Type | `type` value | Key Fields |
|---|---|---|
| Text | `"output_text"` | `text`, `annotations[]` (file citations, URL citations, file paths), `logprobs` |
| Refusal | `"refusal"` | `refusal` (explanation string) |

**Annotation types:** `file_citation` (file_id, filename), `url_citation` (url, title, start/end index), `container_file_citation`, `file_path`

## Response Structure

The response object contains an `output` array with one or more items:

```json
{
  "id": "resp_...",
  "object": "response",
  "created_at": 1756315696,
  "model": "gpt-5-2025-08-07",
  "output": [
    {
      "id": "rs_...",
      "type": "reasoning",
      "content": [],
      "summary": []
    },
    {
      "id": "msg_...",
      "type": "message",
      "status": "completed",
      "content": [
        {
          "type": "output_text",
          "annotations": [],
          "text": "The capital of France is Paris."
        }
      ],
      "role": "assistant"
    }
  ]
}
```

### Output Item Types

| Type | Description |
|---|---|
| `message` | Text output from the model. Content array has items of type `output_text` |
| `reasoning` | Internal chain-of-thought reasoning (may be empty or encrypted) |
| `function_call` | A tool/function call the model wants to make |

> **Warning:** The `output` array often has more than one item. It can contain reasoning items, tool calls, and messages. Never assume `output[0].content[0].text` is the text output.

### The `output_text` Shortcut

SDKs provide an `output_text` property on the response object that aggregates all text outputs into a single string:

```python
response = client.responses.create(
    model="gpt-5",
    input="Say hello"
)
print(response.output_text)  # Aggregated text from all message items
```

## Statefulness

Responses are stored by default (`store: true`). This enables:
- Multi-turn conversations via `previous_response_id`
- Server-side context preservation across turns
- Better cache utilization (40–80% improvement over Chat Completions)

Set `store: false` to disable storage. For ZDR (Zero Data Retention) organizations, `store: false` is enforced automatically.

## Key Differences from Chat Completions

| Aspect | Chat Completions | Responses API |
|---|---|---|
| Endpoint | `/v1/chat/completions` | `/v1/responses` |
| Input parameter | `messages` | `input` (string or array) |
| System messages | `role: "system"` | `role: "developer"` or `instructions` param |
| Output structure | `choices[0].message.content` | `output` array with typed items |
| Text shortcut | None | `output_text` |
| State management | Manual (rebuild message array) | `previous_response_id` or manual |
| Structured outputs | `response_format` | `text.format` |
| Built-in tools | None | `web_search_preview`, `file_search`, etc. |

## Response Object Fields

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique response ID (`resp_...`) |
| `object` | string | Always `"response"` |
| `created_at` | number | Unix timestamp of creation |
| `completed_at` | number | Unix timestamp of completion |
| `model` | string | Actual model used (may be a snapshot) |
| `status` | string | `"queued"`, `"in_progress"`, `"completed"`, `"failed"`, `"cancelled"`, `"incomplete"` |
| `output` | array | Array of output items (messages, reasoning, tool calls) |
| `output_text` | string | Aggregated text from all message items (convenience shortcut) |
| `error` | object | Error details when `status` is `"failed"` |
| `incomplete_details` | object | Details when `status` is `"incomplete"` |
| `usage` | object | Token usage breakdown |
| `metadata` | object | Echoed metadata key-value pairs |
| `service_tier` | string | Actual tier used for processing |

### Error Codes (`error.code`)

| Code | Description |
|---|---|
| `server_error` | Internal server error |
| `rate_limit_exceeded` | Rate limit hit |
| `invalid_prompt` | Prompt was invalid or violated policy |
| `vector_store_timeout` | File search vector store timed out |
| `invalid_image` / `invalid_image_format` / `invalid_base64_image` / `invalid_image_url` | Image input issues |
| `image_too_large` / `image_too_small` / `image_parse_error` / `image_file_too_large` | Image size/parsing errors |
| `image_content_policy_violation` | Image violated content policy |
| `unsupported_image_media_type` / `empty_image_file` / `failed_to_download_image` / `image_file_not_found` | Image file issues |
| `invalid_image_mode` | Invalid image mode |

### Incomplete Reasons (`incomplete_details.reason`)

| Reason | Description |
|---|---|
| `max_output_tokens` | Hit the `max_output_tokens` limit |
| `content_filter` | Output was filtered for safety |

### Token Usage (`usage`)

| Field | Description |
|---|---|
| `input_tokens` | Tokens in the input |
| `input_tokens_details.cached_tokens` | Tokens served from cache |
| `output_tokens` | Tokens in the output |
| `output_tokens_details.reasoning_tokens` | Tokens used for reasoning |
| `total_tokens` | Total tokens (input + output) |

## Other Endpoints

### Retrieve a Response

```
GET /v1/responses/{response_id}
```

Query params: `include` (array of `ResponseIncludable`), `stream` (boolean — if true, streams the full response as SSE events)

Returns: the full `Response` object.

### Delete a Response

```
DELETE /v1/responses/{response_id}
```

Permanently deletes a stored response. Cannot be undone.

### Cancel a Response

```
POST /v1/responses/{response_id}/cancel
```

Cancels an in-progress response. Only applies to background responses (`background: true`).

Returns: the `Response` object with updated status.

### Compact a Response

```
POST /v1/responses/compact
```

Takes a long conversation and compresses it for continued use. Body params:

| Parameter | Type | Required | Description |
|---|---|---|---|
| `input` | array | Yes | Input items to compact |
| `model` | string | Yes | Model to use |
| `instructions` | string | No | System instructions |
| `background` | boolean | No | Run in background |

Returns: a `Response` object containing compacted conversation items.

### List Input Items

```
GET /v1/responses/{response_id}/input_items
```

Returns paginated list of input items for a response.

Query params: `before`, `after`, `limit` (default 20), `order` (`"asc"` or `"desc"`, default `"desc"`)

### Count Tokens

```
POST /v1/responses/count_tokens
```

Count tokens for a potential response request without generating output. Accepts the same body parameters as Create.

Returns: `{total_tokens, input_token_details: {cached_tokens, text_tokens, image_tokens, audio_tokens}}`

## Streaming Events

When `stream: true`, the API sends server-sent events. Event names follow the pattern `response.<category>.<action>`.

### Lifecycle Events

| Event | Description |
|---|---|
| `response.created` | Response object created |
| `response.queued` | Response queued for processing |
| `response.in_progress` | Response processing started |
| `response.completed` | Response finished successfully |
| `response.failed` | Response failed (check `error`) |
| `response.incomplete` | Response stopped early (check `incomplete_details`) |

### Content Events

| Event | Description |
|---|---|
| `response.output_item.added` | New output item (message, reasoning, tool call) |
| `response.output_item.done` | Output item complete |
| `response.content_part.added` | Content part added to output item |
| `response.content_part.done` | Content part complete |
| `response.output_text.delta` | Incremental text chunk |
| `response.output_text.done` | Text output complete |
| `response.refusal.delta` | Incremental refusal text |
| `response.refusal.done` | Refusal complete |

### Tool Call Events

| Event | Description |
|---|---|
| `response.function_call_arguments.delta` | Incremental function call arguments |
| `response.function_call_arguments.done` | Function call arguments complete |
| `response.file_search_call.in_progress` / `.searching` / `.completed` | File search lifecycle |
| `response.web_search_call.in_progress` / `.searching` / `.completed` | Web search lifecycle |
| `response.code_interpreter_call.in_progress` / `.interpreting` / `.completed` | Code interpreter lifecycle |
| `response.code_interpreter_call.code.delta` / `.done` | Code interpreter code streaming |
| `response.mcp_call.in_progress` / `.completed` / `.failed` | MCP tool lifecycle |
| `response.mcp_call_arguments.delta` / `.done` | MCP tool arguments streaming |
| `response.mcp_list_tools.in_progress` / `.completed` / `.failed` | MCP tool listing |
| `response.custom_tool_call_input.delta` / `.done` | Custom tool input streaming |
| `response.image_gen_call.in_progress` / `.generating` / `.partial_image` / `.completed` | Image generation |

### Reasoning Events

| Event | Description |
|---|---|
| `response.reasoning.delta` / `.done` | Reasoning text streaming |
| `response.reasoning_summary_part.added` / `.done` | Reasoning summary parts |
| `response.reasoning_summary_text.delta` / `.done` | Summary text streaming |

### Audio Events (if audio output enabled)

| Event | Description |
|---|---|
| `response.audio.delta` / `.done` | Audio chunk streaming |
| `response.audio.transcript.delta` / `.done` | Audio transcript streaming |

### Delta Event Structure

All delta events include `sequence_number` for ordering. Text deltas have a `delta` field (string). The full event structure is:

```json
{"type": "response.output_text.delta", "item_id": "msg_...", "output_index": 0, "content_index": 0, "delta": "Hello", "sequence_number": 42}
```
