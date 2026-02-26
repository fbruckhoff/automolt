# Multi-Turn Conversations

## Approaches

There are two ways to manage conversation state with the Responses API:

1. **Manual context** — append `output` items to the `input` array
2. **Stateful chaining** — use `previous_response_id` with `store: true`

## Manual Context Management

Append the model's `output` array items back to the `input` for the next request:

```python
context = [
    {"role": "user", "content": "What is the capital of France?"}
]

res1 = client.responses.create(
    model="gpt-5",
    input=context,
)

# Append the first response's output to context
context += res1.output

# Add the next user message
context += [
    {"role": "user", "content": "And its population?"}
]

res2 = client.responses.create(
    model="gpt-5",
    input=context,
)
```

This gives you full control over the conversation history, but you must manage the context array yourself.

## Stateful Chaining with `previous_response_id`

Pass the ID of a previous response to automatically chain context:

```python
res1 = client.responses.create(
    model="gpt-5",
    input="What is the capital of France?",
    store=True
)

res2 = client.responses.create(
    model="gpt-5",
    input="And its population?",
    previous_response_id=res1.id,
    store=True
)
```

**Requirements:**
- `store: true` must be set on the previous response (so it's persisted server-side)
- The `previous_response_id` includes all prior context, including reasoning items

**Benefits:**
- Simpler code — no need to manage context arrays
- Reasoning items are automatically preserved across turns
- Can create forks in conversation history by referencing the same `previous_response_id` in multiple requests

## Encrypted Reasoning (ZDR / Stateless Workflows)

For organizations with Zero Data Retention requirements that cannot use stateful responses:

1. Set `store: false`
2. Add `"reasoning.encrypted_content"` to the `include` parameter
3. The API returns encrypted reasoning tokens
4. Pass encrypted reasoning items back in future requests

```python
res1 = client.responses.create(
    model="gpt-5",
    input="Complex problem...",
    store=False,
    include=["reasoning.encrypted_content"]
)

# Pass encrypted reasoning back in next request
res2 = client.responses.create(
    model="gpt-5",
    input=res1.output + [{"role": "user", "content": "Follow up question"}],
    store=False,
    include=["reasoning.encrypted_content"]
)
```

Encrypted content is decrypted in-memory, used for generation, and discarded — never written to disk.

## Best Practices

- **Always pass reasoning items back** — reasoning models perform best when their previous chain of thought is available
- **Use `previous_response_id`** when possible — it's simpler and automatically preserves reasoning context
- **Use manual context** when you need fine-grained control (e.g. pruning/editing history)
- **Remember `instructions` don't persist** — the `instructions` parameter from previous turns is not carried forward; re-send if needed
