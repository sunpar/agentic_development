# V0.2 Backlog

The current codebase-intelligence module is a v0.1 scaffold. These items are intentionally not claimed as complete production behavior.

## Feature Implementation Flow

- Implemented in `feature_task_generator.py`: emits epics, milestones, releases, PR-sized implementation tasks, task Markdown files, tasks CSV, and waves from a feature model.
- Generated tasks include TDD plans, context bundles, write scopes, dependencies, parallel conflicts, verification commands, and acceptance criteria.
- Feature implementation tasks are separate from codebase review/refactor slices.
- Implemented in `orchestrate_implementation_waves.py`: validates generated implementation plans, prepares or dry-runs task worktrees, emits task prompts, and writes external run state and summaries.
- Implemented in `report_implementation_wave_runs.py`: aggregate reporting across multiple historical implementation-wave runs, including dry-run counts, selected waves, task status totals, failed tasks, branches, worktrees, and prompt paths from `run-summary.json` or `run-state.json`.
- Implemented dry-run-safe cleanup/listing in `orchestrate_implementation_waves.py` for old implementation run directories and task worktrees, with actual removal gated by `--confirm-cleanup`.
- Remaining follow-up: add Codex task execution and PR automation after the dry-run/worktree executor has been dogfooded.

## Real Wave Orchestration

- Implemented in `orchestrate_slice_waves.py`: resumable state, per-slice worktrees, `--max-parallel`, wave failure blocking, ordered merge gates, external run state under `~/.codex/runs/codebase-review/`, post-wave `run-summary.json` and `run-summary.md`, and safe cleanup listing/removal for old run directories and worktrees.
- Implemented in `report_codebase_review_runs.py`: aggregate reporting across multiple historical runs, including status totals, failed slices, and PR numbers from `run-summary.json` or `run-state.json`.

## PR Review And CI Loop

- Implemented for merge gating: GraphQL review-thread checks, required CI checks, review decision, draft/mergeability/head-SHA gates, and split `merge_gate.py` execution.
- Implemented in `poll_review_comments.py`: standalone review polling and saved-payload classification with provider identity counts, actionable `must_fix` / `should_fix` grouping, and Markdown/JSON reports.

## Hooks

- Implemented with tests and documented inputs: strict hook behavior, slice-state scope fallback, diff-aware slop scanning by default, and Codex transcript payload support for stop summaries.
- Implemented hook fixture examples under `fixtures/hooks/` for slice-state scope loading, diff-aware slop detection, and Codex transcript stop-summary payloads.
- Remaining follow-up: keep hook behavior aligned with future Codex hook schema changes.

## Schemas And Validators

- Implemented in `validate_slice_plan.py`: required fields, list-shaped fields, unsafe path checks, slice type and risk enums, branch safety, positive expected PR size fields, dependency cycle detection, unknown dependency and parallel-conflict references, wave membership, dependency wave ordering, same-wave edit conflicts, and declared same-wave parallel conflicts.
- Implemented tighter `feature_model` and `slice_plan` JSON Schemas with stricter ID and branch-name patterns, enum constraints, positive expected PR size fields, and nonempty arrays where execution needs concrete context.
- Implemented validator checks for nonempty slice context and test plans beyond `files_allowed_to_edit` and `verification_commands`.

## Skill Depth

- Implemented deeper operational references for maintenance orchestration, wave execution, failure handling, review comment resolution, and reviewable slice validation.
- Added command examples, output contracts, and good/bad examples for those operational references.
- Keep manual workflows as explicit opt-in fallbacks.
