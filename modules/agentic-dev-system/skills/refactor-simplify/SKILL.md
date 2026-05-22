---
name: refactor-simplify
description: Perform behavior-preserving simplification and cleanup after green tests.
---

# Refactor Simplify

## Trigger
Use when requested refactor is readability/DRY/removal of repeated abstraction.

## Inputs
- Task/task set and green baseline test evidence.

## Outputs
- Refactored code with no behavior regression.
- Updated/added characterization tests if necessary.

## Procedure
1. Confirm baseline is green.
2. Identify duplicate abstractions, verbose wrappers, and repeated boilerplate.
3. Refactor only local scope.
4. Keep public behavior unchanged.

## Guardrails
- No behavior change unless explicitly requested.
- Preserve API/shape.

## Success criteria
- Equivalent behavior verified by rerun of baseline suite.

## Prefer Superpowers
- Use `refactor` patterns only and ask `writing-plans` only when scope is large.

## Avoid scope creep
- Do not introduce new architecture in simplification pass.
