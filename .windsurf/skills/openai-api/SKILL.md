---
name: openai-api
description: Work with OpenAI Responses API for text generation, structured outputs, and model configuration. Use when making OpenAI API calls, choosing models, formatting requests, or handling responses.
---

# OpenAI Responses API Guide

Use the OpenAI **Responses API** exclusively. Do NOT use Chat Completions.

## Responses API

Endpoint, authentication, request parameters (all body params), `include` values, input item types, output content types, response object fields, error codes, incomplete reasons, token usage, streaming events, and secondary endpoints (Retrieve, Delete, Cancel, Compact, List Input Items, Count Tokens).
Reference: references/responses-api.md

## Text Generation & Prompting

Message roles (`developer` > `user` > `assistant`), prompt engineering best practices, the `instructions` parameter, and reusable prompts.
Reference: references/text-generation.md

## Structured Outputs

Constrain model output to a JSON schema using `text.format`. Covers schema structure, supported types, constraints, refusals, and when to use function calling vs `text.format`.
Reference: references/structured-outputs.md

## Models & Configuration

GPT-5 family models (`gpt-5.2`, `gpt-5.2-pro`, `gpt-5.2-codex`, `gpt-5.1`, `gpt-5`, `gpt-5-mini`, `gpt-5-nano`, `gpt-5-pro`), complete model ID list with snapshots, o-series models, `reasoning.effort` levels with per-model defaults, `reasoning.summary` config, `text.verbosity` control, and snapshot pinning for production.
Reference: references/models.md

## Multi-Turn Conversations

Manage conversation state by appending `output` to `input`, or use `previous_response_id` with `store: true` for stateful chaining. Covers encrypted reasoning for ZDR workflows.
Reference: references/multi-turn.md

## Tools

Built-in tools (`web_search_preview`, `file_search`, `code_interpreter`, `computer_use`, `apply_patch`, `function_shell`, `image_generation`), web search configuration, custom tools with freeform inputs, CFG-constrained outputs, `tool_choice` types and variants, `allowed_tools` parameter, function calling, file search with filters and ranking, and MCP tool integration.
Reference: references/tools.md

## Safety & Security

Prompt injection mitigation, data leakage prevention, structured outputs for constraining data flow, guardrails, and eval-driven monitoring.
Reference: references/safety.md

## Key Rules

1. **Always use the Responses API** — endpoint is `/v1/responses`, method is `client.responses.create()`
2. **`output` is an array** — it can contain reasoning items, messages, and tool calls; never assume `output[0]` is the text
3. **Use `instructions` for system-level guidance** — it takes priority over `input` messages
4. **Use `developer` role** (not `system`) for developer messages in the `input` array
5. **Pin model snapshots in production** — e.g. `gpt-5-2025-08-07` instead of `gpt-5`
6. **Never put untrusted input in developer messages** — always use `user` role for untrusted content
