# Structured Outputs

Structured Outputs ensure model responses conform to a JSON Schema you define. In the Responses API, structured outputs are configured via the `text.format` parameter (not `response_format`).

## Basic Usage

### Raw JSON Schema via `text.format`

```python
response = client.responses.create(
    model="gpt-5",
    input="Jane, 54 years old",
    text={
        "format": {
            "type": "json_schema",
            "name": "person",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "minLength": 1},
                    "age": {"type": "number", "minimum": 0, "maximum": 130}
                },
                "required": ["name", "age"],
                "additionalProperties": False
            }
        }
    }
)
```

### Using `responses.parse()` with SDK Helpers

Python (Pydantic):
```python
from openai import OpenAI
from pydantic import BaseModel

client = OpenAI()

class CalendarEvent(BaseModel):
    name: str
    date: str
    participants: list[str]

response = client.responses.parse(
    model="gpt-5",
    input=[
        {"role": "developer", "content": "Extract the event information."},
        {"role": "user", "content": "Alice and Bob are going to a science fair on Friday."}
    ],
    text_format=CalendarEvent,
)
event = response.output_parsed
```

JavaScript (Zod):
```javascript
import { zodTextFormat } from "openai/helpers/zod";
import { z } from "zod";

const CalendarEvent = z.object({
  name: z.string(),
  date: z.string(),
  participants: z.array(z.string()),
});

const response = await openai.responses.parse({
  model: "gpt-5",
  input: [
    { role: "developer", content: "Extract the event information." },
    { role: "user", content: "Alice and Bob are going to a science fair on Friday." }
  ],
  text: { format: zodTextFormat(CalendarEvent, "event") },
});
const event = response.output_parsed;
```

## Schema Requirements

### `text.format` Object Structure

```json
{
  "type": "json_schema",
  "name": "schema_name",
  "strict": true,
  "schema": { ... }
}
```

| Field | Required | Description |
|---|---|---|
| `type` | Yes | Must be `"json_schema"` |
| `name` | Yes | A name for the schema |
| `strict` | Yes | Set to `true` for guaranteed schema conformance |
| `schema` | Yes | The JSON Schema object |

### Critical Rules

- **Root must be an object** — the top-level `schema` must have `"type": "object"`
- **Root must not be `anyOf`**
- **`additionalProperties: false`** — must be set on all object types in strict mode
- **All properties must be `required`** — in strict mode, every property must be listed in `required`

## Supported JSON Schema Types

| Type | Description |
|---|---|
| `string` | Text values |
| `number` | Numeric values (float) |
| `integer` | Integer values |
| `boolean` | True/false |
| `object` | Nested objects |
| `array` | Lists |
| `enum` | Enumerated values |
| `anyOf` | Union types (not at root level) |

## Supported Constraints

### String Constraints

| Constraint | Description |
|---|---|
| `pattern` | Regular expression the string must match |
| `format` | Predefined format: `date-time`, `time`, `date`, `duration`, `email`, `hostname`, `ipv4`, `ipv6`, `uuid` |

### Number Constraints

| Constraint | Description |
|---|---|
| `minimum` | Greater than or equal to |
| `maximum` | Less than or equal to |
| `exclusiveMinimum` | Greater than |
| `exclusiveMaximum` | Less than |
| `multipleOf` | Must be a multiple of |

### Array Constraints

| Constraint | Description |
|---|---|
| `minItems` | Minimum number of items |
| `maxItems` | Maximum number of items |

## Schema Tips

- Name keys clearly and intuitively
- Create clear titles and descriptions for important keys
- Create and use evals to determine the structure that works best for your use case
- These constraints are not yet supported for fine-tuned models

## Refusals

When using structured outputs with user-generated input, the model may refuse requests for safety reasons. A refusal does not follow the schema — instead, the output includes a `refusal` field:

```python
response = client.responses.parse(
    model="gpt-5",
    input=[
        {"role": "user", "content": "potentially unsafe content"}
    ],
    text_format=MySchema,
)

# Check for refusal
if response.output_parsed is None and response.refusal:
    print(f"Refused: {response.refusal}")
else:
    print(response.output_parsed)
```

Always check for refusals when processing user-generated input.

## Function Calling vs `text.format`

| Use Case | Approach |
|---|---|
| Connecting the model to your tools, functions, data | Function calling with structured outputs |
| Structuring the model's response to the user | `text.format` with `json_schema` |

- **Function calling** — when you want the model to invoke tools with structured parameters
- **`text.format`** — when you want the model's textual response to follow a specific schema

## JSON Mode (Alternative)

For simpler cases where you just need valid JSON without a specific schema:

```json
{
  "text": {
    "format": {
      "type": "json_object"
    }
  }
}
```

JSON mode guarantees valid JSON output but does not enforce a specific schema. You must instruct the model in the prompt about the desired JSON structure. Prefer Structured Outputs (`json_schema`) for reliability.
