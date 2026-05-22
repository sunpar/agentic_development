---
name: slice-agent-review-loop
description: Use after PR creation when requesting Codex or Copilot review.
---

# slice-agent-review-loop

## Trigger

Use after PR creation when requesting Codex or Copilot review.

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

- references/codex-review-policy.md
- references/copilot-review-policy.md
- references/review-comment-resolution.md
