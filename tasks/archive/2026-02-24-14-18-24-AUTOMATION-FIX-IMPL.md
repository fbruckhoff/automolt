# AUTOMATION-FIX-IMPL

## 1) Objective

Align automation filter/action semantics, action-stage structured output contract, upvote execution path reuse, and action-stage logging behavior with the required policy.

## 2) Hard Requirements (Source of Truth)

1. **Filter stage prompt scope**
   - Filter stage uses `FILTER.md` only.
   - Filter stage does **not** use `BEHAVIOR.md`.
   - Filter stage is the sole stage deciding whether to act on a queue item.

2. **Action stage prompt scope + structured output**
   - Action stage uses `BEHAVIOR.md` only.
   - Action stage does **not** use `FILTER.md`.
   - Action stage generates reply text and an upvote signal.
   - Action stage must use OpenAI structured responses via the official `openai` Python package.
   - Structured fields must be:
     - `reply_text` (text to post)
     - `upvote` (boolean)

3. **Upvote execution code reuse**
   - If `upvote == true`, automation must upvote the acted-on base item.
   - Upvote execution must reuse the same implementation path as `moltbook upvote`.
   - Minimize code duplication.

4. **No upvote when not requested**
   - If `upvote == false`, automation must skip upvoting.

5. **Action-stage logging observability**
   - Action-stage logs must explicitly capture whether upvoting actually occurred.

## 3) Verified Current Gaps

1. `ActionPlan` currently uses `should_reply` and `reply_content`; required `reply_text` field is missing.
2. Action-stage prompt contract still requests `should_reply`/`reply_content`.
3. Automation upvote path currently calls API client methods directly instead of reusing `moltbook upvote` execution path (`PostService.upvote_target` + command semantics).
4. Existing action-stage trace log currently stores prompt + raw LLM output but does not explicitly record whether upvote occurred.

## 4) Implementation Directives

### 4.1 Structured output contract update

**File:** `moltbook/models/llm.py`

1. Replace action output contract with required fields:
   - `reply_text: str`
   - `upvote: bool`
2. Remove `should_reply` from runtime decision path.
3. Normalize/validate `reply_text` (trim whitespace, enforce non-empty, bounded length).
4. Keep local parser compatibility for legacy fixtures by accepting alias `reply_content` for `reply_text` input parsing only.

### 4.2 Action-stage system prompt and runloop semantics

**File:** `moltbook/services/automation_service.py`

1. Update `ACTION_SYSTEM_PROMPT` JSON key contract to `reply_text` and `upvote`.
2. Ensure filter stage remains sole act/no-act decision:
   - Relevance from analysis controls whether action stage runs.
   - Remove action-stage `should_reply` gating.
3. Ensure action stage continues to use `BEHAVIOR.md` only.
4. Rename runtime handling from `reply_content` to `reply_text`.

### 4.3 Reuse upvote command execution path

**Files:**
- `moltbook/services/post_service.py`
- `moltbook/commands/upvote_command.py`
- `moltbook/services/automation_service.py`

1. Consolidate shared upvote response evaluation into `PostService` (message extraction + vote-removed rejection semantics).
2. Update `moltbook upvote` command to use the shared `PostService` evaluator.
3. Update automation upvote execution to call `PostService.upvote_target(...)` and shared response evaluator (same path as command).
4. Remove duplicated upvote response parsing logic from automation service.

### 4.4 Action-stage upvote occurrence logging

**File:** `moltbook/services/automation_service.py`

1. Extend action-stage logging with an explicit execution-outcome entry that records:
   - `upvote_requested`
   - `upvote_attempted`
   - `upvote_performed`
   - upvote target info
   - optional upvote message/error context
2. Ensure both dry-run and live branches log outcome with explicit upvote-performed state.

### 4.5 Tests

1. Update `tests/services/test_openai_llm_client.py` to validate `reply_text` + `upvote` structured parsing and strict schema behavior.
2. Add/adjust tests for shared upvote response evaluation in `PostService`.
3. Add/adjust tests for automation action outcome logging helper payload semantics where practical.

## 5) Validation Checklist

- [ ] Filter stage still uses `FILTER.md` only.
- [ ] Action stage uses `BEHAVIOR.md` only.
- [ ] Action stage structured output uses `reply_text` and `upvote`.
- [ ] Automation no longer uses action-stage `should_reply` gate.
- [ ] `upvote=true` path reuses same code path as `moltbook upvote`.
- [ ] `upvote=false` path performs no upvote call.
- [ ] Action-stage logs explicitly show whether upvote occurred.
- [ ] Targeted tests pass.

## 6) Documentation Updates Required

Update living docs to match implemented behavior (minimum: `docs/AUTOMATION.md`), including:
- action-stage contract (`reply_text`, `upvote`),
- filter vs action responsibility split,
- shared upvote execution path,
- action-stage log upvote-occurrence metadata.
