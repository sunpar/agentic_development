# Sample Prompts

These prompts use the unified Agentic Development System vocabulary. See `EXAMPLES.md` for full command sequences.

## Initial Build

1. "Use repo-context-map to map this repo before planning. Include architecture, entry points, tests, CI, runtime commands, and risks."
2. "Use acceptance-test-writer for this feature request. Produce acceptance criteria that are specific enough for TDD."
3. "Use task-generator for this feature spec and repo context. Emit epics, PR-sized tasks, waves, and plan.json under docs/agentic-system/build/."
4. "Use task-scope-validator and wave-validator on docs/agentic-system/build/plan.json."
5. "Use task-implementor for TASK-ID. Work in the generated worktree, follow TDD, and include validation evidence."
6. "Use task-reviewer to review TASK-ID against its task spec, diff, tests, and completion note."
7. "Use integration-merge-manager for wave N. Plan integration by default; merge only if explicit merge approval was given."

## Review And Refactor

1. "Use codebase-deep-analyzer to analyze this repository deeply. Build inventory, architecture map, docs map, test/CI map, and risk notes under docs/agentic-system/."
2. "Use feature-model-builder to create a high-level model of the major features. Include evidence, confidence, docs, code paths, tests, and risks."
3. "Use feature-slice-generator to break the feature model into bounded review/refactor slices with explicit read sets, write sets, invariants, non-goals, verification commands, and branch names."
4. "Use reviewable-slice-validator and slice-wave-planner on docs/agentic-system/review/slice-plan.json. Same-wave slices must be parallel-safe."
5. "Use slice-review-workflow and slice-refactor-workflow for SLICE-ID. Apply only valid behavior-preserving findings and verify."

## PR, Review, CI, And Release

1. "Use deslop on the current branch before PR."
2. "Use commit-pr to commit, push, and create or update a PR with concise test evidence."
3. "Use request-agent-review to ask @codex to review this PR, focusing on correctness, tests, API compatibility, and scope."
4. "Use the actionable review summary to fix only in-scope must-fix and should-fix comments. Commit and push follow-up changes, then reply with evidence."
5. "Use slice-ci-debug-and-merge for this PR with --no-merge. Debug failing CI minimally, but leave the PR unmerged."
6. "Use release-notes-and-migration after integration to summarize completed changes and migration requirements."
