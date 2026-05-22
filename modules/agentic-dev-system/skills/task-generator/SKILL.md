---
name: task-generator
description: Convert feature context into epics, tasks, waves, and deterministic task artifacts.
---

# Task Generator

## Trigger
Use when a feature spec needs a PR-sized plan with waves.

## Inputs
- Feature description and source docs.
- Optional repo context from `repo-context-map`.
- Validation rules from wave/task validators.

## Outputs
- `docs/agent-plans/<feature>/plan.md`
- `docs/agent-plans/<feature>/plan.json`
- `docs/agent-plans/<feature>/tasks.csv`
- `docs/agent-plans/<feature>/tasks/<TASK-ID>.md`

## Procedure
1. Parse feature and determine epics.
2. Create tasks with required fields.
3. Assign conservative wave numbers and dependency edges.
4. Produce `plan.json` including `feature`, `source_documents`, `assumptions`, `open_questions`, `epics`, `tasks`, `waves`.
5. Emit task markdown files with exact objective and acceptance criteria.
6. Export `tasks.csv`.

## Required task schema
Each task includes: `id`, `epic_id`, `wave`, `title`, `branch`, `objective`, `non_goals`, `context_to_load`, `read_set`, `write_set`, `dependencies`, `parallel_conflicts`, `implementation_steps`, `tests_to_write_first`, `verification_commands`, `acceptance_criteria`, `review_focus`, `rollback_notes`.

## Guardrails
- Reject unrelated behavior.
- Keep tasks PR-sized and independently reviewable.
- Enforce same-wave dependency and write-set safety.

## Success criteria
- Tasks are concrete and actionable with explicit read/write sets and post-wave verification.

## Prefer Superpowers
- Use `writing-plans`, `writing-skills`, and `planning` style workflows from Superpowers for decomposition.

## Avoid scope creep
- Include implementation guidance, but do not prescribe exact code unless required. Give enough detail for a PR-sized implementor to proceed without re-planning.
- Do not assign changes outside the requested feature.
