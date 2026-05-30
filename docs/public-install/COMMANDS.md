# Operational Commands

## Full Review Slice Generation

```bash
cd /path/to/repo

python3 ~/.codex/codebase-review-factory/scripts/detect_repo_inventory.py \
  --output docs/agentic-system/repo-inventory.json

python3 ~/.codex/codebase-review-factory/scripts/build_feature_model.py \
  docs/agentic-system/repo-inventory.json \
  --output docs/agentic-system/feature-model.json
```

Codex refinement prompt:

```text
Use codebase-deep-analyzer and feature-model-builder to refine docs/agentic-system/feature-model.json with evidence from docs, code paths, tests, entry points, risks, and unknowns. Do not edit code.
```

```bash
python3 ~/.codex/codebase-review-factory/scripts/validate_feature_model.py \
  docs/agentic-system/feature-model.json

python3 ~/.codex/codebase-review-factory/scripts/generate_slice_plan.py \
  docs/agentic-system/feature-model.json \
  --output-dir docs/agentic-system/review

python3 ~/.codex/codebase-review-factory/scripts/validate_slice_plan.py \
  docs/agentic-system/review/slice-plan.json
```

## Implementation Wave Reporting

```bash
python3 ~/.codex/agentic-dev-system/scripts/report_implementation_wave_runs.py \
  --runs-root ~/.codex/runs/implementation-waves \
  --output-json ~/.codex/runs/implementation-waves/report.json \
  --output-md ~/.codex/runs/implementation-waves/report.md

python3 ~/.codex/agentic-dev-system/scripts/orchestrate_implementation_waves.py \
  docs/agentic-system/implementation/implementation-plan.json \
  --wave 1 \
  --run-dir ~/.codex/runs/implementation-waves/RUN \
  --worktree-dir ~/.codex/worktrees/implementation \
  --resume \
  --reuse-worktrees

python3 ~/.codex/agentic-dev-system/scripts/orchestrate_implementation_waves.py \
  --cleanup-artifacts \
  --dry-run \
  --runs-root ~/.codex/runs/implementation-waves \
  --worktree-dir ~/.codex/worktrees/implementation \
  --cleanup-older-than-days 30
```

## End-To-End Wrapper

Dry-run:

```bash
~/.codex/bin/run_agentic_review_refactor.sh \
  /path/to/repo \
  --max-parallel 999 \
  --allow-pr \
  --allow-review-request \
  --auto-merge \
  --dry-run-orchestrator
```

PR-only:

```bash
~/.codex/bin/run_agentic_review_refactor.sh \
  /path/to/repo \
  --max-parallel 999 \
  --allow-pr \
  --allow-review-request \
  --no-merge
```

Auto-merge with gates:

```bash
~/.codex/bin/run_agentic_review_refactor.sh \
  /path/to/repo \
  --max-parallel 999 \
  --allow-pr \
  --allow-review-request \
  --auto-merge \
  --merge-method squash
```

## Direct Wave Runner

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

Resume:

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
