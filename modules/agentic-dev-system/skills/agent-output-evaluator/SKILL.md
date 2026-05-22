---
name: agent-output-evaluator
description: Evaluate plans/tasks/outputs for schema and quality violations.
---

# Agent Output Evaluator

## Trigger
Use for quality audits of generated outputs.

## Inputs
- plan/task files, skill outputs, fixtures.

## Outputs
- Rubric-based score and specific violations.

## Procedure
1. Validate required task fields.
2. Validate wave safety and scope constraints.
3. Detect vague tasks and oversized PR assumptions.
4. Provide fix recommendations.

## Guardrails
- Keep scoring reproducible and artifact-based.

## Success criteria
- Every failure includes exact path + reason.
