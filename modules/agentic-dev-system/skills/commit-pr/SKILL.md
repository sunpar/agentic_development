---
name: commit-pr
description: Stage changes, commit, push, and create/update PR with review-ready hygiene.
---

# Commit PR

## Trigger
Use when implementation branch is ready for publish.

## Inputs
- Staged diff and current branch.
- Task completion summary.

## Outputs
- Commit with concise message.
- Pushed branch and PR URL.

## Procedure
1. Validate branch not protected unless forced.
2. Show and confirm staged set.
3. Stage all only if `--stage-all`.
4. Commit with concise generated message.
5. Push and create/update PR.

## Guardrails
- Refuse on protected branch unless explicit override.
- Do not commit if gh unavailable or unauthenticated.

## Success criteria
- Branch is pushed and PR exists with review-ready body.

## Prefer Superpowers
- Use `receiving-code-review` and `requesting-code-review` for review lifecycle.

## Avoid scope creep
- No unrelated file changes after commit.
