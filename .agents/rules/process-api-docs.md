---
trigger: manual
---

Your task is to process an input source API documentation file step-by-step, section-by-section, item by item, atomically.

Your task is to process an input source API documentation file step-by-step, section-by-section, item by item, atomically, and possibly by applying specified filter criteria. Your task is to transfer targeted compacted API documentation from the source API documentation to the reference file(s) of an AI Skill directory.

## Inputs

The user must provide two inputs alongside this rule:

1. **Source API documentation** — a file path or URL containing the API documentation to process.
2. **Target `SKILL.md`** — the skill file whose `references/` directory will receive the integrated content.

If either input is missing or ambiguous, ask the user to clarify before proceeding.

## Definitions

An atomic item is: a symbol, function, method, parameter, argument, or other artifact that is listed along with its own description.

An item is NOT considered atomic if it is clearly listed and described in a hierarchy that falls under some other item. For example: a parameter that belongs to a function. In this case, the function is the atomic item of interest, not the specific parameter.

## Setup

Create a working copy of the source API documentation under `tasks/{NAME-OF-SOURCE}-PROCESSING.md`, relative to the target skill's directory. If the source is a URL, extract the entire content into this file before beginning any processing. For multi-page or paginated sources, ensure all pages are captured.

All paths below are relative to the target skill's directory (the directory containing the target `SKILL.md`).

## Processing Loop

For each atomic item in the working copy:

- [ ] Review the target `SKILL.md` to determine the relevant reference file. Create a new reference file under `references/` if needed, and ensure the target `SKILL.md` references it along with a brief description such that an AI coding agent can decide based on context if this reference is relevant to its task or problem.

- [ ] Diligently integrate the atomic item into the identified reference file and ensure correctness and completeness.

- [ ] Cross-verify your integration of the atomic item with the entirety of the reference file and ensure there is no unwanted duplication. If there is unwanted duplication, aim to clean it up without dropping information.

- [ ] Delete the processed atomic item from the `tasks/{NAME-OF-SOURCE}-PROCESSING.md` working copy.

Iteratively perform this process step-by-step, respecting the described sequence of steps, until `tasks/{NAME-OF-SOURCE}-PROCESSING.md` has been fully processed.

## Resumption

If processing is interrupted (e.g., context limits, session end), resume from the current state of the `tasks/{NAME-OF-SOURCE}-PROCESSING.md` working copy. Items already deleted have been processed — do not re-process them. Begin with the first remaining atomic item.

## Strict Rules

- You are not allowed to take any shortcuts. Perform this diligently and carefully, step-by-step, as prescribed. Taking shortcuts will cause your work to be useless and irrelevant.
- Do not batch or combine multiple atomic items into one step.
- Do not skip the cross-verification step.
