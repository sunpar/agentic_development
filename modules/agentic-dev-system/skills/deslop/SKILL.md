---
name: deslop
description: Detect and remove AI slop patterns from code, docs, PRs, and comments.
---

# Deslop

## Trigger
Use before PR creation or branch handoff.

## Inputs
- Diff, changed markdown, PR body, or task branch.

## Outputs
- Slop findings with file and line references.
- Suggested remediation actions.

## Procedure
1. Scan changed surface for concrete patterns:
   - redundant comments
   - needless abstractions
   - fake certainty
   - duplicated prose
   - vague helper names
   - apology/requested-verbosity language
2. Produce actionable recommendations only.
3. Remove slop behaviorlessly, preserving logic.

## Guardrails
- No behavior changes.
- Keep changes tied to touched files.

## Success criteria
- PR diff is cleaner, specific, and review-focused.

## Prefer Superpowers
- Use `test-driven-development` and `deslop` companions from request/review loops.

## Avoid scope creep
- Do not rewrite stable architecture for style.
