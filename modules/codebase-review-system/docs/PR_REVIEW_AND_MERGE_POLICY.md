# PR Review And Merge Policy

PRs must be scoped to one slice. Request `@codex review` and Copilot review when available. Poll comments, classify actionable feedback, fix in scope, reply with evidence, and never mark comments resolved unless addressed or explicitly explained.

Merging is opt-in by default. A complete merge gate requires explicit user merge authorization, a verified target PR, non-draft status, mergeability, green required checks, satisfied review policy, no unresolved review threads, no unresolved must-fix comments, clean local state, and the intended merge method. An explicit `--no-merge` or `--pr-only` command always wins and leaves the PR ready for human merge.

Current helper status: `ci_debug_and_merge.py` is a CI check helper plus optional manual `gh pr merge` command wrapper. It is not a complete merge state machine and does not itself verify draft status, review threads, mergeability, must-fix comment closure, or slice scope cleanliness. Use it only when those gates have been checked separately, or prefer PR-only mode.
