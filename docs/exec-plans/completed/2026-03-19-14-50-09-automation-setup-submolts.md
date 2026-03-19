# Extend automation setup to manage BEHAVIOR_SUBMOLT.md

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This document must be maintained in accordance with `.agents/PLANS.md`.

## Purpose / Big Picture

After this change, operators can configure all automation prompt artifacts from one place, including the planner policy file `BEHAVIOR_SUBMOLT.md`, directly through `automolt automation setup`. The user-visible outcome is that both setup modes (interactive wizard and atomic flags) will offer a first-class path to create or edit the submolt behavior file instead of requiring manual file editing outside the setup command.

A human can verify this by running `automolt automation setup --help` and seeing a dedicated submolt-behavior flag, then using either interactive setup or flag-based setup to create/update `BEHAVIOR_SUBMOLT.md` under `.agents/<handle>/`.

Documentation depth decision: `minimal`, because this is a command-surface and setup-flow enhancement that does not change core planner runtime architecture.

## Progress

- [x] (2026-03-17 17:31Z) Researched existing setup command flow, including atomic and interactive pathways.
- [x] (2026-03-17 17:33Z) Mapped current prompt prerequisites in setup and runtime validation to identify safe integration points.
- [x] (2026-03-17 17:35Z) Authored this active ExecPlan with implementation, validation, and documentation steps.
- [x] (2026-03-17 18:10Z) Implemented setup command support for submolt behavior prompt in both interactive and atomic modes.
- [x] (2026-03-17 18:15Z) Added CLI tests for setup help, atomic prompt-file workflow, and success-panel status output for the new setup option.
- [x] (2026-03-17 18:18Z) Updated design docs for the expanded setup command surface and verified design-doc index metadata.
- [x] (2026-03-17 18:19Z) Ran validation commands (`unittest discover`, targeted setup tests, `ruff check`, and setup help inspection) with passing results.

## Surprises & Discoveries

- Observation: `automation setup` already has robust prompt-edit UX primitives that can be reused for a third prompt without introducing new persistence code paths.
  Evidence: `automolt/commands/automation/setup_command.py` uses shared helpers (`_collect_prompt_file`, `_apply_atomic_prompt_update`, `_open_editor_and_collect_content`) that are parameterized by `prompt_name`.

- Observation: setup completeness checks currently only require `FILTER.md` and `BEHAVIOR.md`, while planner policy loading is handled as planner-stage gating at runtime.
  Evidence: `automolt/commands/automation/setup_command.py:_collect_missing_setup_requirements` only validates `("filter", "behavior")`, and `automolt/services/automation_service.py:_validate_required_prompt_files` also only requires those two per-agent prompts.

- Observation: the planner policy file already has a dedicated operational command (`automation reload`), so adding setup-time editing should align with existing `behavior_submolt` naming and file location conventions.
  Evidence: `automolt/commands/automation/reload_command.py` reloads `BEHAVIOR_SUBMOLT.md` through `AutomationService.reload_submolt_policy`.

- Observation: Click option wiring for existing prompt flags (`--filter-md`, `--behavior-md`) is flag-only (`flag_value=""`) and does not accept a separate path argument token.
  Evidence: validation run surfaced `Error: Got unexpected extra argument (...)` when invoking `automation setup --behavior-submolt-md <path>`, matching current behavior for existing prompt flags.

## Decision Log

- Decision: Add a new setup flag following existing naming style as `--behavior-submolt-md`.
  Rationale: Existing prompt flags use the pattern `--<prompt>-md`; this keeps CLI ergonomics and discoverability consistent with `--filter-md` and `--behavior-md`.
  Date/Author: 2026-03-17 / Cascade

- Decision: Keep `BEHAVIOR_SUBMOLT.md` optional for setup-completeness gating in this iteration.
  Rationale: Planner policy availability is intentionally planner-stage scoped; forcing it as a global setup prerequisite would regress the current contract where baseline reply automation can run without planner policy content.
  Date/Author: 2026-03-17 / Cascade

- Decision: Reuse existing prompt helper functions and persistence abstraction (`prompt_store`) rather than introducing a submolt-specific setup path.
  Rationale: `prompt_store.get_prompt_path(..., prompt_name)` already maps arbitrary prompt names to `.agents/<handle>/<PROMPT>.md`, so `behavior_submolt` naturally resolves to `BEHAVIOR_SUBMOLT.md` with minimal code churn.
  Date/Author: 2026-03-17 / Cascade

