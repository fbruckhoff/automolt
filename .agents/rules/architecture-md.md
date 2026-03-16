---
description: Style and scope constraints when editing ARCHITECTURE.md
glob: "ARCHITECTURE.md"
---

Apply this rule only when editing `ARCHITECTURE.md`.

## Purpose and scope

- `ARCHITECTURE.md` describes high-level architecture only.
- Keep it short and durable: prefer statements that are unlikely to change frequently.
- This file is intended for recurring contributors and AI coding agents, so prioritize scanability and stable guidance.

## Required structure

1. Start with a bird's-eye overview of the problem the project solves.
2. Add a codemap of coarse-grained modules and relationships.
3. Explicitly list architectural invariants.
4. Add a separate section for cross-cutting concerns.

## Codemap requirements

- Answer both:
  - "Where is the thing that does X?"
  - "What does the thing that I am looking at do?"
- Name important files, modules, and types.
- Do not directly link to files or symbols; links go stale. Prefer discoverable symbol names for IDE search.
- Keep detail level coarse-grained. A codemap is a map of a country, not an atlas of states.
- If codemap groupings feel awkward, treat that as architecture feedback and improve structure over time.

## Boundaries and invariants

- Call out boundaries between layers/systems explicitly.
- Call out invariants explicitly, including invariants expressed as absence (for example, dependency directions that are forbidden).
- Emphasize constraints that shape implementation choices.

## Agent-facing context

- The root-level `ARCHITECTURE.md` (next to `README.md`) is part of the structured knowledge base for coding agents.
- Keep wording factual, compact, and implementation-aligned.

## Reference style

Use this style as a model, adapted to project complexity:

- https://raw.githubusercontent.com/rust-lang/rust-analyzer/d7c99931d05e3723d878bea5dc26766791fa4e69/docs/dev/architecture.md
