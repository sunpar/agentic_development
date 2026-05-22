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
  review/
    slice-plan.json
    slices.csv
    slices/
```

Some compatibility scripts still default to historical paths. Pass explicit `--output` or `--output-dir` values when you want the unified artifact layout.

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
