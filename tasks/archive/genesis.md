# moltbook-cli genesis notes (archived)

> **Archive notice:** This file preserves early brainstorming and bootstrap notes.
> It is intentionally historical and not the source of truth for the current implementation.
>
> For up-to-date implementation details, use:
> - `README.md` (user-facing capabilities and setup)
> - `AGENTS.md` (project architecture and conventions)
> - `docs/AUTOMATION.md` (consolidated automation architecture and behavior)
> - `tasks/AUTOMATION-IMPL.md` (automation doc fact-verification report)

---

# Legacy planning snapshot

The original bootstrap draft is preserved below as a raw archive.
It is commented out to prevent accidental use as current documentation.

<!--
We are going to build a CLI to interact with the Moltbook social network. Refer to your `moltbook` skill for Moltbook related information and API reference.


# Tech Stack
Python 3.14.3

Click package (refer to your click-package skill)

UV package manager (Reference: https://docs.astral.sh/uv/)

Rich library for beautiful terminal output formatting
	Repository: https://github.com/Textualize/rich
	Docs: https://rich.readthedocs.io/en/stable/

Pydantic for data validation
	Repository: https://github.com/pydantic/pydantic
	Docs: https://docs.pydantic.dev/latest/

httpx for REST API calls
	Repository: https://github.com/encode/httpx
	Docs: https://www.python-httpx.org/

Ruff linter and formatter for code quality
	Must install VSCode extension.
	README must mention use of Ruff.


# Packaging
Configured via `pyproject.toml`

- There is a `moltbook/__init__.py` at the top.
- There are no other `__init__.py` files.
- Must use absolute imports everywhere, e.g. `from moltbook.services.agent_service import AgentService`.

This means that I cannot run my CLI simply like `moltbook signup`, for example, when I want to execute the `signup` command? Instead I have to do `python -m moltbook signup`?

## pyproject.toml
Must define the entry point to the CLI.

```
[project.scripts]
moltbook = "moltbook.main:main"
```

Must define dependencies.
Be sure to specify the latest stable versions for each dependency.

Be sure to require python:
`requires-python = ">=3.14.3"`


# High-Level Architecture
There are three layers:

Top (controllers): CLI, Automation
Middle (brain): Services
Bottom (tools/workers): Models, Persistence, API Client

CLI | Automation
  ↓
Services
  ↓
Models | Persistence | API Client

## CLI
- Starts and controls the Automation
- Uses Command Handlers, which use Services
- Flow: `main.py` -> `cli.py` -> Command Handlers.

- main.py: Entry point, imports and runs `cli.py`.

- cli.py: The command router.
	- Defines main @click.group().
	- Defines the `ctx` object, sets up `Rich`, and registers commands.
	- Holds shared objects like the `Rich` console or the API Client.
	- Uses the Click package.
	- Delegates to specific command handlers in the `commands/` folder which use specific Services to do their work.

- Command handlers live in the CLI, because they manage user input and output.

### Command Handlers
- Command handler files reside under `commands/`
- Command handler file names must match the corresponding command, postfixed with `_command`.
	- e.g. `commands/signup_command.py` for the `signup` command.

Role of command handlers:
- Responsible for control flow, acting as the "driver".
	- Owns the conversation, deciding when to do what.
	- Services handle the business logic (the "how").
- The interface communicating with the user.
	- Printing pretty text with `Rich`.
	- Asking for input (`click.prompt`, etc)
	- Parsing arguments
- Delegates work to the command's Service.

- Each command handler contains command-specific presentation logic (parsing inputs, displaying outputs).
	- Providing feedback like spinners or progress bars.
	- Displaying text
	- etc.

- Each Command handler calls a specific Service, containing the business logic and rules specific to that command.

- `commands/signup_command.py` handles the signup command, using `services/agent_service.py`.

(other commands will follow later, once signup got implemented successfully)

## Automation
- Triggered by time or signals
- Uses the Services

(Just create a stub for now. We will get to this later.)

## Services
- Use Models
- Use Persistence
- Use the API Client

- Service files reside under `services/`
- Service file names must match the corresponding service, postfixed with `_service`.
	- e.g. `services/agent_service.py` for handling identity & auth, such as signup.
	- e.g. `services/post_service.py` for creating posts, delegting posts, creating submolts, upvoting, downvoting (we will ignore this for now)
	- e.g. `services/feed_service.py` for getting the feed, searching, getting submolt posts (we will ignore this for now)

- Services never call CLI commands.
	- If a Service needs another feature, it calls the corresponding Service method directly. The CLI layer manages `ctx.invoke`.

Role of Services:
- The business logic invoked by a command handler.
	- Command handlers handle the control flow.
- Uses system components such as Models, Persistance, API Client, etc.
	- Validates rules (e.g. "Is this username >= 3 chars long?")
	- May make API calls
	- May persist data (via Persistance)
	- Returns data (true/false, Objects) back to the Command Handler (the caller)

- services/agent_service.py: Handles agent signup, etc. (just implement signup support for now)

- services/post_service.py: Manages fetching / creating / deleting / voting on posts and links (just implement a simple stub for now)

- (other services here)

## Models
- Models reside under `models/`

- Data Validation: Enforces data integrity (e.g., email format, required fields) using Pydantic.
- Serialization: Handles conversion between JSON strings (for API/Disk) and Python Objects (for Logic).
- Type Safety: Provides a single source of truth for data structures, enabling IDE autocompletion and static analysis.
- JSON structure handled via Pydantic.

- Not just "classes with fields." It's typical for Python that it protects the rest of the app from bad data.

- models/agent.py: Pydantic models for agent data (Agent, AgentResponse, etc.)

- models/post.py: Pydantic models for post data (Post, PostCreate, Vote, etc.)

## Persistence
- Persistence files reside under `persistence/`

- Handles agent.json file ops
	- agent.json files live in `.agents/` subdirectories as runtime data
	- Each agent has a subdirectory in `.agents/` matching its username (handle).

- `agent.json` files are mapped to `AgentConfig` objects.

- `persistence/agent_store.py` handles all file I/O for `agent.json` files. It creates agent directories under `.agents/<handle>`, writes configuration files to disk, and checks for local existence.

## API Client
- Communicates with external Moltbook API
- Must mask Authorization header in debug outputs


# README.md requirements
- Must outline the tech stack
- Must outline the architecture
- Must outline capabilites
- Must provide installation and usage instructions


# CLI requirements
Name of the CLI: `moltbook`

The CLI can handle multiple moltbook accounts.

`moltbook init` will ask the user to confirm whether the current directory is where they wish to initialize their client (similar to how git initializes a repo). The user can select yes / no. If they select no, the initialization ends and a message directs the user to cd into their desired client directory. If they select yes, it will create supporting directories in the current working directory:

`.agents/` (folder where all agents will be stored as sub-folders with the agents name as folder name)

`client.json` file for client-level configuration, with the following structure:

```
{
  "active_agent": "HandleOfActiveAgent"
}
```


# Separation of concern requirements

- Put all API calls (httpx), Pydantic models/validation, business rules, and file read/write operations in separate reusable modules/functions.
- These core functions must not depend on Click, Rich, or any CLI-specific code.
- Click commands handle only: user input (prompts), argument parsing, Rich formatting/output, and error display.
- Do not put file operations, API logic, or validation inside @click.command functions
- Separation of concerns is important because the CLI might later be used as the backbone for a Mac app or web app backend.


# Moltbook Signup Flow

`moltbook signup` command handled by `commands/signup_command.py`, which calls `services/agent_service.py` to run the signup flow.

## Signup Flow Steps
1) User runs `moltbook signup` in the terminal

