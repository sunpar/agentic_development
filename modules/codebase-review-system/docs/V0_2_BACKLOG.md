# V0.2 Backlog

The current codebase-intelligence module is a v0.1 scaffold. These items are intentionally not claimed as complete production behavior.

## Feature Implementation Flow

- Implemented in `feature_task_generator.py`: emits epics, milestones, releases, PR-sized implementation tasks, task Markdown files, tasks CSV, and waves from a feature model.
- Generated tasks include TDD plans, context bundles, write scopes, dependencies, parallel conflicts, verification commands, and acceptance criteria.
- Feature implementation tasks are separate from codebase review/refactor slices.
- Remaining follow-up: add an implementation-wave executor that consumes generated task plans directly.

## Real Wave Orchestration

- Implemented in `orchestrate_slice_waves.py`: resumable state, per-slice worktrees, `--max-parallel`, wave failure blocking, ordered merge gates, external run state under `~/.codex/runs/codebase-review/`, post-wave `run-summary.json` and `run-summary.md`, and safe cleanup listing/removal for old run directories and worktrees.
- Remaining follow-up: add aggregate reporting across multiple historical runs.

## PR Review And CI Loop

- Implemented for merge gating: GraphQL review-thread checks, required CI checks, review decision, draft/mergeability/head-SHA gates, and split `merge_gate.py` execution.
- Remaining follow-up: richer provider identity tracking, actionable classification reports, and standalone review-polling UX.

## Hooks

- Implemented with tests and documented inputs: strict hook behavior, slice-state scope fallback, diff-aware slop scanning by default, and Codex transcript payload support for stop summaries.
- Remaining follow-up: add fixture examples for each installed hook payload and keep hook behavior aligned with future Codex hook schema changes.

## Schemas And Validators

- Implemented in `validate_slice_plan.py`: required fields, list-shaped fields, unsafe path checks, slice type and risk enums, branch safety, positive expected PR size fields, dependency cycle detection, unknown dependency and parallel-conflict references, wave membership, dependency wave ordering, same-wave edit conflicts, and declared same-wave parallel conflicts.
- Remaining follow-up: tighten JSON Schema files to match validator behavior, add stricter ID and branch-name patterns, and validate nonempty context/test plans beyond the current `files_allowed_to_edit` and `verification_commands` checks.

## Skill Depth

- Promote operational details from manual workflows into skill references.
- Add good/bad examples, output examples, and concrete procedure contracts.
- Keep manual workflows as explicit opt-in fallbacks.
