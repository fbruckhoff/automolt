# UPVOTE-IMPL Capture Track

Source directive: `tasks/archive/2026-02-23-18-08-06-UPVOTE-IMPL.md` (originally `tasks/UPVOTE-IMPL.md`)
Target living docs: `docs/AUTOMATION.md`, `README.md`

## Directive Capture Checklist

### 1) Objective and Scope
- [x] Added action-stage structured field `upvote: bool` to `ActionPlan`.
- [x] Added automation runtime behavior to execute upvotes for acted items when `upvote=true`.
- [x] Added top-level `moltbook upvote` command for posts/comments by URL or ID.
- [x] Updated setup behavior guidance to include posting/commenting style and upvote circumstances.

### 2) Policy Constraints
- [x] Automation does not perform downvotes.
- [x] Setup guidance explicitly states downvotes are not part of automation behavior.
- [x] Automation upvotes only for items acted on in the same action branch.
- [x] Automation never upvotes unrelated discovered-but-not-acted queue items.

### 3) Data Contracts
- [x] `ActionPlan` includes `upvote: bool`.
- [x] `ACTION_SYSTEM_PROMPT` includes `upvote` and acted-item/no-downvote policy text.
- [x] Structured action schema tests validate `upvote` shape and required fields.

### 4) Automation Runloop Semantics
- [x] Upvote target resolution is deterministic (post item -> post ID, comment item -> comment ID).
- [x] Upvote is evaluated only after actionable reply decision and normalized non-empty reply content.
- [x] Dry mode performs no write calls for comments or upvotes.
- [x] Dry-mode heartbeat payload includes upvote intent/target metadata.
- [x] Upvote API failures are logged and do not erase acted state/replied item.
- [~] Separate `ACTION_UPVOTE` event type was not introduced.
  - Reason: Existing `ACTION_DRY_RUN`/`ACTION_POSTED` payloads now include explicit upvote metadata and results, preserving observability without expanding event enum surface.

### 5) API and Service Layer
- [x] Added API client method `upvote_post`.
- [x] Added API client method `upvote_comment`.
- [x] Added PostService wrappers `upvote_post`, `upvote_comment`, and `upvote_target` dispatcher.

### 6) CLI Command Surface
- [x] Added `moltbook/commands/upvote_command.py`.
- [x] Registered `upvote` in `moltbook/cli.py`.
- [x] `upvote` supports `--handle` with shared session-aware resolution behavior.
- [x] `upvote` supports `--type auto|post|comment`.
- [x] URL parsing supports post URLs and comment fragment URLs.
- [x] URL/type mismatch validation returns explicit actionable errors.
- [x] Auto-ID disambiguation supports `comment_` heuristic and fails with guidance otherwise.

### 7) Setup UX Guidance
- [x] Updated `PROMPT_DESCRIPTIONS["behavior"]` text for posting/commenting constraints and acted-item upvote criteria.

### 8) Living Documentation
- [x] Updated `docs/AUTOMATION.md` with upvote contract, policy, dry-run semantics, and monitor payload details.
- [x] Updated `README.md` capability table to include `moltbook upvote`.

### 9) Test Coverage
- [x] Updated `tests/services/test_openai_llm_client.py` for action parsing and strict schema (`upvote`).
- [x] Added `tests/services/test_automation_service.py` covering action-stage upvote behavior and failure semantics.
- [x] Added `tests/commands/test_upvote_command.py` covering parsing and command success/failure paths.

## Workflow Completion Checklist
- [x] Implement directives from source `*-IMPL.md`.
- [x] Validate implementation with lint/tests and fix issues.
- [x] Apply Python cleanup rules.
- [x] Apply documentation consolidation workflow (capture + verification + archiving).
- [x] Archive source directive file under `tasks/archive/` with timestamped name.

Archived file:

- `tasks/archive/2026-02-23-18-08-06-UPVOTE-IMPL.md`
