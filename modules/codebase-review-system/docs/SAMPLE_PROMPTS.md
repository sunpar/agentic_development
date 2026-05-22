# Codebase Intelligence Module Sample Prompts

Use these prompts as part of the unified Agentic Development System flow. The full coordinated examples are in `~/.codex/agentic-dev-system/docs/EXAMPLES.md`.

1. "Use codebase-deep-analyzer to analyze this repository deeply. Build inventory, architecture map, docs map, test/CI map, and risk notes under docs/agentic-system/. Do not edit code."
2. "Use feature-model-builder to create a high-level model of all major features in this repository. Include evidence, confidence, docs, code paths, tests, and risks."
3. "Use feature-slice-generator to break the feature model into small reviewable/refactorable slices. Include read sets, allowed edit scope, non-goals, invariants, verification commands, branch names, and review focus."
4. "Use reviewable-slice-validator and slice-wave-planner on docs/agentic-system/review/slice-plan.json. Same-wave slices must be dependency-safe and write-set-safe."
5. "Use slice-review-workflow and slice-refactor-workflow for SLICE-ID. Review only the listed scope, apply only valid behavior-preserving findings, verify, and write a completion note."
6. "Use slice-pr-lifecycle for SLICE-ID. Commit, push, and create or update a PR with a terse reviewer-useful body. Do not merge."
7. "Use slice-agent-review-loop for this PR. Request Codex review for correctness, tests, API compatibility, and slice scope. Poll for review comments and produce actionable-review-summary.json."
8. "Use slice-ci-debug-and-merge for this PR with --no-merge. Debug failing CI minimally and leave the PR unmerged."
