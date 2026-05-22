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
python3 ~/.codex/codebase-review-factory/scripts/orchestrate_slice_waves.py docs/agentic-system/review/slice-plan.json docs/agentic-system/review/slice-plan.json --setup-command 'make install' --max-parallel 999 --allow-pr --allow-review-request --no-merge
```

## Merge Policy

Merging is opt-in. Use `--allow-merge` only when the user explicitly asks for merge execution. Use `--no-merge` or `--pr-only` when the desired outcome is PR-only.

When `--allow-review-request` and `--allow-merge` are both enabled, the orchestrator records the review-request timestamp and the merge gate waits for a completed PR review submitted after that timestamp before merging.

The wave orchestrator writes run state outside the target repository by default under `~/.codex/runs/codebase-review/`.

Use repeatable `--setup-command` flags for repo-specific worktree setup such as dependency installation. Setup commands run inside each slice worktree before Codex and before verification commands, with `.venv/bin` and `frontend/node_modules/.bin` placed first on `PATH`.
