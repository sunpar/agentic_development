# PR Review And Merge Policy

PRs must be scoped to one slice. Request `@codex review` and Copilot review when available. Poll comments, classify actionable feedback, fix in scope, reply with evidence, and never mark comments resolved unless addressed or explicitly explained.

Merging is opt-in by default. A complete merge gate requires explicit user merge authorization, a verified target PR, non-draft status, mergeability, green required checks, satisfied review policy, no unresolved review threads, no unresolved must-fix comments, clean local state, and the intended merge method. An explicit `--no-merge` or `--pr-only` command always wins and leaves the PR ready for human merge.

Current helper status: `ci_debug_and_merge.py` is a CI check helper only. It no longer runs `gh pr merge`; merge execution belongs to `merge_gate.py` or the wave orchestrator, which pass the head-SHA and review gates explicitly.
