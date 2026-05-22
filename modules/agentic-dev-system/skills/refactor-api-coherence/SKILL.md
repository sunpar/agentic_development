---
name: refactor-api-coherence
description: Improve API, route, schema, event, CLI, and interface coherence.
---

# Refactor API Coherence

## Trigger
Use for naming, versioning, route/schema consistency tasks.

## Inputs
- API contracts, schema versions, and integration touch points.

## Outputs
- Coherent API/CLI contracts and migration notes.

## Procedure
1. Map current public contract and dependencies.
2. Propose minimal coherence edits.
3. Validate compatibility or migration notes.
4. Update docs and tests.

## Guardrails
- Do not break existing clients unless explicitly scoped.
- Preserve backward compatibility where possible.

## Success criteria
- Contract checks and compatibility notes are explicit.

## Prefer Superpowers
- Use `api-contract-review` companion workflows.

## Avoid scope creep
- Avoid broad refactors outside stated API surfaces.
