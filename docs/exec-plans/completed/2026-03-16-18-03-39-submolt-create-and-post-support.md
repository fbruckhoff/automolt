# Add Useful Submolt Creation and Posting Support

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This document must be maintained in accordance with `.agents/PLANS.md`.

## Purpose / Big Picture

After this change, a claimed agent can use `automolt` to create a new Moltbook submolt with the fields Moltbook actually supports, then publish a post into that submolt from the CLI. The result must be visible through an observable command flow, not just reflected in code. In practice that means `automolt submolt create ...` needs to accept the Moltbook creation fields, `automolt submolt post ...` needs to exist and send a real post to a named submolt, and the CLI needs to handle Moltbook’s content verification challenge so the newly created submolt or post does not remain hidden in a pending state.

## Progress

- [x] (2026-03-16 17:41Z) Read `.agents/PLANS.md`, `ARCHITECTURE.md`, the design-doc index, current `submolt`/`post` command and service code, and the Moltbook public skill documentation sections for posts, submolts, and AI verification challenges.
- [x] (2026-03-16 17:45Z) Authored this active ExecPlan in `docs/exec-plans/active/submolt-create-and-post-support.md`.
- [x] (2026-03-16 17:53Z) Replaced the prompt-driven `automolt submolt create` flow with explicit Moltbook-aligned options, useful bare-group help output, and shared agent-targeting helpers.
- [x] (2026-03-16 17:56Z) Added `automolt submolt post`, typed post-creation models, and API/service support for creating posts in a named submolt.
- [x] (2026-03-16 18:03Z) Added `automolt/services/content_verification_service.py` and wired automatic verification for pending submolt and post publication responses.
- [x] (2026-03-16 18:13Z) Added automated tests for CLI help behavior, verification solving, and post-service validation; validated with `uv run python -m unittest discover -s tests`, `uv run ruff check .`, and the `submolt` help commands.
- [x] (2026-03-16 18:15Z) Updated `README.md`, confirmed documentation depth remains `minimal`, and prepared the plan for archival with no deferred work.

## Surprises & Discoveries

- Observation: The repository already has a `submolt create` implementation, but it is interactive-only, does not expose Moltbook’s `allow_crypto` field, and there is no post-creation command for submolts.
  Evidence: `automolt/commands/submolts/submolt_command.py` contains only the `create` subcommand and prompts interactively for all fields.

- Observation: Moltbook content creation can return a `verification_required` challenge for posts, comments, and submolts; unverified content remains hidden.
  Evidence: `https://www.moltbook.com/skill.md` states that content creation responses may include `verification_required: true`, a `verification` object, and a required follow-up call to `POST /api/v1/verify`.

- Observation: Obfuscation symbols inside Moltbook challenge text can look like arithmetic operators, so the solver cannot treat every visible `/` or `-` character as the intended math operation.
  Evidence: The initial solver misread decorative `/` and `-` characters in `A] lO^bSt-Er S[wImS aT/ tW]eNn-Tyy ...` until operator detection was limited to true numeric symbol expressions or normalized operation words.

## Decision Log

- Decision: Treat automatic handling of Moltbook verification challenges as in-scope for this feature.
  Rationale: Without verification support, the CLI could report “created” while the new submolt or post remains hidden and unusable, which fails the user-visible outcome required by this plan.
  Date/Author: 2026-03-16 / Cascade

- Decision: Keep the feature centered on the existing `submolt` command group instead of introducing a separate top-level `post` command.
  Rationale: The user explicitly asked to design the `submolt` command accordingly, and the goal is a cohesive workflow for creating a community and posting inside it.
  Date/Author: 2026-03-16 / Cascade

- Decision: Documentation depth starts at `minimal`.
  Rationale: This work changes user-facing CLI behavior and help surfaces, so `README.md` must be updated. At current scope, no architecture document changes are planned unless implementation reveals a broader contract change.
  Date/Author: 2026-03-16 / Cascade

- Decision: Implement verification handling as one shared service used by both submolt creation and post creation.
  Rationale: The same pending-content contract applies across both command paths, and one reusable service keeps the command handlers focused on UX and the orchestration logic focused on publication policy.
  Date/Author: 2026-03-16 / Cascade

## Outcomes & Retrospective

Implemented the planned submolt workflow end to end. `automolt submolt` now shows useful help output when invoked without a subcommand. `automolt submolt create` now accepts explicit Moltbook-aligned options for `--name`, `--display-name`, optional `--description`, and `--allow-crypto`, while preserving the repository’s existing `--handle` targeting pattern. `automolt submolt post` now creates text or link posts inside a named submolt and reports created identifiers in a Rich panel consistent with the rest of the CLI.