- Decision: Keep prompt-flag parser semantics aligned with existing setup options (flag-only default-path editor flow) and make help/docs wording explicit instead of introducing a broader parser-contract change in this plan.
  Rationale: path-argument parsing behavior predates this work and affects existing prompt flags; this plan remains scoped to adding first-class `BEHAVIOR_SUBMOLT.md` setup parity without changing established option-parsing behavior.
  Date/Author: 2026-03-17 / Cascade

## Outcomes & Retrospective

Completed outcome: `automolt automation setup` now supports `BEHAVIOR_SUBMOLT.md` management in both flows. Interactive setup collects `behavior_submolt` with the same UX as other prompts, atomic setup supports `--behavior-submolt-md`, and setup success output includes `BEHAVIOR_SUBMOLT.md` status.

Validation outcome: all local checks passed (`uv run python -m unittest discover -s tests`, `uv run python -m unittest tests/test_automation_setup_command.py`, `uv run ruff check .`, `uv run python -m automolt.main automation setup --help`). Runtime prerequisite semantics remain unchanged (`FILTER.md` + `BEHAVIOR.md` required; `BEHAVIOR_SUBMOLT.md` optional and planner-scoped).

## Context and Orientation

`automolt automation setup` is implemented in `automolt/commands/automation/setup_command.py`. It has two user flows:

1. Interactive mode (no atomic flags): prompts for search query/cutoff, collects prompt files, then collects stage provider/model settings.
2. Atomic mode (one or more flags): applies targeted updates through `_run_atomic_setup(...)` and reports missing requirements.

Per-agent prompt files are persisted through `automolt/persistence/prompt_store.py`, where `prompt_name` maps directly to `.agents/<handle>/<PROMPT_NAME_UPPER>.md`. This means prompt name `behavior_submolt` resolves to `.agents/<handle>/BEHAVIOR_SUBMOLT.md` without new store code.

Runtime prerequisite validation lives in `automolt/services/automation_service.py:_validate_required_prompt_files(...)` and currently requires only `FILTER.md` and `BEHAVIOR.md`. Planner policy (`BEHAVIOR_SUBMOLT.md`) is loaded and validated by planner-specific runtime logic and can also be manually refreshed via `automolt automation reload`.

Because this plan is about setup ergonomics, command-handler modules should own all UX/option changes while persistence and service layers remain focused on existing responsibilities.

## Plan of Work

Milestone 1 introduces command-surface parity for planner policy prompt management. Add one new setup option for submolt behavior prompt editing in atomic mode and add one new interactive step that reuses existing prompt collection UX. Extend setup status output so users can see whether `BEHAVIOR_SUBMOLT.md` exists and is valid length.

Milestone 2 hardens setup feedback and compatibility behavior. Ensure atomic-mode missing-requirements messaging remains accurate (without turning planner policy into a hard prerequisite), and ensure `--help` text clearly describes how the new option works and where the file is stored.

Milestone 3 adds targeted tests and docs updates. Add CLI help and setup-flow tests covering the new option and update design docs that describe setup command surface so documentation stays aligned with behavior.

## Concrete Steps

All commands run from repository root:

    /Users/franz/Desktop/Tapsweets/Apps/CLI/automolt/automolt

Implementation sequence:

1. Add new setup CLI flag and parameter wiring.

   Edit `automolt/commands/automation/setup_command.py`:

   - Add `@click.option("--behavior-submolt-md", ...)` with `flag_value=""` semantics matching existing prompt flags.
   - Add `behavior_submolt_md` parameter to `setup(...)`.
   - Include `behavior_submolt_md` in atomic-mode detection and `_run_atomic_setup(...)` invocation.

2. Extend atomic prompt update flow.

   In `_run_atomic_setup(...)`:

   - Accept `behavior_submolt_md` argument.
   - When provided, call `_apply_atomic_prompt_update(..., prompt_name="behavior_submolt", option_value=behavior_submolt_md, ...)`.
   - Append status output line for `--behavior-submolt-md` consistent with existing color/status style.

3. Extend interactive prompt collection flow.

   In `setup(...)`:

   - After existing `filter` and `behavior` collection, collect `behavior_submolt` via `_collect_prompt_file(...)`.
   - Add `PROMPT_DESCRIPTIONS["behavior_submolt"]` text explaining cadence/policy guidance purpose and that it controls planner behavior.

