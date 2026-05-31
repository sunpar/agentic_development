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

python3 ~/.codex/agentic-dev-system/scripts/validate_plan.py \
  docs/agentic-system/implementation/implementation-plan.json

python3 ~/.codex/agentic-dev-system/scripts/orchestrate_implementation_waves.py \
  docs/agentic-system/implementation/implementation-plan.json \
  --wave 1 \
  --worktree-dir ~/.codex/worktrees/implementation \
  --dry-run

python3 ~/.codex/agentic-dev-system/scripts/orchestrate_implementation_waves.py \
  docs/agentic-system/implementation/implementation-plan.json \
  --wave 1 \
  --worktree-dir ~/.codex/worktrees/implementation \
  --base-ref HEAD

python3 ~/.codex/agentic-dev-system/scripts/orchestrate_implementation_waves.py \
  docs/agentic-system/implementation/implementation-plan.json \
  --wave 1 \
  --task TASK-001 \
  --worktree-dir ~/.codex/worktrees/implementation \
  --base-ref HEAD \
  --allow-codex

python3 ~/.codex/agentic-dev-system/scripts/orchestrate_implementation_waves.py \
  docs/agentic-system/implementation/implementation-plan.json \
  --wave 1 \
  --task TASK-001 \
  --worktree-dir ~/.codex/worktrees/implementation \
  --base-ref HEAD \
  --allow-codex \
  --allow-pr

python3 ~/.codex/agentic-dev-system/scripts/orchestrate_implementation_waves.py \
  docs/agentic-system/implementation/implementation-plan.json \
  --wave 1 \
  --task TASK-001 \
  --worktree-dir ~/.codex/worktrees/implementation \
  --base-ref HEAD \
  --allow-codex \
  --allow-pr \
  --allow-review-request \
  --review-agents codex,copilot

python3 ~/.codex/agentic-dev-system/scripts/orchestrate_implementation_waves.py \
  docs/agentic-system/implementation/implementation-plan.json \
  --wave 1 \
  --task TASK-001 \
  --worktree-dir ~/.codex/worktrees/implementation \
  --base-ref HEAD \
  --allow-codex \
  --allow-pr \
  --allow-review-request \
  --review-agents codex,copilot \
  --allow-merge \
  --merge-method squash
```

The generator writes:

- `implementation-plan.json` with epics, milestones, releases, PR-sized tasks, and waves.
- `waves.json` for implementation wave execution planning.
- `tasks.csv` for spreadsheet-style tracking.
- `tasks/TASK-*.md` with context bundles, write scopes, TDD plans, tests to write first, verification commands, acceptance criteria, dependencies, and rollback notes.
- `epics/EPIC-*.md` summaries.

Use `--feature FEATURE-ID` to generate tasks for one feature, and `--dry-run` to print JSON without writing files.

`orchestrate_implementation_waves.py` prepares task worktrees, emits per-task prompts, and writes external run state under `~/.codex/runs/implementation-waves/`. Pass `--allow-codex` to run `codex exec` against each task prompt after worktree preparation, add `--allow-pr` to commit changed files, push the task branch, and create a PR, add `--allow-review-request` to comment review requests for `--review-agents`, and add `--allow-merge` to run the shared merge gate for the task PR. If the merge gate reports unresolved review threads, `--review-repair-attempts` bounds automatic Codex repair attempts; use `--no-resolve-review-threads` to leave GitHub thread resolution manual. `--no-merge` and `--pr-only` disable merge execution even when merge authority is otherwise present. It checkpoints run state and summaries at run start and after each task, so partial preparation failures preserve completed task state and the failing task error.
Run summaries include the implementation plan path and hash, selected task ids, execution options, per-task wave numbers, branches, worktrees, prompt paths, Codex status, verification results, changed files, commit SHAs, PR URLs/numbers, review request records, review repair records, merge-gate logs, merge timestamps, statuses, and errors.

Resume a partially prepared implementation wave:

```bash
python3 ~/.codex/agentic-dev-system/scripts/orchestrate_implementation_waves.py \
  docs/agentic-system/implementation/implementation-plan.json \
  --wave 1 \
  --run-dir ~/.codex/runs/implementation-waves/RUN \
  --worktree-dir ~/.codex/worktrees/implementation \
  --resume \
  --reuse-worktrees
```

Resume mode verifies the saved repo, plan path/hash, selected waves, and dry-run mode before skipping already prepared tasks and retrying failed or missing tasks. If a task is already `pr_ready` and the resumed command adds `--allow-merge`, the executor runs the merge gate against the saved PR instead of re-running Codex. Reported resume commands preserve saved Codex, PR, review-request, review-repair, and merge flags from the original run.
Use repeatable `--task TASK-ID` with `--wave` to prepare only selected tasks from a wave, preserving plan validation and wave order.

Aggregate historical implementation-wave runs:

```bash
python3 ~/.codex/agentic-dev-system/scripts/report_implementation_wave_runs.py \
  --runs-root ~/.codex/runs/implementation-waves \
  --output-json ~/.codex/runs/implementation-waves/report.json \
  --output-md ~/.codex/runs/implementation-waves/report.md
