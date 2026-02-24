# AUTOMATION-FIX-IMPL Capture Track

Source directive: `tasks/archive/2026-02-24-14-18-24-AUTOMATION-FIX-IMPL.md` (originally `tasks/AUTOMATION-FIX-IMPL.md`)
Target living docs: `docs/AUTOMATION.md`

## Directive Capture Checklist

### 1) Hard Requirements
- [x] Filter stage uses `FILTER.md` only.
- [x] Filter stage does not use `BEHAVIOR.md`.
- [x] Filter stage remains the sole relevance/act gate for queue item progression into action stage.
- [x] Action stage uses `BEHAVIOR.md` only.
- [x] Action stage does not use `FILTER.md`.
- [x] Action stage structured output contract uses `reply_text` and `upvote`.
- [x] Action stage continues to use OpenAI Responses structured JSON schema via the official `openai` Python package.
- [x] `upvote=true` executes an upvote on the acted-on target.
- [x] Upvote execution reuses the same shared code path used by `moltbook upvote` (`PostService.upvote_target` + `PostService.evaluate_upvote_response`).
- [x] `upvote=false` skips upvote execution.
- [x] Action-stage logs now explicitly capture upvote occurrence state.

### 2) Code Changes
- [x] Updated `ActionPlan` contract in `moltbook/models/llm.py` to `reply_text` + `upvote` with alias compatibility for legacy `reply_content` payloads.
- [x] Updated `ACTION_SYSTEM_PROMPT` in `moltbook/services/automation_service.py` to the required JSON fields.
- [x] Removed runtime `should_reply` gating and switched action reply handling to `reply_text`.
- [x] Added shared upvote evaluation helpers in `moltbook/services/post_service.py`.
- [x] Updated `moltbook/commands/upvote_command.py` to use shared upvote response evaluation.
- [x] Updated automation upvote execution to use the same shared post-service path as `moltbook upvote`.
- [x] Added `action-outcome` stage logging for explicit upvote requested/attempted/performed metadata.

### 3) Tests
- [x] Updated `tests/services/test_openai_llm_client.py` for `reply_text`/`upvote` contract and strict schema assertions.
- [x] Added `tests/services/test_post_service.py` for shared upvote response evaluation.
- [x] Added `tests/services/test_automation_service.py` for upvote path reuse and action-outcome log payload checks.

### 4) Documentation
- [x] Updated `docs/AUTOMATION.md` stage contracts and wording from `reply_content`/`should_reply` to `reply_text`/`upvote`.
- [x] Documented prompt-scope separation (`FILTER.md` vs `BEHAVIOR.md`).
- [x] Documented shared upvote execution path reuse.
- [x] Documented `action-outcome` logs that capture upvote occurrence.

## Workflow Completion Checklist
- [x] Implement directives from source `*-IMPL.md`.
- [x] Validate implementation with lint/tests and fix issues.
- [x] Apply Python cleanup rules.
- [x] Apply documentation consolidation workflow (capture + verification + archiving).
- [x] Archive source directive file under `tasks/archive/` with timestamped name.

Archived file:

- `tasks/archive/2026-02-24-14-18-24-AUTOMATION-FIX-IMPL.md`
