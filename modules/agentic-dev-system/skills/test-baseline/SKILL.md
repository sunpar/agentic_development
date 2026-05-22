---
name: test-baseline
description: Capture pre-implementation test status and environment assumptions.
---

# Test Baseline

## Trigger
Use before implementation starts in a new task.

## Inputs
- Repository root and plan/task context.

## Outputs
- Baseline record of failing tests, command outputs, environment assumptions.

## Procedure
1. Run known test commands.
2. Record known failures and runtime constraints.
3. Save baseline as artifact next to task notes.

## Guardrails
- Do not modify code during baseline.

## Success criteria
- Baseline explicitly lists command and failure list.
