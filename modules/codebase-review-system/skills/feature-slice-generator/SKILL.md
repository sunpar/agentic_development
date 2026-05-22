---
name: feature-slice-generator
description: Use when there is a feature model and the user wants reviewable/refactorable slices.
---

# feature-slice-generator

## Trigger

Use when there is a feature model and the user wants reviewable/refactorable slices.

## Inputs

- target repository path or current repository
- optional focus areas
- optional exclusions
- relevant factory artifacts when available

## Procedure

- Read repository instructions such as AGENTS.md first.
- Prefer Superpowers workflows when installed and relevant.
- Prefer OpenAI curated GitHub skills for PR comments and CI when available.
- Stay within the requested scope.
- Record evidence, assumptions, unknowns, and verification commands.
- Do not perform mutating actions unless this skill's role explicitly requires mutation.

## Outputs

Write outputs under `docs/agentic-system/` in the target repository unless the user requests another location. Follow the schemas in `~/.codex/codebase-review-factory/schemas/`.

## References

- references/slice-contract.md
- references/slice-sizing-rules.md
- references/slice-template.md
