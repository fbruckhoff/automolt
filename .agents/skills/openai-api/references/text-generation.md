# Text Generation & Prompting

## Instructions vs Input

The Responses API separates system-level guidance from user input:

- **`instructions`** — High-level instructions for the model (tone, goals, constraints). Takes priority over anything in `input`.
- **`input`** — The user's prompt. Can be a string or a message array.

```python
response = client.responses.create(
    model="gpt-5",
    instructions="You are a helpful assistant. Always respond in French.",
    input="What is the capital of Germany?"
)
```

This is equivalent to using a `developer` role message in the `input` array:

```python
response = client.responses.create(
    model="gpt-5",
    input=[
        {"role": "developer", "content": "You are a helpful assistant. Always respond in French."},
        {"role": "user", "content": "What is the capital of Germany?"}
    ]
)
```

**Note:** The `instructions` parameter only applies to the current request. When using `previous_response_id` for multi-turn conversations, instructions from previous turns are not carried forward.

## Message Roles

Messages have roles that determine their priority level:

| Role | Priority | Description |
|---|---|---|
| `developer` | Highest | Application developer instructions (business logic, rules). Replaces the legacy `system` role. |
| `user` | Medium | End-user input. Prioritized behind developer messages. |
| `assistant` | — | Model-generated responses. Used when replaying conversation history. |

Think of `developer` and `user` messages like a function and its arguments:
- `developer` messages define the function's rules and behavior
- `user` messages provide the inputs/arguments

## Prompt Engineering Best Practices

1. **Pin model snapshots** — Use specific versions like `gpt-5-2025-08-07` for consistent behavior in production, instead of aliases like `gpt-5`.

2. **Build evals** — Create evaluations that measure prompt performance so you can monitor behavior across iterations and model upgrades.

3. **Use `developer` role for instructions** — Never put untrusted user input in `developer` messages, as these take highest precedence.

4. **Encourage reasoning** — With lower reasoning effort settings (e.g. `none`), prompt the model to "think" or outline its steps before answering.

5. **Use the Responses API for reasoning models** — Reasoning models like GPT-5 demonstrate higher intelligence when used with the Responses API compared to Chat Completions.

## Reusable Prompts

Create prompts in the OpenAI dashboard and reference them by ID in API requests:

```python
response = client.responses.create(
    model="gpt-5",
    prompt={
        "id": "pmpt_abc123",
        "version": "2",
        "variables": {
            "customer_name": "Jane Doe",
            "product": "40oz juice box"
        }
    }
)
print(response.output_text)
```

**Prompt parameters:**

| Parameter | Description |
|---|---|
| `id` | Unique identifier of your prompt (from the dashboard) |
| `version` | Specific version to use (defaults to "current" as set in dashboard) |
| `variables` | Map of values to substitute for `{{placeholders}}` in your prompt |

Variable values can be strings or other input types like `input_image` or `input_file`:

```python
response = client.responses.create(
    model="gpt-5",
    prompt={
        "id": "pmpt_abc123",
        "variables": {
            "topic": "Dragons",
            "reference_pdf": {
                "type": "input_file",
                "file_id": file.id
            }
        }
    }
)
```
