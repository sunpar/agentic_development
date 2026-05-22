---
name: slice-ci-debug-and-merge
description: Use when a slice PR exists and CI must be inspected or repaired before an optional explicit merge.
---

# slice-ci-debug-and-merge

## Trigger

Use when a slice PR exists and CI must be inspected or repaired before an optional explicit merge.

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
- Merge is opt-in: do not merge unless the invocation explicitly provides `--allow-merge`.
- Explicit opt-out wins: if the invocation provides `--no-merge` or `--pr-only`, leave the PR unmerged even when merge authority is otherwise available.
- Treat `ci_debug_and_merge.py` as a CI check helper plus optional manual merge command wrapper, not as a complete merge gate. Before any merge, separately verify target PR, non-draft state, mergeability, required checks, review policy, unresolved review threads, unresolved must-fix comments, local cleanliness, and slice scope.
- Record evidence, assumptions, unknowns, and verification commands.
- Do not perform mutating actions unless this skill's role explicitly requires mutation.

## Outputs

Write outputs under `docs/agentic-system/` in the target repository unless the user requests another location. Follow the schemas in `~/.codex/codebase-review-factory/schemas/`.

## References

- references/ci-debugging-policy.md
- references/safe-merge-policy.md
