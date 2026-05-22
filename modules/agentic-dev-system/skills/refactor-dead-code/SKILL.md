---
name: refactor-dead-code
description: Remove unused or unreachable code with safe reference checks.
---

# Refactor Dead Code

## Trigger
Use when code appears unused and safe to delete.

## Inputs
- Static search results or lints indicating dead symbols.

## Outputs
- Deletions of obsolete symbols and updated references.

## Procedure
1. Confirm usage across repository.
2. Remove dead symbols and imports.
3. Run tests and targeted checks.

## Guardrails
- Do not remove extension points without explicit confirmation.
- Keep public API surfaces unless user approves.

## Success criteria
- No remaining references and tests pass.

## Prefer Superpowers
- Use `test-driven-development` for added safety checks.

## Avoid scope creep
- Keep deletion scope tied to explicit task write set.
