# V0.2 Backlog

The current codebase-intelligence module is a v0.1 scaffold. These items are intentionally not claimed as complete production behavior.

## Feature Implementation Flow

- Add `feature-task-generator` that emits epics, milestones, releases, PR-sized implementation tasks, task markdown files, tasks CSV, and waves.
- Include TDD plans, context bundles, allowed edit scopes, dependencies, parallel conflicts, verification commands, and acceptance criteria.
- Separate feature implementation tasks from codebase review/refactor slices.

## Real Wave Orchestration

- Implemented in `orchestrate_slice_waves.py`: resumable state, per-slice worktrees, `--max-parallel`, wave failure blocking, ordered merge gates, and external run state under `~/.codex/runs/codebase-review/`.
- Remaining follow-up: richer post-wave summary reports and cleanup commands for old worktrees/run directories.

## PR Review And CI Loop

- Implemented for merge gating: GraphQL review-thread checks, required CI checks, review decision, draft/mergeability/head-SHA gates, and split `merge_gate.py` execution.
- Remaining follow-up: richer provider identity tracking, actionable classification reports, and standalone review-polling UX.

## Hooks

- Expand strict hook behavior with tests and documented inputs.
- Make scope guard read slice state when available.
- Make slop guard diff-aware by default.
- Make stop-summary guard compatible with Codex hook payload shape.

## Schemas And Validators

- Tighten schema properties, enums, ID patterns, branch-name patterns, and typed arrays.
- Add dependency cycle detection.
- Validate wave references against task IDs.
- Validate same-wave write-set conflicts.
- Validate expected PR size and nonempty context/test plans.

## Skill Depth

- Promote operational details from manual workflows into skill references.
- Add good/bad examples, output examples, and concrete procedure contracts.
- Keep manual workflows as explicit opt-in fallbacks.
