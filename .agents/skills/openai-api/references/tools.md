# Tools

The Responses API provides built-in tools and supports custom function calling, all within a single API request. The model can call multiple tools during one request as part of its agentic loop.

## Built-In Tools

Specify built-in tools directly in the `tools` array:

```python
response = client.responses.create(
    model="gpt-5",
    input="Who is the current president of France?",
    tools=[{"type": "web_search_preview"}]
)
print(response.output_text)
```

| Tool | Type Value | Description |
|---|---|---|
| Web Search | `web_search_preview` | Search the web for current information |
| File Search | `file_search` | Search through uploaded files |
| Code Interpreter | `code_interpreter` | Execute code to perform calculations, analysis, etc. |
| Computer Use | `computer_use` | Interact with a computer interface |
| Remote MCP | `mcp` | Connect to remote MCP servers |
| Apply Patch | `apply_patch` | Create, delete, or update files using unified diffs |
| Function Shell | `function_shell` | Execute shell commands in a sandbox |
| Image Generation | `image_generation` | Generate images |

Built-in tools are executed server-side by OpenAI — you don't need to implement them yourself.

### Web Search Configuration

```json
{
    "type": "web_search_preview",
    "search_context_size": "medium",
    "user_location": {"type": "approximate", "city": "...", "region": "...", "country": "..."}
}
```

| Field | Description |
|---|---|
| `search_context_size` | `"low"`, `"medium"` (default), or `"high"` — controls search context |
| `user_location` | Approximate user location for localized results |

## Custom Function Calling

Define custom functions the model can call:

```python
response = client.responses.create(
    model="gpt-5",
    input="What's the weather in Paris?",
    tools=[{
        "type": "function",
        "name": "get_weather",
        "description": "Get current weather for a location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City name"},
                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
            },
            "required": ["location"],
            "additionalProperties": False
        }
    }]
)
```

When the model wants to call a function, the `output` array will include a `function_call` item with the function name and arguments. Your application must execute the function and return the result.

## Custom Tools (Freeform Inputs)

Define tools with `type: custom` to let the model send plaintext inputs (code, SQL, shell commands) instead of JSON:

```json
{
    "type": "custom",
    "name": "code_exec",
    "description": "Executes arbitrary python code"
}
```

### CFG-Constrained Outputs

GPT-5.2 supports context-free grammars (CFGs) for custom tools. Attach a Lark grammar to constrain outputs to a specific syntax or DSL (e.g. SQL grammar). This ensures the model's tool call text matches your grammar exactly.

### Best Practices for Custom Tools

- Write concise, explicit tool descriptions
- State clearly if you want the model to always call the tool
- Validate outputs on the server side — freeform strings require safeguards

## `allowed_tools` — Restricting Tool Subsets

Define a full toolkit but restrict the model to a subset:

```json
{
    "tools": [ ... all tools ... ],
    "tool_choice": {
        "type": "allowed_tools",
        "mode": "auto",
        "tools": [
            {"type": "function", "name": "get_weather"},
            {"type": "function", "name": "search_docs"}
        ]
    }
}
```

| `mode` | Behavior |
|---|---|
| `auto` | Model may pick any of the allowed tools |
| `required` | Model must invoke one of the allowed tools |

Benefits:
- Greater safety and predictability
- Improved prompt caching (full toolkit stays stable)
- Dynamic restriction without modifying the tools list

## `tool_choice` Types

| Type | Description |
|---|---|
| `"none"` | Model will not call any tool |
| `"auto"` | Model picks between message or tool calls (default) |
| `"required"` | Model must call one or more tools |
| `{type: "allowed_tools", mode, tools}` | Restrict to subset. `mode`: `"auto"` or `"required"`. `tools`: list of `{type, name}` |
| `{type: "function", name}` | Force a specific function call |
| `{type: "mcp", server_label, name?}` | Force a specific MCP tool |
| `{type: "custom", name}` | Force a specific custom tool |
| `{type: "file_search"}` | Force file search |
| `{type: "web_search_preview"}` | Force web search |
| `{type: "code_interpreter"}` | Force code interpreter |
| `{type: "image_generation"}` | Force image generation |
| `{type: "apply_patch"}` | Force the apply_patch tool |
| `{type: "shell"}` | Force the shell tool |

## Function Tool Parameters

```json
{
    "type": "function",
    "name": "function_name",
    "description": "What this function does",
    "strict": true,
    "parameters": { ... JSON Schema ... }
}
```

| Field | Required | Description |
|---|---|---|
| `name` | Yes | Function name |
| `parameters` | Yes | JSON Schema describing the function's parameters |
| `strict` | Yes | Whether to enforce strict parameter validation (default `true`) |
| `description` | No | Used by the model to decide whether to call the function |

## File Search Tool Parameters

```json
{
    "type": "file_search",
    "vector_store_ids": ["vs_..."],
    "filters": { ... },
    "max_num_results": 10,
    "ranking_options": { "ranker": "auto", "score_threshold": 0.5 }
}
```

| Field | Required | Description |
|---|---|---|
| `vector_store_ids` | Yes | IDs of vector stores to search |
| `filters` | No | Comparison or compound filter: `{key, type: "eq"/"ne"/"gt"/etc., value}` |
| `max_num_results` | No | Max results to return |
| `ranking_options` | No | `{ranker: "auto", score_threshold: 0-1}` |

## MCP Tool

```json
{
    "type": "mcp",
    "server_label": "my_server",
    "server_url": "https://example.com/mcp",
    "require_approval": "never",
    "allowed_tools": ["tool1", "tool2"]
}
```

| Field | Required | Description |
|---|---|---|
| `server_label` | Yes | Unique label for referencing the server |
| `server_url` | Yes | URL of the MCP server |
| `require_approval` | No | `"never"`, `"always"`, or `{never: {tool_names: [...]}}` |
| `allowed_tools` | No | Restrict which tools from the server can be used |
| `headers` | No | Custom HTTP headers for server requests |