```

The implementation-wave report scans direct child run directories, reads `run-summary.json` when available, falls back to `run-state.json`, and totals selected waves, tasks, task statuses, dry-run counts, failed tasks, branches, worktrees, prompt paths, PR numbers, review-request counts, merged task counts, and merge log paths across runs. When state metadata is available, failed tasks include exact resume commands with the run directory, wave, task id, worktree root, dry-run mode, saved execution options, and `--resume --reuse-worktrees`.

List old implementation-wave run directories and task worktrees without removing anything:

```bash
python3 ~/.codex/agentic-dev-system/scripts/orchestrate_implementation_waves.py \
  --cleanup-artifacts \
  --dry-run \
  --runs-root ~/.codex/runs/implementation-waves \
  --worktree-dir ~/.codex/worktrees/implementation \
  --cleanup-older-than-days 30
```

Actual removal requires both `--cleanup-artifacts` and `--confirm-cleanup`. Run directories are only considered when they contain `run-state.json`; worktree cleanup scans direct child directories of `--worktree-dir`.

## Merge Policy

Merging is opt-in. Use `--allow-merge` only when the user explicitly asks for merge execution. Use `--no-merge` or `--pr-only` when the desired outcome is PR-only.

When `--allow-review-request` is enabled, the orchestrator requests Codex and Copilot review by default using `--review-agents codex,copilot`. Requests run in parallel, and each agent is polled independently until it submits review activity or `--review-agent-timeout-seconds` elapses. The default per-agent wait is 600 seconds. If at least one agent responds, the merge gate requires completed review activity after the request timestamp; `--review-timeout-seconds` also defaults to 600 seconds for that gate. If no requested agent responds before timeout, the timeout is recorded and normal branch review protections still apply.

If the merge gate finds active review threads, the orchestrator automatically attempts bounded in-scope repair before giving up. Review-thread blockers fail fast by default with `--review-thread-timeout-seconds 0`, so the repair loop can run instead of waiting on already-known unresolved threads. The default is `--review-repair-attempts 2`: fetch active threads, run Codex with the thread JSON and slice scope, verify, commit, push, resolve addressed thread IDs, request fresh Codex and Copilot reviews in parallel, then retry the merge gate. Use `--review-repair-attempts 0` to disable automatic repair, or `--no-resolve-review-threads` to avoid resolving GitHub thread IDs after a pushed repair.

Write a standalone actionable review report:

```bash
python3 ~/.codex/codebase-review-factory/scripts/poll_review_comments.py \
  --pr 123 \
  --output-json actionable-review-report.json \
  --output-md actionable-review-report.md
```

For deterministic or offline classification, pass a saved `gh pr view --json comments,latestReviews,url,number,title` payload:

```bash
python3 ~/.codex/codebase-review-factory/scripts/poll_review_comments.py \
  --input-json pr-review-payload.json \
  --output-json actionable-review-report.json \
  --output-md actionable-review-report.md
```

The report normalizes review comments and reviews, records provider counts for Codex, Copilot, and human reviewers, strips explicit nonblocking phrases such as `No P1 findings`, and groups actionable feedback into `must_fix` and `should_fix`.

The wave orchestrator writes run state outside the target repository by default under `~/.codex/runs/codebase-review/`.

Use repeatable `--setup-command` flags for repo-specific worktree setup such as dependency installation. Setup commands run inside each slice worktree before Codex and before verification commands, with `.venv/bin` and `frontend/node_modules/.bin` placed first on `PATH`.

Each orchestration run writes `run-summary.json` and `run-summary.md` beside `run-state.json`. The summary includes plan and waves paths/hashes, slice branch bindings, wave status, slice status totals, worktree paths, PR numbers when available, review-request records, review-gate timestamps, review-repair attempts, merge timestamps, and slice errors when a wave blocks.

Aggregate historical runs:

```bash
python3 ~/.codex/codebase-review-factory/scripts/report_codebase_review_runs.py \
  --runs-root ~/.codex/runs/codebase-review \
  --output-json ~/.codex/runs/codebase-review/report.json \
  --output-md ~/.codex/runs/codebase-review/report.md
```

The aggregate report scans direct child run directories, reads `run-summary.json` when available, falls back to `run-state.json`, and totals waves, slices, slice statuses, failed slices, PR counts, review-request counts, and merged-slice counts across runs. Per-run entries still list exact branches, worktrees, PR numbers, review-request totals, and merge totals when present. When plan and worktree metadata is available, failed slices include a resume command with the saved slice plan, waves file, run directory, worktree root, saved execution options such as setup, PR, review-request, and merge flags, and `--resume --reuse-worktrees`.

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

Fixture examples for supported hook payloads live under `fixtures/hooks/`:

- `slice-state.json` exercises slice-state based scope loading.
- `slop-added-line.json` exercises diff-aware slop detection by storing split text parts that tests reconstruct.
- `stop-summary-payload.json` and `stop-transcript.jsonl` exercise Codex transcript payload parsing.
