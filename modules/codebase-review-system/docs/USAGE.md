# Codebase Intelligence Module Usage

This module is used through the unified Agentic Development System flow. The canonical usage and examples are:

```text
~/.codex/agentic-dev-system/docs/USAGE.md
~/.codex/agentic-dev-system/docs/EXAMPLES.md
```

## Minimal Review/Refactor Flow

```bash
python3 ~/.codex/codebase-review-factory/scripts/detect_repo_inventory.py --output docs/agentic-system/repo-inventory.json
python3 ~/.codex/codebase-review-factory/scripts/build_feature_model.py docs/agentic-system/repo-inventory.json --output docs/agentic-system/feature-model.json
python3 ~/.codex/codebase-review-factory/scripts/validate_feature_model.py docs/agentic-system/feature-model.json
python3 ~/.codex/codebase-review-factory/scripts/generate_slice_plan.py docs/agentic-system/feature-model.json --output-dir docs/agentic-system/review
python3 ~/.codex/codebase-review-factory/scripts/validate_slice_plan.py docs/agentic-system/review/slice-plan.json
python3 ~/.codex/codebase-review-factory/scripts/orchestrate_slice_waves.py docs/agentic-system/review/slice-plan.json docs/agentic-system/review/slice-plan.json --setup-command 'make install' --max-parallel 999 --allow-pr --allow-review-request --review-agents codex,copilot --review-agent-timeout-seconds 600 --no-merge
```

## Feature Implementation Task Generation

Feature implementation tasks are generated separately from review/refactor slices:

```bash
python3 ~/.codex/codebase-review-factory/scripts/feature_task_generator.py \
  docs/agentic-system/feature-model.json \
  --output-dir docs/agentic-system/implementation
```

The generator writes:

- `implementation-plan.json` with epics, milestones, releases, PR-sized tasks, and waves.
- `waves.json` for implementation wave execution planning.
- `tasks.csv` for spreadsheet-style tracking.
- `tasks/TASK-*.md` with context bundles, write scopes, TDD plans, tests to write first, verification commands, acceptance criteria, dependencies, and rollback notes.
- `epics/EPIC-*.md` summaries.

Use `--feature FEATURE-ID` to generate tasks for one feature, and `--dry-run` to print JSON without writing files.

## Merge Policy

Merging is opt-in. Use `--allow-merge` only when the user explicitly asks for merge execution. Use `--no-merge` or `--pr-only` when the desired outcome is PR-only.

When `--allow-review-request` is enabled, the orchestrator requests Codex and Copilot review by default using `--review-agents codex,copilot`. Requests run in parallel, and each agent is polled independently until it submits review activity or `--review-agent-timeout-seconds` elapses. The default per-agent wait is 600 seconds. If at least one agent responds, the merge gate requires completed review activity after the request timestamp; `--review-timeout-seconds` also defaults to 600 seconds for that gate. If no requested agent responds before timeout, the timeout is recorded and normal branch review protections still apply.

If the merge gate finds active review threads, the orchestrator automatically attempts bounded in-scope repair before giving up. Review-thread blockers fail fast by default with `--review-thread-timeout-seconds 0`, so the repair loop can run instead of waiting on already-known unresolved threads. The default is `--review-repair-attempts 2`: fetch active threads, run Codex with the thread JSON and slice scope, verify, commit, push, resolve addressed thread IDs, request fresh Codex and Copilot reviews in parallel, then retry the merge gate. Use `--review-repair-attempts 0` to disable automatic repair, or `--no-resolve-review-threads` to avoid resolving GitHub thread IDs after a pushed repair.

The wave orchestrator writes run state outside the target repository by default under `~/.codex/runs/codebase-review/`.

Use repeatable `--setup-command` flags for repo-specific worktree setup such as dependency installation. Setup commands run inside each slice worktree before Codex and before verification commands, with `.venv/bin` and `frontend/node_modules/.bin` placed first on `PATH`.

Each orchestration run writes `run-summary.json` and `run-summary.md` beside `run-state.json`. The summary includes wave status, slice status totals, PR numbers when available, and slice errors when a wave blocks.

List old external run directories and slice worktrees without removing anything:

```bash
python3 ~/.codex/codebase-review-factory/scripts/orchestrate_slice_waves.py \
  --cleanup-artifacts \
  --dry-run \
  --runs-root ~/.codex/runs/codebase-review \
  --worktree-dir ~/.codex/worktrees/codebase-review \
  --cleanup-older-than-days 30
```

Actual removal requires both `--cleanup-artifacts` and `--confirm-cleanup`. Run directories are only considered when they contain `run-state.json`; worktree cleanup scans direct child directories of `--worktree-dir`.

## Hook Inputs

Hooks are warning-first unless `CODEBASE_REVIEW_FACTORY_STRICT=1` is set.

- `slice_scope_guard.py` reads `CODEBASE_REVIEW_FACTORY_ALLOWED_SCOPE` first. If that is missing, it can read `CODEBASE_REVIEW_FACTORY_SLICE_STATE` or `CODEBASE_REVIEW_FACTORY_SLICE_STATE_PATH`, plus optional `CODEBASE_REVIEW_FACTORY_SLICE_ID`, from a JSON object containing `files_allowed_to_edit` or a plan-like `slices` array.
- `slop_guard.py` is diff-aware by default and scans only added lines from `git diff`. Set `CODEBASE_REVIEW_FACTORY_SLOP_PATHS` to scan explicit files instead.
- `stop_summary_guard.py` reads `CODEBASE_REVIEW_FACTORY_STOP_SUMMARY`, plain stdin text, JSON stdin text, or a Codex-style JSON payload with `transcript_path`.
