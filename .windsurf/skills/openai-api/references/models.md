# Models & Configuration

## GPT-5 Model Family

| Model | Best For |
|---|---|
| `gpt-5.2` | Most complex tasks requiring broad world knowledge. Flagship model. |
| `gpt-5.2-pro` | Uses more compute for consistently better answers on hard problems |
| `gpt-5.2-codex` | Coding-optimized variant for agentic workflows |
| `gpt-5.1` | Previous-gen reasoning model |
| `gpt-5.1-codex` | Previous-gen coding variant |
| `gpt-5.1-codex-max` | Extended variant with `xhigh` reasoning support |
| `gpt-5.1-mini` | Previous-gen smaller model |
| `gpt-5` | Reasoning model, medium effort default |
| `gpt-5-mini` | Smaller, faster, cost-effective model |
| `gpt-5-nano` | Smallest model, lowest cost |
| `gpt-5-pro` | High-effort-only model for hardest problems |
| `gpt-5-codex` | Coding variant (Responses API only) |

### Complete Model ID List

**GPT-5.2:** `gpt-5.2`, `gpt-5.2-2025-12-11`, `gpt-5.2-chat-latest`, `gpt-5.2-pro`, `gpt-5.2-pro-2025-12-11`

**GPT-5.1:** `gpt-5.1`, `gpt-5.1-2025-11-13`, `gpt-5.1-codex`, `gpt-5.1-codex-max`, `gpt-5.1-mini`, `gpt-5.1-chat-latest`

**GPT-5:** `gpt-5`, `gpt-5-2025-08-07`, `gpt-5-mini`, `gpt-5-mini-2025-08-07`, `gpt-5-nano`, `gpt-5-nano-2025-08-07`, `gpt-5-chat-latest`, `gpt-5-pro`, `gpt-5-pro-2025-10-06`, `gpt-5-codex`

**o-series:** `o4-mini`, `o4-mini-2025-04-16`, `o3`, `o3-2025-04-16`, `o3-mini`, `o3-mini-2025-01-31`, `o3-pro`, `o3-pro-2025-06-10`, `o3-deep-research`, `o3-deep-research-2025-06-26`, `o4-mini-deep-research`, `o4-mini-deep-research-2025-06-26`, `o1`, `o1-2024-12-17`, `o1-pro`, `o1-pro-2025-03-19`

**Responses-only models:** `o1-pro`, `o3-pro`, `o3-deep-research`, `o4-mini-deep-research`, `computer-use-preview`, `gpt-5-codex`, `gpt-5-pro`, `gpt-5.1-codex-max`

**GPT-4.1:** `gpt-4.1`, `gpt-4.1-2025-04-14`, `gpt-4.1-mini`, `gpt-4.1-mini-2025-04-14`, `gpt-4.1-nano`, `gpt-4.1-nano-2025-04-14`

**Legacy (GPT-4o/4/3.5):** `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`, `gpt-4`, `gpt-3.5-turbo` (with various snapshots)

### Snapshot Pinning

For production, always pin to a specific model snapshot for consistent behavior:

```
gpt-5-2025-08-07     # Instead of "gpt-5"
```

Use model aliases like `gpt-5` only for development/experimentation. When changing model versions, re-run evals to verify prompt performance.

## Reasoning Effort

Control how many reasoning tokens the model generates before responding:

```python
response = client.responses.create(
    model="gpt-5.2",
    input="How much gold would it take to coat the Statue of Liberty?",
    reasoning={"effort": "medium"}
)
```

| Level | Description |
|---|---|
| `none` | No internal reasoning. Lowest latency. |
| `minimal` | Minimal reasoning. |
| `low` | Light reasoning. Fast responses. |
| `medium` | Moderate reasoning. Good balance. |
| `high` | Thorough reasoning. Better for complex problems. |
| `xhigh` | Maximum reasoning. Supported on `gpt-5.1-codex-max` and later. |

**Per-model defaults:**
- `gpt-5.1` defaults to `none` (no reasoning). Supports: `none`, `low`, `medium`, `high`.
- All models before `gpt-5.1` default to `medium`. Do not support `none`.
- `gpt-5-pro` defaults to and only supports `high`.
- `xhigh` is supported for all models after `gpt-5.1-codex-max`.

### Reasoning Summary

Control reasoning visibility with `reasoning.summary`:
| Value | Description |
|---|---|
| `"auto"` | Let model decide |
| `"concise"` | Brief summary (supported on `computer-use-preview` and all reasoning models after `gpt-5`) |
| `"detailed"` | Full summary |

**Tips:**
- With `none`, encourage the model to "think" or outline steps in your prompt to compensate
- Start with `none`/`low` and increase only if accuracy is insufficient
- Higher effort = more tokens = higher cost and latency

## Verbosity Control

Control how concise or detailed the model's output is:

```python
response = client.responses.create(
    model="gpt-5.2",
    input="Explain the theory of relativity.",
    text={"verbosity": "low"}
)
```

| Level | When to Use |
|---|---|
| `low` | Concise answers, simple code generation (SQL queries, short responses) |
| `medium` | Default. Balanced output length. |
| `high` | Thorough explanations, extensive code refactoring, detailed documentation |

**Note:** You can still steer verbosity through prompting even after setting it via the API parameter. The parameter defines a general token range, but actual output is flexible within that range based on prompt guidance.

## Reasoning Models

GPT-5 family models are reasoning models that break problems down step by step, producing an internal chain of thought. Key considerations:

- **Pass reasoning items back** — in multi-turn conversations, include reasoning items from previous turns for best results. Use `previous_response_id` to do this automatically.
- **Responses API gives better results** — reasoning models demonstrate higher intelligence when used with Responses vs Chat Completions (3% improvement on SWE-bench).
- The `output` array may include a `reasoning` type item alongside the `message` item.