The HTTP and service layers now support post creation and verification submission. `automolt/api/client.py` exposes `create_post` and `verify_content`, `automolt/services/post_service.py` now orchestrates post creation, and `automolt/services/submolt_service.py` now handles Moltbook’s full submolt creation contract. The new `automolt/services/content_verification_service.py` solves representative obfuscated math challenges deterministically and submits the answer immediately so pending content becomes published in the normal success path.

Validation passed with `uv run python -m unittest discover -s tests`, `uv run ruff check .`, `uv run python -m automolt.main submolt --help`, `uv run python -m automolt.main submolt create --help`, and `uv run python -m automolt.main submolt post --help`. Documentation depth remained `minimal`; only `README.md` required updates. No implementation or documentation work was intentionally deferred, so no debt entry was added.

## Context and Orientation

`automolt` is a Python command-line client for Moltbook. Command handlers live under `automolt/commands`, service orchestration lives under `automolt/services`, typed API contracts live under `automolt/models`, and HTTP requests to Moltbook live under `automolt/api/client.py`. The CLI root is `automolt/cli.py`, which constructs shared service objects and registers top-level commands.

The current submolt entry point is `automolt/commands/submolts/submolt_command.py`. It defines a `submolt` Click group and one `create` subcommand. That subcommand resolves the active agent with the standard handle-targeting contract, loads the agent’s API key, prompts for a name, display name, and description, and calls `SubmoltService.create_submolt`. This is not sufficient for the requested workflow because it does not expose Moltbook’s optional `allow_crypto` field, it is not shaped like the other option-driven commands, and there is no command that lets an agent publish a post into a submolt.

The current submolt service is `automolt/services/submolt_service.py`. It wraps `MoltbookClient.create_submolt` and validates the response using `automolt/models/submolt.py`. The current post service is `automolt/services/post_service.py`, but it only handles comments and upvotes. `automolt/api/client.py` also lacks a method for `POST /posts` and lacks a method for `POST /verify`.

A “submolt” is a Moltbook community. A “verification challenge” is a temporary math puzzle Moltbook can require after creating content. The response includes a verification code and an obfuscated word problem. The client must solve the math problem and submit the answer to `POST /api/v1/verify` before the content becomes visible. Moltbook’s public skill documentation states that submolt challenges expire in 30 seconds and post challenges expire in 5 minutes, so this CLI must verify immediately when needed.

## Plan of Work

The first milestone updates `automolt/commands/submolts/submolt_command.py` so the `submolt` group becomes useful on its own and its `create` subcommand matches Moltbook’s field contract. Replace the purely prompt-driven creation path with explicit command options for `--name`, `--display-name`, optional `--description`, and `--allow-crypto`, while preserving the standard `--handle` targeting behavior and the style of concise help strings used by `comment`, `search`, and `profile`. The command should validate submolt names according to the Moltbook contract described in the public skill file: lowercase, hyphen-safe, and 2-30 characters. If the bare `submolt` group is invoked without a subcommand, it should produce useful help output instead of silently doing nothing.

The second milestone adds a new `submolt post` subcommand in `automolt/commands/submolts/submolt_command.py`. This command should accept a target submolt name and the fields required to create a post there. The CLI surface should remain concise and consistent: one argument or option must clearly identify the target submolt, `--title` must be required, and content fields must be validated so the command cannot submit an empty post. This work requires adding a `create_post` method to `automolt/api/client.py`, adding typed post-creation models in `automolt/models/post.py`, and extending `automolt/services/post_service.py` with a post-creation method that normalizes the request, validates the response, and returns a typed result to the command handler.

The third milestone adds shared verification support used by both submolt creation and post creation. Implement this in one reusable service-oriented module under `automolt/services/` rather than duplicating logic in command handlers. The new verification flow must detect when Moltbook returns `verification_required`, extract the verification code and challenge text from the created content payload, solve the simple arithmetic challenge, submit the answer through a new `MoltbookClient` verification method, and surface success or failure through the existing command-level `MoltbookAPIError` handling pattern. The solver should be deterministic and implemented locally in Python. It must normalize the obfuscated challenge text, recover the two numeric operands and the arithmetic operation, and format the answer with two decimal places before submission.

The fourth milestone adds validation and finish work. Add automated tests in a new `tests/` package if necessary, using the standard library `unittest` module and `click.testing.CliRunner` so no new dependency is required. Cover at least three areas: command help/argument behavior for the new `submolt` flows, solver behavior on representative verification challenge strings, and service-level validation for empty or malformed post requests. Then update `README.md` so the CLI capability matrix includes the new `submolt post` surface and the richer `submolt create` behavior. If implementation ends up changing any design document, update `docs/design-docs/_index.md` accordingly; otherwise keep documentation depth at `minimal`.

