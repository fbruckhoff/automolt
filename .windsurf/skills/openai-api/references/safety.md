# Safety & Security

Best practices for building safe applications with the OpenAI API, focused on preventing prompt injections, data leakage, and unintended agent behavior.

## Types of Risk

### Prompt Injections

A prompt injection occurs when untrusted text or data enters an AI system and malicious content attempts to override instructions. Goals include:
- Exfiltrating private data via downstream tool calls
- Taking misaligned actions
- Changing model behavior in unintended ways

Example: A prompt tricks a data lookup agent into sending raw customer records instead of the intended summary.

### Private Data Leakage

A model may accidentally share private data without an attacker involved:
- Sending more data to a tool than intended
- Including sensitive information in responses
- Leaking context from previous conversations

## Mitigation Strategies

### 1. Don't Use Untrusted Variables in Developer Messages

`developer` messages take precedence over `user` and `assistant` messages. Injecting untrusted input into developer messages gives attackers the highest degree of control.

**Rule:** Always pass untrusted inputs through `user` role messages to limit their influence.

```python
# WRONG — untrusted input in developer message
response = client.responses.create(
    model="gpt-5",
    instructions=f"Process this data: {user_provided_data}",  # DANGEROUS
    input="Summarize the data"
)

# CORRECT — untrusted input in user message
response = client.responses.create(
    model="gpt-5",
    instructions="You are a data summarization assistant. Summarize the data the user provides.",
    input=user_provided_data  # Safe: user role has lower priority
)
```

### 2. Use Structured Outputs to Constrain Data Flow

Define structured outputs between processing steps (enums, fixed schemas, required fields) to eliminate freeform channels that attackers can exploit:

```python
response = client.responses.create(
    model="gpt-5",
    input=user_input,
    text={
        "format": {
            "type": "json_schema",
            "name": "safe_output",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["summarize", "translate", "classify"]},
                    "result": {"type": "string"}
                },
                "required": ["action", "result"],
                "additionalProperties": False
            }
        }
    }
)
```

### 3. Steer with Clear Guidance and Examples

Strengthen prompts with:
- Clear documentation of desired policies
- Explicit examples of correct behavior
- Anticipated edge cases and how to handle them
- Examples of what NOT to do

### 4. Use GPT-5 or GPT-5-mini

These models are more disciplined about following developer instructions and exhibit stronger robustness against jailbreaks and indirect prompt injections. Use them for higher-risk workflows.

### 5. Keep Tool Approvals Enabled

When using tools, ensure end users can review and confirm operations, especially:
- Write operations (creating, updating, deleting data)
- Operations involving sensitive data
- Operations with external side effects

### 6. Use Guardrails for User Inputs

Sanitize incoming inputs to:
- Redact personally identifiable information (PII)
- Detect jailbreak attempts
- Validate input format and length

Guardrails alone are not foolproof but provide an effective first defense layer.

### 7. Run Trace Graders and Evals

Use evaluations to:
- Monitor model performance across prompt iterations
- Score agent decisions, tool calls, and reasoning steps
- Catch unintended behavior patterns early
- Understand where agents perform well or make mistakes

## Combined Defense Strategy

Design workflows so untrusted data never directly drives agent behavior:

1. Extract only specific structured fields from external inputs
2. Use structured outputs between processing nodes
3. Pass untrusted content via `user` messages only
4. Enable tool confirmations for sensitive operations
5. Run evals to validate behavior continuously

Risk rises when agents process arbitrary text that influences tool calls. Structured outputs and isolation reduce, but don't fully eliminate, this risk.
