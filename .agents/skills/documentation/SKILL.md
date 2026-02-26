---
name: documentation
description: Consolidate implementation directives into living documentation with strict capture tracking, code verification, discrepancy reporting, and one-by-one directive deletion. Use whenever prompts involve `-IMPL.md` specs/directives and documentation updates.
---

# Documentation Consolidation Skill

Use this skill whenever the task includes one or more implementation directive/specification markdown files (typically `*-IMPL.md`) and asks to consolidate them into living docs.

If implementation work was requested from a `*-IMPL.md` directive, run this workflow automatically after implementation is complete.

Primary rule to apply:

- `.agents/rules/documentation.md`

## Trigger Heuristics

Apply this skill when the user request includes any of:

- "consolidate" + implementation directive/spec
- source files ending in `-IMPL.md`
- requests to verify capture completeness
- requests to delete directive files only after verification
- requests to create discrepancy reports under `/tasks`

## Required Workflow

1. Read all source directives and target docs.
2. Consolidate into living documentation only (no implementation instructions).
3. Build/update a capture checklist in `/tasks`, item-by-item.
4. Verify new facts against code and write/update `/tasks/<TARGET_DOC_STEM>-IMPL.md`.
5. Delete directives one-by-one only after full capture + verification.
6. Run final integrity checks (deleted files gone, stale references resolved, docs consistent).

Execution timing:

- If a prompt asks to implement a `*-IMPL.md` directive, apply this workflow at the end of that implementation cycle.
- If a prompt directly asks for consolidation/verification, apply this workflow immediately.

## Hard Constraints

- Treat `/tasks` as directive/report location.
- Treat `/docs` as living documentation location.
- Never delete directive files before complete verification.
- Record every discrepancy explicitly.
- If no discrepancy exists, state this explicitly in the verification report.

## Output Expectations

- Updated documentation file(s) in `/docs`.
- Updated capture checklist in `/tasks`.
- Verification/discrepancy report in `/tasks`.
- Controlled one-by-one deletion audit trail.
