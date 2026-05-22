# Agentic Development

A unified local Codex workflow system for:

- repo intake and feature modeling,
- PR-sized implementation planning,
- isolated task worktrees,
- review/refactor slices,
- parallel slice wave orchestration,
- PR creation and review requests,
- explicit, gated merge handoff.

This repository packages the local Agentic Development System that was developed under `~/.codex/agentic-dev-system` and `~/.codex/codebase-review-factory`.

## Quick Install

Clone the repo and run:

```bash
python3 scripts/install.py --dry-run
python3 scripts/install.py
```

This installs:

- `modules/agentic-dev-system` to `~/.codex/agentic-dev-system`
- `modules/codebase-review-system` to `~/.codex/codebase-review-factory`
- skill discovery links under `~/.agents/skills`
- `run_agentic_review_refactor.sh` under `~/.codex/bin`

Global Codex config is not installed by default. To install agent TOMLs, hooks, `AGENTS.md`, and `hooks.json` with backups:

```bash
python3 scripts/install.py --install-global-config
```

## Generate And Run Review Slices

From the target repo:

```bash
python3 ~/.codex/codebase-review-factory/scripts/detect_repo_inventory.py \
  --output docs/agentic-system/repo-inventory.json

python3 ~/.codex/codebase-review-factory/scripts/build_feature_model.py \
  docs/agentic-system/repo-inventory.json \
  --output docs/agentic-system/feature-model.json
```

Then ask Codex:

```text
Use codebase-deep-analyzer and feature-model-builder to refine docs/agentic-system/feature-model.json with evidence from docs, code paths, tests, entry points, risks, and unknowns. Do not edit code.
```

Then:

```bash
python3 ~/.codex/codebase-review-factory/scripts/validate_feature_model.py \
  docs/agentic-system/feature-model.json

python3 ~/.codex/codebase-review-factory/scripts/generate_slice_plan.py \
  docs/agentic-system/feature-model.json \
  --output-dir docs/agentic-system/review

python3 ~/.codex/codebase-review-factory/scripts/validate_slice_plan.py \
  docs/agentic-system/review/slice-plan.json
```

Dry-run wave orchestration:

```bash
python3 ~/.codex/codebase-review-factory/scripts/orchestrate_slice_waves.py \
  docs/agentic-system/review/slice-plan.json \
  docs/agentic-system/review/slice-plan.json \
  --dry-run \
  --max-parallel 999 \
  --allow-pr \
  --allow-review-request \
  --allow-merge \
  --merge-method squash
```

Run PR-only:

```bash
python3 ~/.codex/codebase-review-factory/scripts/orchestrate_slice_waves.py \
  docs/agentic-system/review/slice-plan.json \
  docs/agentic-system/review/slice-plan.json \
  --max-parallel 999 \
  --allow-pr \
  --allow-review-request \
  --no-merge
```

Run with explicit merge gates:

```bash
python3 ~/.codex/codebase-review-factory/scripts/orchestrate_slice_waves.py \
  docs/agentic-system/review/slice-plan.json \
  docs/agentic-system/review/slice-plan.json \
  --max-parallel 999 \
  --allow-pr \
  --allow-review-request \
  --allow-merge \
  --merge-method squash
```

Resume an interrupted run:

```bash
python3 ~/.codex/codebase-review-factory/scripts/orchestrate_slice_waves.py \
  docs/agentic-system/review/slice-plan.json \
  docs/agentic-system/review/slice-plan.json \
  --run-dir "/path/to/original/run-dir" \
  --worktree-dir ~/.codex/worktrees/codebase-review \
  --resume \
  --reuse-worktrees \
  --max-parallel 999 \
  --allow-pr \
  --allow-review-request \
  --allow-merge \
  --merge-method squash
```

## Main Directories

- `modules/agentic-dev-system`: build/task planning, task worktrees, PR helpers, tests, fixtures, docs, and skills.
- `modules/codebase-review-system`: feature modeling, review slices, wave orchestration, merge gate, tests, fixtures, schemas, prompts, docs, and skills.
- `configs`: optional global Codex config templates, agent TOMLs, hooks, `AGENTS.md`, and `hooks.json`.
- `scripts`: installer plus the end-to-end review/refactor wrapper.
- `tools`: packaging scripts used to build reviewer/upload archives.
- `docs/public-install`: public installation and operational docs.

## Safety Defaults

- Merge is disabled unless `--allow-merge` is provided.
- `--no-merge` / `--pr-only` wins over merge authority.
- Runs write state outside target repos by default under `~/.codex/runs/codebase-review`.
- Existing user Codex files are backed up before replacement by the installer.
- Global Codex config is opt-in.

