# Design Docs Index

This index catalogs every markdown document in `docs/design-docs/`.

## Index Metadata

`_index.md`: Canonical catalog of all design docs in this folder.

## Core Architecture

`cli-architecture.md`: CLI command structure, handler responsibilities, and delegation boundaries.
`models-and-persistence.md`: Model responsibilities, persistence ownership, and runtime state directories.
`client-configuration.md`: `client.json` contract, prompt artifacts, and agent-targeting/session rules.
`session-targeting-design.md`: Design rationale for handle resolution order and mutation constraints.
`core-beliefs.md`: Long-lived architecture beliefs and agent-first operating principles.

## Development Workflow

`contributing-and-releases.md`: Source-of-truth location for contributor and release policy.

## Subsystems

`automation-system.md`: Full automation reference with command surface, runtime behavior, queue semantics, and LLM pipeline.
`automation-runtime-design.md`: Design-focused abstraction of heartbeat orchestration and scheduler ownership.