4. Extend setup display and validation messaging.

   In `setup_command.py`:

   - Update `_display_success(...)` to show status for `BEHAVIOR_SUBMOLT.md`.
   - Align prompt-option help text with current flag semantics (default prompt-file path editing).
   - Keep `_collect_missing_setup_requirements(...)` and `_validate_prompt_files(...)` behavior aligned with current runtime contract: `filter` + `behavior` remain required, `behavior_submolt` is displayed and editable but not mandatory for setup completion.

5. Add/update tests.

   Add tests (new or existing CLI test module under `tests/`) to verify:

   - `automolt automation setup --help` includes `--behavior-submolt-md`.
   - Atomic mode accepts `--behavior-submolt-md` and writes `.agents/<handle>/BEHAVIOR_SUBMOLT.md`.
   - Success/status output includes `BEHAVIOR_SUBMOLT.md` state.
   - Existing behavior for required prompts (`FILTER.md`, `BEHAVIOR.md`) remains unchanged.

6. Update docs for setup surface.

   Update the setup-related section in `docs/design-docs/automation-system.md` (and `docs/design-docs/_index.md` only if needed for verification note wording) to include the new setup option and prompt artifact coverage.

Validation commands during and after implementation:

    uv run python -m unittest discover -s tests
    uv run ruff check .
    uv run python -m automolt.main automation setup --help

Manual validation commands:

    uv run python -m automolt.main automation setup --handle <handle> --behavior-submolt-md
    uv run python -m automolt.main automation setup --handle <handle>
    uv run python -m automolt.main automation reload --handle <handle>

Expected evidence examples:

    - Help output lists `--behavior-submolt-md` with flag semantics matching existing `--filter-md`/`--behavior-md` options.
    - Atomic setup opens/creates the target file and persists content to `.agents/<handle>/BEHAVIOR_SUBMOLT.md`.
    - Interactive setup offers a third prompt-collection step for submolt behavior policy.
    - Setup completion panel reports `BEHAVIOR_SUBMOLT.md` status alongside other prompt artifacts.

## Validation and Acceptance

Acceptance is met when all of the following are true:

- `automolt automation setup --help` documents a dedicated submolt behavior prompt option.
- In atomic mode, users can create/edit `BEHAVIOR_SUBMOLT.md` via a setup flag without affecting unrelated fields.
- In interactive mode, users are prompted to provide `BEHAVIOR_SUBMOLT.md` using the same editor/copy UX as other prompts.
- Setup output surfaces `BEHAVIOR_SUBMOLT.md` status clearly.
- Existing setup prerequisite semantics remain stable: `FILTER.md` and `BEHAVIOR.md` are still required for completion, while planner prompt policy remains stage-scoped.
- Existing runtime entry points (`automation tick`, `automation reload`) behave as before with no regression in command targeting or prompt validation boundaries.

## Idempotence and Recovery

All changes are additive and command-level. Re-running setup with the new flag should be idempotent: it overwrites only the selected prompt content and leaves unrelated setup fields unchanged.

If a user exits editor flow with insufficient content, setup should preserve existing behavior by reporting a clear validation warning and skipping the write.

If users accidentally create invalid planner policy content, recovery remains explicit through editing the same file and running `automolt automation reload --handle <handle>` to verify parse success.

## Artifacts and Notes

Representative file outcome:

    .agents/<handle>/BEHAVIOR_SUBMOLT.md

Representative help-line outcome:

    --behavior-submolt-md  Open or create submolt behavior prompt markdown in the default prompt file path.

Representative setup status panel snippet:

    BEHAVIOR_SUBMOLT.md: 124 characters

## Interfaces and Dependencies

Primary modules to edit:

- `automolt/commands/automation/setup_command.py` for option parsing, interactive/atomic UX, and success rendering.
- `automolt/persistence/prompt_store.py` should remain unchanged and be reused with prompt name `behavior_submolt`.
- `tests/` CLI test module(s) for command-surface and file-write coverage.
- `docs/design-docs/automation-system.md` for operator-facing setup behavior documentation.

No new third-party dependencies are required. Keep absolute imports and existing Click/Rich patterns consistent with current command modules.

## Revision Notes

- 2026-03-17 / Cascade: Created initial active ExecPlan to add `BEHAVIOR_SUBMOLT.md` support to `automation setup` in both interactive and atomic flows while preserving current runtime prerequisite contracts. Reason: users need first-class setup UX for planner policy prompt management without manual file-only workflows.
- 2026-03-17 / Cascade: Completed implementation, tests, and minimal documentation updates; recorded parser-semantics discovery and aligned help/docs wording to observed behavior. Reason: keep this plan self-contained and execution-accurate for future contributors.
