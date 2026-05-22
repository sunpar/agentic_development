# Agentic Development System Examples

These examples show the single coordinated flow. Historical compatibility paths are still supported, but new runs should prefer an explicit project artifact directory such as `docs/agentic-system`.

## Validate The Local Install

```bash
python3 -B -m unittest discover ~/.codex/agentic-dev-system/tests
python3 -B -m unittest discover ~/.codex/codebase-review-factory/tests
python3 -B ~/.codex/agentic-dev-system/scripts/sync_skills.py --check
python3 ~/.codex/codebase-review-factory/scripts/sync_skills.py --dry-run
```

## Sync Skill Discovery

```bash
python3 ~/.codex/agentic-dev-system/scripts/sync_skills.py
python3 ~/.codex/codebase-review-factory/scripts/sync_skills.py
```

This keeps both compatibility skill collections discoverable:

```text
~/.agents/skills/agentic-dev-system
~/.agents/skills/codebase-review-factory
```

## Initial Feature Build Flow

Use this when the user asks for new product behavior, a new feature, or a larger implementation wave.

1. Map the target repo:

```text
Use repo-context-map to map this repository before planning. Include architecture, entry points, tests, CI, runtime commands, and risk notes.
```

2. Generate acceptance criteria if the requirements are thin:

```text
Use acceptance-test-writer for this feature request. Produce acceptance criteria that are specific enough for TDD.
```

3. Generate PR-sized tasks:

```text
Use task-generator for this feature spec and the repo context map. Emit epics, tasks, waves, task markdown files, and plan.json under docs/agentic-system/build/.
```

4. Validate task plan and waves:

```bash
python3 ~/.codex/agentic-dev-system/scripts/validate_plan.py docs/agentic-system/build/plan.json
```

```text
Use task-scope-validator and wave-validator on docs/agentic-system/build/plan.json. Confirm every task is PR-sized, independently testable, and dependency-safe.
```

5. Create a task worktree:

```bash
python3 ~/.codex/agentic-dev-system/scripts/create_task_worktree.py --plan docs/agentic-system/build/plan.json --task-id TASK-ID
```

6. Implement one task:

```text
Use task-implementor for TASK-ID from docs/agentic-system/build/plan.json. Follow TDD, use the generated worktree, write a completion note, and include validation evidence.
```

7. Review one task:

```text
Use task-reviewer to review TASK-ID against the task spec, diff, tests, and completion note. Classify findings as P0, P1, P2, or P3.
```

8. Prepare a PR:

```text
Use deslop on the current branch, then use commit-pr to commit, push, and create or update the PR with concise test evidence.
```

9. Request agent review:

```text
Use request-agent-review to ask @codex to review this PR, focusing on correctness, tests, API compatibility, and scope.
```

## Codebase Intelligence And Slice Flow

Use this after an initial build, for a mature repo, or when the user asks for targeted review/refactor work.

1. Create repo inventory:

```bash
python3 ~/.codex/codebase-review-factory/scripts/detect_repo_inventory.py --output docs/agentic-system/repo-inventory.json
```

2. Build a feature model skeleton:

```bash
python3 ~/.codex/codebase-review-factory/scripts/build_feature_model.py docs/agentic-system/repo-inventory.json --output docs/agentic-system/feature-model.json
python3 ~/.codex/codebase-review-factory/scripts/validate_feature_model.py docs/agentic-system/feature-model.json
```

3. Refine the feature model with Codex:

```text
Use codebase-deep-analyzer and feature-model-builder to refine docs/agentic-system/feature-model.json with evidence from docs, code paths, tests, entry points, risks, and unknowns.
```

4. Generate reviewable/refactorable slices:

