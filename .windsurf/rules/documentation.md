---
description: Workflow for consolidating implementation directives (`*-IMPL.md` files) into living documentation md files
---

# Documentation Consolidation Rule

The following rule describes the workflow for consolidating implementation directives into living documentation files.

## Scope and Rules

- Implementation directives live under `/tasks` and typically end in `-IMPL.md`.
- NEVER delete implementation directives. Instead, archive them under `tasks/archive/` and rename them according to the following pattern: `{yyyy-MM-dd-HH-mm-ss}-{directive_file_name_without_extension}.md`
- Living documentation `*.md` files live under `/docs` and are named thematically, by subsystem, or by behavior.
- The target documentation must describe current behavior and architecture as verifyably implemented in the codebase, not implementation instructions.
- Each documentation file must have a YAML frontmatter
```
---
includes: ...
excludes: ...
related: ...
---
```

`includes:` describes what part(s) of the system this documentation file covers.
`excludes:` Optional. Clarifies what is out of scope for this documentation file. Only clarify if non-obvious from context.
`related:` Optional. Lists related documentation files that provide complementary information. Do not include `_INDEX.md` in `related`.

If boundaries are blurry with other documentation files, ensure all affected files sufficiently clarify their boundaries and coverage via `includes` and `excludes` frontmatter and reference each other.

Do not follow circular references. Do not load files into context that you have already loaded into context.

- `docs/_INDEX.md` is the main index file for all documentation files. It must list all documentation files, thematically grouped, and provide a compact description of what it covers, in under 300 characters, for each file in the following format: `- FILE-NAME.md: description`. The index does not have YAML frontmatter.

- Upon creating a new documentation file, update `docs/_INDEX.md` to reference the new file.

## Inputs

1. One or more source implementation directive files (from `/tasks`).
2. Optionally one or more target documentation files (in `/docs`), or if none specified and no ideal match exists under `/docs`, a new documentation `.md` file will be created with a descriptive name in capital letters, and hyphens will be used to separate words.
3. Optionally: Relevant source code modules needed for fact verification. If none are provided, you must exhaustively search the codebase to identify all relevant modules in order to verify the documentation claims and facts.

## Non-Negotiable Quality Gates

1. Every directive item must be explicitly marked as:
   - `- [x]` captured in the documentation, or
   - `- [~]` intentionally not carried forward (with reason).
2. Every newly added fact in documentation must be diligently verified against the codebase.
3. Any discrepancy must be recorded in a `_TASK-REPORT.md` file under `/tasks`.
4. Verify directive files step-by-step, one-by-one, before moving them to `/tasks/completed`.
5. Finished directive files must be moved to `/tasks/completed`, and renamed according to the following pattern: `{yyyy-MM-dd-HH-mm-ss}-{directive_file_name_without_extension}.md`, where the timestamp is the current date and time.

## Execution Workflow

### Step 1) Discover and baseline

- Read all provided directive files and provided target docs files. If no docs files were provided, try to discover the most relevant docs file(s) via `docs/_INDEX.md`. If uncertain about relevance, read the frontmatter of the referenced file. If no relevant docs file exists, create a new one per topic or subsystem you have been instructed to work on (as per the implementation directive(s)). Each significant aspect of the codebase has its own focused documentation. If there may be overlap, do not repeat the same information across multiple files. Instead, provide the documentation in one file and make sure to reference the relevant documentation file(s) from each other.
- Identify missing concepts in target docs.
- Identify all code files required to verify claims and facts.

### Step 2) Consolidate into living docs

- Merge documentation content from the implementation directives into the target docs file under `/docs`.
- Rewrite into factual system documentation (architecture, behavior, constraints, operations, etc.).
- Remove directive/process language (no "must implement", no TODO-style implementation plans).

### Step 3) Build capture checklist

- Create/update a capture tracking file in `/tasks`.
- Add a section for each directive file and list each atomic item from the directive.
- Mark each item as captured or intentionally not carried forward.
- Maintain an explicit completion workflow checklist for the source directives.

### Step 4) Self-audit and corrections

- Re-read updated docs and capture checklist.
- Correct any omissions, overstatements, or stale wording.
- Ensure terminology, claims and facts match current code, by analyzing the code base step-by-step.

### Step 5) Code verification of newly added claims

- Verify all newly added facts against source code.
- Create/update `/tasks/<TARGET_DOC_STEM>-IMPL.md` verification report containing:
  - scope,
  - files checked,
  - verified claims,
  - discrepancies (or explicit "none"),
  - any follow-up required.

### Step 6) Controlled archiving (one-by-one)

For each verified directive file:

1. Confirm all its items are marked captured/not-carried in checklist.
2. Confirm relevant claims are verified against code.
3. Archive (move) exactly one input implementation directive file under `tasks/archive/` and rename it according to the following pattern: `{yyyy-MM-dd-HH-mm-ss}-{directive_file_name_without_extension}.md`
4. Update archiving checklist state.
5. Repeat for next file.

### Step 7) Final integrity pass

- Verify the input implementation directives have been archived.
- Ensure target docs + task reports reflect final truth.

## Deliverable Checklist

- [ ] Target docs updated in `/docs`
- [ ] Capture checklist updated in `/tasks`
- [ ] Verification report created/updated in `/tasks`
- [ ] Directive files archived one-by-one only after verification
- [ ] Stale references cleaned or explicitly documented
