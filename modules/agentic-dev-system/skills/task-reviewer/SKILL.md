---
name: task-reviewer
description: Review one task implementation against its spec with severity and pass/fail outcome.
---

# Task Reviewer

## Trigger
Use after implementation and test evidence are available.

## Inputs
- Task spec (`plan.json` or task file).
- Branch diff and completion note.
- Tests list and verification output.

## Outputs
- Review summary with P0-P3 severity findings and explicit recommendation.

## Procedure
1. Validate file scope against task read/write sets.
2. Verify tests requested in task are present and run.
3. Check acceptance criteria against diff.
4. Emit severity-ranked findings and required follow-up.

## Guardrails
- Read-only review only.
- Use exact evidence with file/line references.

## Success criteria
- Final recommendation clearly states Pass / Fail / Rework.

## Prefer Superpowers
- Use `requesting-code-review` and `receiving-code-review` for handoff workflow.

## Avoid scope creep
- Do not approve partial behavior coverage.

## Concrete artifact names
- `<task>-review.md`
