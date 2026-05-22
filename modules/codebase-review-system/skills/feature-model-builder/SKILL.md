---
name: feature-model-builder
description: Use after codebase-deep-analyzer or when the user asks for a high-level model of all repository features.
---

# feature-model-builder

## Trigger

Use after codebase-deep-analyzer or when the user asks for a high-level model of all repository features.

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

- references/feature-model-contract.md
- references/feature-taxonomy.md