2) `main.py` loads the application and routes the command to `commands/signup_command.py` via `cli.py`.

3) `commands/signup_command.py` enters a `while` loop, using `Rich` to prompt the user for a handle.

4) `commands/signup_command.py` calls `agent_service.is_handle_available(handle)`.

5) `services/agent_service.py` `is_handle_available(handle)` performs the check:
	- It calls `api/client.py` (`check_username_availability`) to query the Moltbook API.

6) `services/agent_service.py` returns `True` or `False` to the command handler.

7) If the handle is unavailable, `commands/signup_command.py` displays an error and loops back to Step 3 so that the user gets prompted to provide an alternative handle.

8) If the handle is available, `commands/signup_command.py` prompts to provide a description of their agent.

9) Once the user has provided a valid description, `commands/signup_command.py` calls `agent_service.create_agent(handle, description)`.

10) `services/agent_service.py` `create_agent(handle, description)` calls `api/client.py` `register_agent(handle, description)` to register the agent via the Moltbook API.

11) On success, `services/agent_service.py` `create_agent(handle, description)` parses the Moltbook API response JSON and instantiates an `AgentConfig` model (from `models/agent.py`) with the new handle, the description, the api_key, the claim_url and the verification_code.

12) `services/agent_service.py` `create_agent(handle, description)` passes this model to `persistence/agent_store.py`, which writes it to `.agents/<handle>/agent.json`.

13) Upon success, `commands/signup_command.py` receives a positive response and prints a success message to the user with instructions for how to claim and verify their agent. "Please visit this URL to claim and verify your agent."

Once the tweet is detected by Moltbook, the agent's status changes from `pending_claim` to `claimed`, and the API key becomes fully active for posting.


`.agents/<handle>/agent.json` must have this structure:

```json
{
  "agent": {
    "handle": "UsernameOfTheAgentHere",
    "description": "AgentDescriptionHere",
    "api_key": null,
    "claim_url": null,
    "verification_code": null
  },
  "heartbeat": {
    "interval_seconds": 600,
    "enabled": false,
    "last_at": null
  }
}
```

## Implementation Guidance
- We must define the exact structure of the `agent.json` file using Pydantic.
- `AgentConfig` object represents `agent.json`.

———————————————————
# V2 (not relevant now, ignore)

## Development Dependencies
- Use Hatchling with VCS-backed versioning (git tags for versions) to publish to PyPI. PyPI is Python's package registry, like npm is for JavaScript. Hatchling needed because uv's native builder lacks Git VCS versioning support.
- CI/CD: GitHub Actions for automated PyPI publishing


## Universal Interface for various social networks
- Master CLI with adapters (Adapter Pattern)
- Unified Service Interface (The "Contract", or Abstraction Layer) defines generic set of actions that all networks share (Post, Reply, Login, etc)
- Architecture moves from simple stack to a "Hub and Spoke" model
- Moltbook Adapter | xyz Adapter | etc.
- Capability System: Unified Service Interface defines what is possible, but the Adapter defines what is supported.

-->

