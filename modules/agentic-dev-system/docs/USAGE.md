# Usage Guide

Use this system as one coordinated development loop.

## Quick Start

1. Validate the local install:

```bash
python3 -B -m unittest discover ~/.codex/agentic-dev-system/tests
python3 -B -m unittest discover ~/.codex/codebase-review-factory/tests
```

2. Sync skill discovery:

```bash
python3 ~/.codex/agentic-dev-system/scripts/sync_skills.py
python3 ~/.codex/codebase-review-factory/scripts/sync_skills.py
```

3. Pick the flow:

- New feature or initial build: start with `repo-context-map`, then `task-generator`, `wave-validator`, `task-implementor`, `task-reviewer`, `commit-pr`, and `request-agent-review`.
- Feature-model-driven implementation: generate `docs/agentic-system/implementation/implementation-plan.json` with `feature_task_generator.py`, validate it with `validate_plan.py`, then prepare task worktrees with `orchestrate_implementation_waves.py`.
- Existing codebase review/refactor: start with `detect_repo_inventory.py`, then `feature-model-builder`, `feature-slice-generator`, `reviewable-slice-validator`, `slice-review-workflow`, `slice-refactor-workflow`, and `slice-pr-lifecycle`.

## Artifact Directory

Prefer `docs/agentic-system/` for new target-repo artifacts:

```text
docs/agentic-system/
  repo-inventory.json
  feature-model.json
  build/
    plan.json
    tasks/
  implementation/
    implementation-plan.json
    tasks.csv
    tasks/
    epics/
  review/
    slice-plan.json
    slices.csv
    slices/
```

Some compatibility scripts still default to historical paths. Pass explicit `--output` or `--output-dir` values when you want the unified artifact layout.

## Implementation Wave Preparation

```bash
python3 ~/.codex/codebase-review-factory/scripts/feature_task_generator.py docs/agentic-system/feature-model.json --output-dir docs/agentic-system/implementation
python3 ~/.codex/agentic-dev-system/scripts/validate_plan.py docs/agentic-system/implementation/implementation-plan.json
python3 ~/.codex/agentic-dev-system/scripts/orchestrate_implementation_waves.py docs/agentic-system/implementation/implementation-plan.json --wave 1 --worktree-dir ~/.codex/worktrees/implementation --dry-run
python3 ~/.codex/agentic-dev-system/scripts/orchestrate_implementation_waves.py docs/agentic-system/implementation/implementation-plan.json --wave 1 --worktree-dir ~/.codex/worktrees/implementation --base-ref HEAD
python3 ~/.codex/agentic-dev-system/scripts/orchestrate_implementation_waves.py docs/agentic-system/implementation/implementation-plan.json --wave 1 --task TASK-001 --worktree-dir ~/.codex/worktrees/implementation --base-ref HEAD --allow-codex
python3 ~/.codex/agentic-dev-system/scripts/orchestrate_implementation_waves.py docs/agentic-system/implementation/implementation-plan.json --wave 1 --task TASK-001 --worktree-dir ~/.codex/worktrees/implementation --base-ref HEAD --allow-codex --allow-pr
python3 ~/.codex/agentic-dev-system/scripts/orchestrate_implementation_waves.py docs/agentic-system/implementation/implementation-plan.json --wave 1 --task TASK-001 --worktree-dir ~/.codex/worktrees/implementation --dry-run
python3 ~/.codex/agentic-dev-system/scripts/orchestrate_implementation_waves.py docs/agentic-system/implementation/implementation-plan.json --wave 1 --run-dir ~/.codex/runs/implementation-waves/RUN --worktree-dir ~/.codex/worktrees/implementation --resume --reuse-worktrees
python3 ~/.codex/agentic-dev-system/scripts/report_implementation_wave_runs.py --runs-root ~/.codex/runs/implementation-waves --output-json ~/.codex/runs/implementation-waves/report.json --output-md ~/.codex/runs/implementation-waves/report.md
python3 ~/.codex/agentic-dev-system/scripts/orchestrate_implementation_waves.py --cleanup-artifacts --dry-run --runs-root ~/.codex/runs/implementation-waves --worktree-dir ~/.codex/worktrees/implementation --cleanup-older-than-days 30
```

The implementation-wave executor prepares task worktrees and writes run state under `~/.codex/runs/implementation-waves/` by default. Pass `--allow-codex` to run `codex exec` against each task prompt after worktree preparation, and add `--allow-pr` to commit changed files, push the task branch, and create a PR. It still does not request reviews or merge.
`validate_plan.py` rejects duplicate task branches, protected branch names, invalid Git refs, unsafe same-wave dependencies, and same-wave write conflicts before worktrees are prepared.
It checkpoints `run-state.json`, `run-summary.json`, and `run-summary.md` at run start and after each task, so partial preparation failures keep completed task state and the failing task error in the external run directory.
When Codex execution is enabled, task stdout/stderr logs and verification results are written under `tasks/<TASK-ID>/`; run summaries include the implementation plan path and hash, selected task ids, per-task wave numbers, branches, worktrees, prompt paths, Codex status, verification results, changed files, commit SHAs, PR URLs/numbers, statuses, and errors.
Resume mode reloads the existing run state, verifies the repo, implementation plan path/hash, selected waves, and dry-run mode, skips already prepared tasks, and retries failed or missing tasks.
Use repeatable `--task TASK-ID` with `--wave` to prepare only specific tasks from the selected wave while preserving plan validation and wave order.
The implementation-wave reporter scans historical run directories, reads `run-summary.json` when available, falls back to `run-state.json`, and totals selected waves, tasks, task statuses, dry-run counts, failed tasks, branches, worktrees, and prompt paths. When state metadata is available, failed tasks include exact resume commands with the run directory, wave, task id, worktree root, dry-run mode, and `--resume --reuse-worktrees`.
Cleanup mode lists matching artifacts with `--dry-run`; actual removal requires `--cleanup-artifacts --confirm-cleanup`. Run directories are only considered when they contain `run-state.json`, and worktree cleanup scans direct children of `--worktree-dir`.

## Detailed Examples

See `docs/EXAMPLES.md` for command-by-command examples.

## Safety Rules

- Do not implement directly on protected branches.
- Use one worktree per task or slice branch.
- Validate plans before execution.
- Use TDD for implementation tasks.
- Run review and deslop before PR handoff.
- Merge only when the user explicitly asks for merge execution.
- Use `--no-merge` or `--pr-only` to force PR-only behavior.

## Portable Test Mode

- Installed mode: `python3 -B -m unittest discover ~/.codex/agentic-dev-system/tests`
- Extracted-review mode: set `FACTORY_ROOT` to the extracted `agentic-dev-system`, `CODEX_HOME` to the extracted `.codex`, and `AGENTS_HOME` to the extracted `.agents`.
