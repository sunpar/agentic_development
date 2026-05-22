#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  run_agentic_review_refactor.sh /path/to/repo [options]

Options:
  --max-parallel N        Max same-wave slice workers. Default: 999.
  --auto-merge            Pass --allow-merge to the slice orchestrator.
  --no-merge              Force --no-merge / PR-only behavior. Default.
  --allow-pr              Allow PR creation/update during slice execution.
  --allow-review-request  Allow requesting Codex/Copilot review on PRs.
  --merge-method METHOD   Merge method for auto-merge mode. Default: squash.
  --setup-command CMD     Run CMD inside each slice worktree before Codex and verification. Repeatable.
  --skip-codex-refine     Skip the Codex feature-model refinement prompt.
  --codex-profile NAME    Pass a Codex profile to Codex calls.
  --codex-extra-args STR  Extra safe args for Codex/orchestrator calls.
  --dry-run-orchestrator  Print orchestrator plan without executing it.
  -h, --help              Show this help.

Environment overrides:
  CODEBASE_REVIEW_ROOT    Default: ~/.codex/codebase-review-factory
  CODEX_BIN               Default: codex
  CODEX_MODEL             Default: gpt-5.5 for feature-model refinement.
  CODEX_REASONING         Default: xhigh for feature-model refinement.

Notes:
  The installed orchestrate_slice_waves.py executes validated waves, writes
  external run state, and requires explicit PR/merge flags for side effects.
  Slice worker model settings are controlled by the installed orchestrator.
USAGE
}

die() {
  echo "error: $*" >&2
  exit 1
}

