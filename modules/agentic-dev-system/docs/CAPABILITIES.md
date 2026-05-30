# Agentic Development System Capabilities

## Summary

The Agentic Development System supports the full local Codex development loop: repository understanding, initial feature builds, granular review/refactor slices, PR creation, review follow-up, CI repair, and explicit merge handoff.

## Capability Map

| Area | Capability | Primary entrypoints |
| --- | --- | --- |
| Repository intake | Detect repo structure, docs, source roots, tests, CI files, schemas, APIs, CLIs, jobs, config, and package manifests | `repo-context-map`, `detect_repo_context.py`, `detect_repo_inventory.py`, `codebase-deep-analyzer` |
| Acceptance and planning | Turn requirements into acceptance criteria, epics, PR-sized tasks, task files, CSVs, dependencies, waves, and validation commands | `acceptance-test-writer`, `task-generator`, `emit_tasks_csv.py`, `validate_plan.py` |
| Scope and wave validation | Check task size, write sets, dependencies, parallel safety, output quality, and schema validity | `task-scope-validator`, `wave-validator`, `agent-output-evaluator`, `validate_slice_plan.py`, `validate_feature_model.py` |
| Isolated implementation | Create task worktrees, execute generated task waves with bounded same-wave parallelism, require TDD, capture baseline and completion notes | `orchestrate_implementation_waves.py`, `create_task_worktree.py`, `task-implementor`, `test-baseline` |
| Task review | Review completed implementation against exact task spec, classify findings by severity, and require validation evidence | `task-reviewer`, `api-contract-review`, `dependency-change-review`, `deslop` |
| Integration | Plan integration wave-by-wave, merge branches only after explicit approval, and run post-wave checks | `merge_wave.py` |
| Feature modeling | Build and refresh evidence-backed feature models from repo inventory, docs, code paths, tests, risks, and unknowns | `feature-model-builder`, `feature-model-refresh`, `build_feature_model.py` |
| Slice generation | Break existing codebase features into bounded review/refactor slices with explicit read/write sets and invariants | `feature-slice-generator`, `generate_slice_plan.py`, `emit_slices_csv.py` |
| Slice execution | Review one slice, apply only valid findings, simplify behavior-preservingly, verify, and write completion notes | `slice-review-workflow`, `slice-refactor-workflow`, `run_slice_with_codex.py` |
| Slice waves | Execute validated same-wave slices in parallel with external run state, scoped worktrees, PR opt-in, and explicit merge gates | `slice-wave-planner`, `codebase-maintenance-orchestrator`, `orchestrate_slice_waves.py` |
| PR lifecycle | Commit focused changes, push branches, create or update PRs, and generate reviewer-useful PR bodies | `commit-pr`, `commit_push_pr.py`, `slice-pr-lifecycle`, `pr_lifecycle.py` |
| Agent review | Request Codex/Copilot review, poll comments, normalize actionable feedback, and create scoped follow-up prompts | `request-agent-review`, `request_review_and_poll.py`, `slice-agent-review-loop`, `poll_review_comments.py`, `address_review_comments_prompt.py` |
| CI repair and merge handoff | Inspect CI, repair failures minimally, and leave merge execution behind explicit authorization plus separately verified review gates | `slice-ci-debug-and-merge`, `ci_debug_and_merge.py` |
| Cleanup and prose quality | Remove AI-looking slop, vague comments, repeated text, and avoidable complexity without changing behavior | `deslop`, `codebase-deslop`, `deslop_check.py` |
| Release follow-up | Write release notes, migration notes, refreshed feature models, and follow-up task lists after integration | `release-notes-and-migration`, `feature-model-refresh` |
| Packaging | Create clean upload zips without backups, caches, bytecode, or local junk | `package_upload.py`, workspace package scripts |

## Feature Build Capabilities

### Context Mapping

The system can inspect a target repository before planning, identify test commands and entry points, and create a context map that future tasks can cite. This avoids task plans that rely on unsupported assumptions.

### Task Generation

The build path produces PR-sized tasks with explicit read sets, write sets, dependencies, acceptance criteria, non-goals, test commands, and review requirements. Tasks are grouped into waves only when same-wave work is dependency-safe and write-set-safe.

### TDD Execution

Implementation tasks are expected to run test-first. When behavior is unclear, write characterization tests first. Each task should have a baseline, failing test, implementation, green validation, completion note, and review.

### Wave Integration

Wave integration is serial and evidence-based. The integration helper plans merges by default and performs merge side effects only with explicit merge approval.

## Review And Refactor Capabilities

### Repository Inventory

The review path can generate a repository inventory from docs, source roots, tests, manifests, CI files, schemas, migrations, APIs, CLIs, jobs, and config files.

### Feature Model

The feature model records architecture, features, intended behavior, value, entry points, code paths, docs, tests, data models, related components, risks, mismatches, confidence, unknowns, and evidence.

### Reviewable Slices

Slices are small review/refactor units. Each slice declares the files to read, files allowed to edit, files not allowed to edit, docs/tests to inspect, invariants, non-goals, review questions, refactor targets, verification commands, risk, dependencies, branch, PR title, and review focus.

### Behavior-Preserving Refactor

Slice refactors should apply only valid findings. They should preserve documented behavior unless a task explicitly requests a product behavior change.

## PR, Review, And CI Capabilities

### PR Creation

The system can stage focused changes, commit them, push branches, and create or update PRs with concise rationale and test evidence.

### Review Comment Follow-Up

Review comments are collected into normalized summaries. Follow-up work is generated as a scoped prompt so only in-scope must-fix and should-fix comments are addressed.

### CI Debugging

CI debugging is intended to be minimal and evidence-first. Merge remains disabled unless explicit merge authority is provided and all gates pass.

## Current Maturity

| Capability | Status |
| --- | --- |
| Build task planning, validation fixtures, worktree creation, PR helper scripts | Implemented local helper coverage |
| Implementation wave orchestration | Implemented as a resumable local state machine with `--max-parallel`, per-task worktrees, external logs, PR/review/merge opt-ins, and wave failure blocking |
| Repository inventory, feature model skeletons, slice generation, schema validation | Implemented local helper coverage |
| Slice wave orchestration | Implemented as a resumable local state machine with `--max-parallel`, per-slice worktrees, external logs, and wave failure blocking |
| PR review polling | Merge gate checks GraphQL review threads before auto-merge; standalone polling helpers remain basic |
| CI merge state machine | `merge_gate.py` verifies PR state, required checks, review status, review threads, local cleanliness, and head SHA before opt-in merge |
| Unified documentation and package surface | Canonical docs live under `~/.codex/agentic-dev-system/docs` |

## Non-Capabilities

- The system does not automatically merge without explicit approval.
- The system does not bypass sandbox, branch, scope, or review gates.
- The system does not mutate a target repository until a specific task or slice execution path is invoked.
- The system does not make global model/provider changes outside the configured local agents and documented script policy.
- The system does not treat generated feature models or slice plans as authoritative until reviewed and validated.
