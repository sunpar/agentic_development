---
name: request-agent-review
description: Request and track Codex/Copilot review comments on open PRs.
---

# Request Agent Review

## Trigger
Use after PR exists and before merge.

## Inputs
- PR URL or branch.
- Focus areas.

## Outputs
- Review request summary and actionable item list.
- Optional generated fix prompt from `scripts/address_review_comments_prompt.py`.

## Procedure
1. Detect open PR for current branch.
2. Post review request comment tagging requested providers.
3. Poll for review comments and summarize actionable items.
4. If fixes are requested, generate an address-review prompt from the collected JSON:
   `python3 ~/.codex/agentic-dev-system/scripts/address_review_comments_prompt.py --input actionable-review-summary.json --output address-review-comments.md --json-output actionable-review-summary.normalized.json`
5. Hand the generated prompt to Codex/implementor for the fix pass.
6. Reply to addressed comments with evidence after fixes are verified.

## Guardrails
- Separate Codex vs Copilot comments.
- Never mark comments resolved unless fixed.
- The request/poll helper does not apply code changes itself.
- Address only in-scope must-fix and should-fix comments; clarify ambiguous feedback first.

## Success criteria
- PR has clear pending/closed action summary and a scoped fix prompt when follow-up changes are needed.

## Prefer Superpowers
- Use `requesting-code-review` and `receiving-code-review` when available.

## Avoid scope creep
- Do not address unrelated feedback in the same pass.
