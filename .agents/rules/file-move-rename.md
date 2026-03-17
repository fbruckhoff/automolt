---
trigger: model_decision
description: File move and rename operations
---
Use this rule whenever a task requires moving and/or renaming files without changing file contents.

## Core policy

- Do not use `apply_patch` for pure file relocations or renames.
- Use direct filesystem move commands (`mv`) with explicit source and destination paths.
- Reserve `apply_patch` for in-file content edits.

## Standard procedure

1. Confirm the source file exists and the destination directory exists (or create it if the task requires).
2. Execute a direct `mv` command for the relocation/rename.
3. Verify the source path no longer exists.
4. Verify the destination path now exists.
5. Report the exact moved path(s) in the handoff.

## Error handling

- If a patch-tool schema or adapter error appears during a rename attempt (for example missing replacement chunk fields), treat it as tooling incompatibility for move semantics.
- Pivot immediately to `mv` instead of retrying `apply_patch` move-only hunks.
- If the destination file already exists and overwrite behavior is not explicitly requested, stop and ask for user confirmation before proceeding.

## Example

```bash
mv docs/exec-plans/active/submolt-create-and-post-support.md \
   docs/exec-plans/completed/2026-03-16-18-03-39-submolt-create-and-post-support.md
```
