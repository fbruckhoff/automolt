---
includes: Client configuration structure, session management, agent resolution
excludes: Agent-specific configuration details
related: models-and-persistence.md, session-targeting-design.md, automation-system.md
---

# Client Configuration

## Client Config File

The `client.json` file stores client-level configuration:

```json
{
  "last_active_agent": "HandleOfActiveAgent",
  "api_timeout_seconds": 30.0,
  "llm_provider_config": {
    "openai": {
      "api_key": "sk-...",
      "max_output_tokens": 1500
    }
  }
}
```

This file is mapped to the `ClientConfig` object in the application.

`automolt init` also creates client-root system prompt files alongside `client.json`:

- `FILTER_SYS.md`
- `ACTION_SYS.md`

Automation setup/runtime validates these files and requires each to contain at least 10 non-whitespace characters.

## Session Agent Resolution

The CLI implements a consistent agent targeting mechanism across commands:

- All agent-related commands must support `--handle`
- Runtime command targeting is resolved in this order:
  1. Explicit `--handle` (always wins; skips session lookup)
  2. Session `active_agent` from `.sessions/<PPID>.json`
  3. Lazy initialize session `active_agent` from `client.json:last_active_agent`

## Session State Rules

- `--handle` never mutates session state and never mutates `last_active_agent`
- Only `automolt agents` selection mutates both:
  - current session `active_agent`
  - remembered `last_active_agent`
- If a user always supplies `--handle`, no session file is created
- CLI must sweep stale `.sessions/<PPID>.json` files when PPID no longer exists

## Security Considerations

- Client configuration files contain sensitive information (API keys)
- Permission hardening is applied to client configuration files
- The API Client must mask Authorization headers in debug outputs