## Concrete Steps

All commands below run from the repository root: `/Users/franz/Desktop/Tapsweets/Apps/CLI/automolt/automolt`.

Implement the feature by editing these files:

1. `automolt/commands/submolts/submolt_command.py`
2. `automolt/services/submolt_service.py`
3. `automolt/services/post_service.py`
4. `automolt/api/client.py`
5. `automolt/models/submolt.py`
6. `automolt/models/post.py`
7. One new reusable verification support module under `automolt/services/`
8. `README.md`
9. New tests under `tests/`

Use these validation commands as work proceeds and at completion:

    uv run python -m unittest discover -s tests
    uv run ruff check .
    uv run python -m automolt.main submolt --help
    uv run python -m automolt.main submolt create --help
    uv run python -m automolt.main submolt post --help

If a real claimed agent and API key are available in a separate workspace client directory, the end-to-end proof commands are:

    automolt submolt create --name example-lab --display-name "Example Lab" --description "A place for experiments"
    automolt submolt post example-lab --title "First post" --content "Hello from automolt"

Expected human-visible outcomes are a success message that identifies the created submolt, followed by a success message that identifies the created post and the target submolt. If Moltbook requires verification, the command should still complete publication automatically rather than leaving the content pending.

## Validation and Acceptance

Acceptance is satisfied only when all of the following are true.

First, the command surface is observable and useful. `uv run python -m automolt.main submolt --help` must show a meaningful command group, and the help for `submolt create` and `submolt post` must show the new option and argument contract. `automolt submolt` must no longer be a silent no-op.

Second, the CLI can express the full requested workflow. There must be a supported path to create a submolt with Moltbook’s supported fields, including `allow_crypto`, and a supported path to create a post inside a named submolt.

Third, pending content is handled correctly. When a creation response contains a verification challenge, the new verification module must solve it, submit it, and allow the command to report publication success. Tests must cover representative challenge strings with inserted symbols and unusual casing.

Fourth, validation commands must pass. `uv run python -m unittest discover -s tests` and `uv run ruff check .` must both succeed. If any real API validation is run, the observed output should show created identifiers rather than only local state changes.

## Idempotence and Recovery

This plan is safe to apply incrementally. Help-text checks, unit tests, and lint can be run repeatedly without side effects. The only non-idempotent operations are real Moltbook content creation calls, which should only be run intentionally in a separate client workspace with a claimed agent.

If a real creation command fails before Moltbook accepts the content, the user can rerun the command after fixing the validation problem. If Moltbook returns a verification expiration or incorrect-answer error, the safe recovery path is to rerun the original create command so Moltbook issues a fresh verification code. The CLI must not persist partial verification state locally.

## Artifacts and Notes

Expected help output excerpts after implementation:

    Usage: automolt submolt [OPTIONS] COMMAND [ARGS]...
    Manage submolts (communities) on Moltbook.

    Commands:
      create
      post

Expected success output shape for submolt creation:

    Submolt 'Example Lab' created!
    Name: example-lab
    Owner: YourAgent

Expected success output shape for post creation:

    Post created successfully!
    Post ID: <uuid>
    Submolt: example-lab
    Title: First post

## Interfaces and Dependencies

In `automolt/api/client.py`, define a `create_post` method that sends `POST /posts` with a JSON payload containing the target submolt name, title, and optional body or URL. Also define a verification submission method for `POST /verify` that accepts a verification code and a formatted numeric answer.

In `automolt/services/post_service.py`, define a post-creation orchestration method that validates CLI input, delegates to `MoltbookClient.create_post`, invokes the shared verification helper when needed, and returns a typed `PostCreateResponse` model.

In `automolt/services/submolt_service.py`, extend `create_submolt` so it accepts Moltbook’s supported fields, delegates to `MoltbookClient.create_submolt`, invokes the shared verification helper when needed, and returns a typed `SubmoltCreateResponse` model enriched with enough status for the command to render whether verification was performed.

In the new shared verification module, define a small, explicit interface for solving and completing content verification. It must accept the authenticated API key and the raw created-content payload, and it must either return normally after successful publication or raise `MoltbookAPIError` with a clear operator-facing message.

## Revision Notes

- 2026-03-16 / Cascade: Created the initial living ExecPlan after researching the existing submolt implementation and the current Moltbook API documentation. The plan explicitly includes automatic verification because hidden pending content would fail the requested end-to-end behavior.
- 2026-03-16 / Cascade: Updated the living sections after implementation and validation, recording the final command surface, verification approach, and green validation evidence before archival.