```bash
python3 ~/.codex/codebase-review-factory/scripts/generate_slice_plan.py docs/agentic-system/feature-model.json --output-dir docs/agentic-system/review
python3 ~/.codex/codebase-review-factory/scripts/validate_slice_plan.py docs/agentic-system/review/slice-plan.json
python3 ~/.codex/codebase-review-factory/scripts/emit_slices_csv.py docs/agentic-system/review/slice-plan.json --output docs/agentic-system/review/slices.csv
```

5. Plan slice waves conservatively:

```text
Use reviewable-slice-validator and slice-wave-planner on docs/agentic-system/review/slice-plan.json. Same-wave slices must be read/write-set safe.
```

6. Dry-run one slice:

```bash
python3 ~/.codex/codebase-review-factory/scripts/run_slice_with_codex.py docs/agentic-system/review/slice-plan.json SLICE-001 --dry-run
```

7. Run one slice with Codex:

```text
Use slice-review-workflow and slice-refactor-workflow for SLICE-001. Read the slice spec, review only the listed scope, apply only valid behavior-preserving findings, verify, and write a completion note.
```

## Wave Orchestration

Use `--dry-run` to inspect wave order and Codex arguments before execution:

```bash
python3 ~/.codex/codebase-review-factory/scripts/orchestrate_slice_waves.py docs/agentic-system/review/slice-plan.json docs/agentic-system/review/waves.json --dry-run --max-parallel 2 --no-merge
```

Run validated waves with external run state and no merge:

```bash
python3 ~/.codex/codebase-review-factory/scripts/orchestrate_slice_waves.py docs/agentic-system/review/slice-plan.json docs/agentic-system/review/slice-plan.json --setup-command 'make install' --max-parallel 999 --allow-pr --allow-review-request --no-merge
```

Run with explicit opt-in merge gates:

```bash
python3 ~/.codex/codebase-review-factory/scripts/orchestrate_slice_waves.py docs/agentic-system/review/slice-plan.json docs/agentic-system/review/slice-plan.json --setup-command 'make install' --max-parallel 999 --allow-pr --allow-review-request --allow-merge --merge-method squash
```

Use `--setup-command` for repo-specific dependency setup that each slice worktree needs before Codex and verification. The flag is repeatable.

## PR Review Comment Follow-Up

After comments are collected into `actionable-review-summary.json`:

```bash
python3 ~/.codex/agentic-dev-system/scripts/address_review_comments_prompt.py --input actionable-review-summary.json --output address-review-comments.md --json-output actionable-review-summary.normalized.json
```

Then run:

```text
Use address-review-comments.md to fix only in-scope must-fix and should-fix review comments. Commit and push follow-up changes, reply to comments with verification evidence, and do not broaden scope.
```

## CI Repair With PR-Only Behavior

```text
Use slice-ci-debug-and-merge for this PR with --no-merge. Debug failing CI minimally, but leave the PR unmerged even if it becomes green.
```

Equivalent script pattern:

```bash
python3 ~/.codex/codebase-review-factory/scripts/ci_debug_and_merge.py --pr 123 --no-merge
```

## Explicit Manual Merge Handoff

Only use merge authority when the user explicitly asks for it.

```bash
python3 ~/.codex/codebase-review-factory/scripts/ci_debug_and_merge.py --pr 123 --allow-merge
```

For implementation waves:

```bash
python3 ~/.codex/agentic-dev-system/scripts/merge_wave.py --plan docs/agentic-system/build/plan.json --wave WAVE-ID --merge
```

Use `--no-merge` when you want planning or PR-only behavior:

```bash
python3 ~/.codex/agentic-dev-system/scripts/merge_wave.py --plan docs/agentic-system/build/plan.json --wave WAVE-ID --no-merge
```

## Package The Consolidated System

From the workspace used to prepare the package:

```bash
python3 scripts/package_agentic_system.py --output agentic-development-system.zip
```

The package should include canonical docs, both compatibility modules, configured agents, hooks, schemas, prompts, fixtures, and tests. It should exclude timestamped backups, `__pycache__`, `.pytest_cache`, `.DS_Store`, and bytecode files.