repo=""
max_parallel="999"
merge_flag="--no-merge"
allow_pr=0
allow_review_request=0
merge_method="squash"
skip_codex_refine=0
codex_profile=""
codex_extra_args=""
dry_run_orchestrator=0
setup_commands=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --max-parallel)
      [[ $# -ge 2 ]] || die "--max-parallel requires a value"
      max_parallel="$2"
      shift 2
      ;;
    --auto-merge|--allow-merge)
      merge_flag="--allow-merge"
      shift
      ;;
    --no-merge|--pr-only)
      merge_flag="--no-merge"
      shift
      ;;
    --allow-pr)
      allow_pr=1
      shift
      ;;
    --allow-review-request)
      allow_review_request=1
      shift
      ;;
    --merge-method)
      [[ $# -ge 2 ]] || die "--merge-method requires a value"
      merge_method="$2"
      shift 2
      ;;
    --setup-command)
      [[ $# -ge 2 ]] || die "--setup-command requires a value"
      setup_commands+=("$2")
      shift 2
      ;;
    --skip-codex-refine)
      skip_codex_refine=1
      shift
      ;;
    --codex-profile)
      [[ $# -ge 2 ]] || die "--codex-profile requires a value"
      codex_profile="$2"
      shift 2
      ;;
    --codex-extra-args)
      [[ $# -ge 2 ]] || die "--codex-extra-args requires a value"
      codex_extra_args="$2"
      shift 2
      ;;
    --dry-run-orchestrator)
      dry_run_orchestrator=1
      shift
      ;;
    --*)
      die "unknown option: $1"
      ;;
    *)
      [[ -z "$repo" ]] || die "repo path already set: $repo"
      repo="$1"
      shift
      ;;
  esac
done

[[ -n "$repo" ]] || die "missing repo path"
[[ "$max_parallel" =~ ^[0-9]+$ ]] || die "--max-parallel must be a positive integer"
[[ "$max_parallel" -gt 0 ]] || die "--max-parallel must be greater than zero"
[[ "$merge_method" =~ ^(squash|merge|rebase)$ ]] || die "--merge-method must be squash, merge, or rebase"

repo="$(cd "$repo" && pwd)"
[[ -d "$repo/.git" ]] || die "$repo is not a git repository"

CODEBASE_REVIEW_ROOT="${CODEBASE_REVIEW_ROOT:-$HOME/.codex/codebase-review-factory}"
CODEX_BIN="${CODEX_BIN:-codex}"
CODEX_MODEL="${CODEX_MODEL:-gpt-5.5}"
CODEX_REASONING="${CODEX_REASONING:-xhigh}"

scripts_dir="$CODEBASE_REVIEW_ROOT/scripts"
inventory="docs/agentic-system/repo-inventory.json"
feature_model="docs/agentic-system/feature-model.json"
review_dir="docs/agentic-system/review"
slice_plan="$review_dir/slice-plan.json"

[[ -x "$scripts_dir/detect_repo_inventory.py" || -f "$scripts_dir/detect_repo_inventory.py" ]] || die "missing $scripts_dir/detect_repo_inventory.py"
[[ -x "$scripts_dir/build_feature_model.py" || -f "$scripts_dir/build_feature_model.py" ]] || die "missing $scripts_dir/build_feature_model.py"
[[ -x "$scripts_dir/validate_feature_model.py" || -f "$scripts_dir/validate_feature_model.py" ]] || die "missing $scripts_dir/validate_feature_model.py"
[[ -x "$scripts_dir/generate_slice_plan.py" || -f "$scripts_dir/generate_slice_plan.py" ]] || die "missing $scripts_dir/generate_slice_plan.py"
[[ -x "$scripts_dir/validate_slice_plan.py" || -f "$scripts_dir/validate_slice_plan.py" ]] || die "missing $scripts_dir/validate_slice_plan.py"
[[ -x "$scripts_dir/orchestrate_slice_waves.py" || -f "$scripts_dir/orchestrate_slice_waves.py" ]] || die "missing $scripts_dir/orchestrate_slice_waves.py"

codex_args=(exec --model "$CODEX_MODEL" -c "model_reasoning_effort=\"$CODEX_REASONING\"")
orchestrator_args=()

if [[ -n "$codex_profile" ]]; then
  codex_args+=(--profile "$codex_profile")
  orchestrator_args+=(--codex-profile "$codex_profile")
fi

if [[ -n "$codex_extra_args" ]]; then
  orchestrator_args+=(--codex-extra-args "$codex_extra_args")
fi

if [[ "$allow_pr" -eq 1 ]]; then
  orchestrator_args+=(--allow-pr)
else
  orchestrator_args+=(--no-pr)
fi

if [[ "$allow_review_request" -eq 1 ]]; then
  orchestrator_args+=(--allow-review-request)
fi

if [[ "$dry_run_orchestrator" -eq 1 ]]; then
  orchestrator_args+=(--dry-run)
fi

for setup_command in "${setup_commands[@]}"; do
  orchestrator_args+=(--setup-command "$setup_command")
done

if [[ "$merge_flag" == "--allow-merge" && "$allow_pr" -ne 1 ]]; then
  die "--auto-merge requires --allow-pr"
fi

if [[ "$merge_flag" == "--allow-merge" ]]; then
  echo "warning: --auto-merge requested. Only use this once the installed merge gate is strong enough for your repo." >&2
fi

cd "$repo"
mkdir -p "$(dirname "$inventory")" "$review_dir"

echo "==> Detecting repository inventory"
python3 "$scripts_dir/detect_repo_inventory.py" \
  --output "$inventory"

echo "==> Building initial feature model"
python3 "$scripts_dir/build_feature_model.py" \
  "$inventory" \
  --output "$feature_model"

if [[ "$skip_codex_refine" -eq 0 ]]; then
  command -v "$CODEX_BIN" >/dev/null 2>&1 || die "codex binary not found; use --skip-codex-refine or set CODEX_BIN"
  echo "==> Refining feature model with Codex"
  read -r -d '' refine_prompt <<'PROMPT' || true
Use codebase-deep-analyzer and feature-model-builder to refine docs/agentic-system/feature-model.json with evidence from docs, code paths, tests, entry points, risks, and unknowns. Do not edit code.
PROMPT
  "$CODEX_BIN" "${codex_args[@]}" "$refine_prompt"
else
  echo "==> Skipping Codex feature-model refinement"
fi

echo "==> Validating feature model"
python3 "$scripts_dir/validate_feature_model.py" \
  "$feature_model"

echo "==> Generating review slices"
python3 "$scripts_dir/generate_slice_plan.py" \
  "$feature_model" \
  --output-dir "$review_dir"

echo "==> Validating slice plan"
python3 "$scripts_dir/validate_slice_plan.py" \
  "$slice_plan"

echo "==> Running slice review/refactor orchestration"
python3 "$scripts_dir/orchestrate_slice_waves.py" \
  "$slice_plan" \
  "$slice_plan" \
  --max-parallel "$max_parallel" \
  --merge-method "$merge_method" \
  "${orchestrator_args[@]}" \
  "$merge_flag"

echo "==> Done"
