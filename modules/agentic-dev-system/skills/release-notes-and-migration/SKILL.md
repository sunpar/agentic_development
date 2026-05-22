---
name: release-notes-and-migration
description: Generate release and migration notes after completion.
---

# Release Notes and Migration

## Trigger
Use after milestone or epic completion.

## Inputs
- Completed task list and merge summaries.

## Outputs
- Release notes, migration instructions, rollback plan, unresolved risks.

## Procedure
1. Aggregate changed behavior.
2. Produce user-facing and operator-facing notes.
3. Add rollback and compatibility notes.

## Guardrails
- Do not hide unresolved risks.

## Success criteria
- Notes are concise, test-evidenced, and include rollout order.
