# Agentic Development Factory AGENTS

## 1) Working agreements
- Be exact about scope. Do not broaden tasks beyond what the user or parent task explicitly asks.
- Favor clear, executable evidence over assertions.
- Prefer additive edits and avoid destructive changes unless explicitly requested.

## 2) Use Superpowers where available
- Use Superpowers workflows for planning/review/review loops, branch discipline, and debugging:
  - brainstorming, writing-plans, using-git-worktrees, test-driven-development, dispatching-parallel-agents, subagent-driven-development, requesting-code-review, receiving-code-review, finishing-a-development-branch, verification-before-completion.
- If a Superpowers skill path is missing, document the gap and continue with a fallback.

## 3) TDD expectations
- For implementation tasks, write tests first, then code, then refactor.
- If behavior is unclear, write characterization tests first.
- Do not mark work complete without passing validation evidence.

## 4) Git worktree policy
- Implement code in isolated git worktrees using `git worktree`.
- Keep each task isolated to one branch + one worktree.
- Never implement directly on protected branches unless explicitly forced.

## 5) Task scope discipline
- Keep each task behaviorally single-purpose and PR-sized.
- Every task must include read/write sets and explicit dependencies.
- Stop when a missing product decision blocks safe implementation.

## 6) Parallel wave discipline
- Execute same-wave tasks only when dependency-safe and write-set-safe.
- Merge/compare waves strictly in order: all of wave N before wave N+1.
- Escalate conflicts instead of broadening scope.

## 7) Review discipline
- Review tasks against their exact spec before merging.
- Classify findings with severity (P0/P1/P2/P3).
- Keep PRs reviewable: short diff, clear rationale, explicit tests.

## 8) Deslop/style discipline
- Remove obvious AI slop patterns, duplicated prose, needless abstractions, vague generic comments.
- Do not change behavior unless the task asks for behavior changes.
- Keep wording precise and specific.

## 9) Commit/PR discipline
- Keep commits focused and tiny.
- Include concise summaries and explicit test evidence.
- Never commit or push staged protected-branch work unless explicitly forced.

## 10) Safety and non-destructive behavior
- Do not run destructive commands on project files without authorization.
- Never commit secrets, credentials, tokens, or private material.
- Avoid destructive git operations.
- Back up existing personal Codex files before overwrite as required.

## Additional execution constraints
- Before coding in a repo, inspect repo structure and local instructions (`AGENTS.md`-style files, workflow docs).
- Use TDD for implementation tasks unless test-infeasible due to scope type.
- Do not claim success without observed validation output.
- Keep generated prose concise and reviewer-relevant.
