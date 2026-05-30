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
python3 ~/.codex/agentic-dev-system/scripts/report_implementation_wave_runs.py --runs-root ~/.codex/runs/implementation-waves --output-json ~/.codex/runs/implementation-waves/report.json --output-md ~/.codex/runs/implementation-waves/report.md
python3 ~/.codex/agentic-dev-system/scripts/orchestrate_implementation_waves.py --cleanup-artifacts --dry-run --runs-root ~/.codex/runs/implementation-waves --worktree-dir ~/.codex/worktrees/implementation --cleanup-older-than-days 30
```

The implementation-wave executor prepares task worktrees and writes run state under `~/.codex/runs/implementation-waves/` by default. It does not run Codex, create PRs, request reviews, or merge.
It checkpoints `run-state.json`, `run-summary.json`, and `run-summary.md` at run start and after each task, so partial preparation failures keep completed task state and the failing task error in the external run directory.
The implementation-wave reporter scans historical run directories, reads `run-summary.json` when available, falls back to `run-state.json`, and totals selected waves, tasks, task statuses, dry-run counts, failed tasks, branches, worktrees, and prompt paths.
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
