# Agentic Development System: Codebase Intelligence Module

This directory is a compatibility module inside the local Agentic Development System. It provides repository inventory, feature modeling, reviewable slice planning, targeted review/refactor workflows, PR lifecycle helpers, CI repair helpers, schemas, prompts, hooks, tests, and package support.

Canonical project docs live here:

- `~/.codex/agentic-dev-system/docs/ARCHITECTURE.md`
- `~/.codex/agentic-dev-system/docs/CAPABILITIES.md`
- `~/.codex/agentic-dev-system/docs/EXAMPLES.md`

## What This Module Provides

- Inventory a repository's docs, code, tests, CI, APIs, data models, and runtime entry points.
- Build or refresh a durable feature model with evidence and confidence.
- Generate bounded review/refactor slices with explicit files, docs, tests, non-goals, invariants, risks, review questions, and verification commands.
- Validate slice plans and plan conservative waves.
- Provide helpers for slice review, scoped refactor, PR creation, automated review loops, CI repair, and optional merge when explicitly allowed.

## Safety Defaults

- This module does not run against a project repo until invoked from that repo.
- It does not merge unless a merge script is called with explicit merge authority.
- `--no-merge` and `--pr-only` force PR-only behavior.
- Hooks are warning-first unless strict mode is explicitly enabled.
- Agent and script model policy is documented in `docs/MODEL_AGNOSTIC_DESIGN.md`.

## Common Commands

```bash
python3 ~/.codex/codebase-review-factory/scripts/sync_skills.py
python3 ~/.codex/codebase-review-factory/scripts/detect_repo_inventory.py --output docs/agentic-system/repo-inventory.json
python3 ~/.codex/codebase-review-factory/scripts/build_feature_model.py docs/agentic-system/repo-inventory.json --output docs/agentic-system/feature-model.json
python3 ~/.codex/codebase-review-factory/scripts/generate_slice_plan.py docs/agentic-system/feature-model.json --output-dir docs/agentic-system/review
python3 ~/.codex/codebase-review-factory/scripts/validate_slice_plan.py docs/agentic-system/review/slice-plan.json
python3 ~/.codex/codebase-review-factory/scripts/run_slice_with_codex.py docs/agentic-system/review/slice-plan.json SLICE-001 --dry-run
```

See `~/.codex/agentic-dev-system/docs/EXAMPLES.md` for the full coordinated flow.
