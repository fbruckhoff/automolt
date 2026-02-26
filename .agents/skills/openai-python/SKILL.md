---
name: openai-python
description: Use the OpenAI Python SDK with the Responses API for text generation, structured outputs, tools, model configuration, and reliable production behavior.
---

# OpenAI Python SDK Guide

Use the official `openai` Python package for OpenAI integrations.
Use the **Responses API** as the default and do **not** use Chat Completions unless explicitly required.

## Level 0: Setup and Authentication

Install the SDK, load credentials from environment variables, and initialize a client.
Reference: https://github.com/openai/openai-python#installation

## Level 1: First Response (Default Path)

Generate text with `client.responses.create()` using `model`, `instructions`, and `input`.
Prefer `response.output_text` for quick text extraction.
Reference: https://github.com/openai/openai-python#usage

## Level 2: Prompting and Message Roles

Use `instructions` for system-level behavior and `input` for user/task content.
When using message arrays, use `developer` and `user` roles correctly; never put untrusted content in `developer` messages.
Reference: https://platform.openai.com/docs/guides/text

## Level 3: Structured Outputs

Constrain outputs with a JSON schema via `text.format` when deterministic machine-readable output is required.
Handle refusals and schema validation outcomes explicitly.
Reference: https://platform.openai.com/docs/guides/structured-outputs

## Level 4: Model and Reasoning Configuration

Choose the correct model for capability/cost/latency and pin snapshot model IDs in production.
Configure reasoning and output controls (`reasoning.effort`, `reasoning.summary`, `text.verbosity`) when needed.
Reference: https://platform.openai.com/docs/models

## Level 5: Multi-Turn Conversation State

Use one of two patterns:
1. Stateless chaining: append prior `response.output` items to the next `input`.
2. Stateful chaining: use `previous_response_id` with `store=True`.
Reference: https://platform.openai.com/docs/guides/conversation-state

## Level 6: Tools and Function Calling

Use built-in tools and custom function tools through the Responses API.
Control tool behavior with `tool_choice` and limit exposure with `allowed_tools`.
Reference: https://platform.openai.com/docs/guides/tools

## Level 7: Async, Streaming, and Realtime

Use `AsyncOpenAI` for async workflows.
Use `stream=True` with Responses for SSE streaming.
Use Realtime only when low-latency multimodal interaction is required.
Reference: https://github.com/openai/openai-python#async-usage

## Level 8: Reliability in Production

Handle SDK exceptions explicitly (`APIConnectionError`, `APIStatusError`, `RateLimitError`).
Log request IDs (`_request_id` on success, `exc.request_id` on failures).
Tune retries (`max_retries`) and timeouts (`timeout`) at client or per-request level.
Reference: https://github.com/openai/openai-python#handling-errors

## Level 9: Safety and Security

Never hardcode API keys; use environment variables and secret managers.
Treat all external/user content as untrusted input.
Use structured outputs and allowlists to reduce prompt-injection and data-exfiltration risk.
Reference: https://platform.openai.com/docs/guides/safety-best-practices

## SDK-Specific Notes

- Use `OpenAI()` for sync and `AsyncOpenAI()` for async; interfaces are otherwise equivalent.
- Request params are strongly typed (TypedDict-like), and responses are typed objects with helpers such as `to_dict()` and `to_json()`.
- Use `.with_options(...)` for per-request overrides (timeouts, retries, headers).
- For paginated endpoints, use the SDK iterator instead of writing manual pagination loops.
Reference: https://github.com/openai/openai-python

## Key Rules

1. **Use Responses API by default**: `client.responses.create(...)`.
2. **Do not assume `output[0]` is text**: `output` may include reasoning, tool calls, and messages.
3. **Use `instructions` for top-level behavior** and keep untrusted content in `user` input.
4. **Pin production model snapshots** (for example, `gpt-5-2025-08-07`) instead of floating aliases.
5. **Build for failure**: retries, timeouts, explicit exception handling, and request-id logging.
6. **Do not use Completions/Chat Completions APIs** in this skill unless a task explicitly requires them.
