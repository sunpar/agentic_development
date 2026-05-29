# Agentic Development Next Steps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the current review/merge orchestration work, validate release readiness, refresh backlog truth, then add the next operational features in order.

**Architecture:** Keep source changes in `modules/agentic-dev-system` and `modules/codebase-review-system`, with installed copies treated as generated install targets. Add behavior through small CLI helpers and validators, with tests in the relevant module test suites before production edits.

**Tech Stack:** Python standard library CLIs, `unittest`, shell-based installer dry-runs, Codex skill Markdown docs, and repository hook scripts.

---

### Task 1: Stabilize Current Review And Merge Orchestration

**Files:**
- Modify: `modules/codebase-review-system/scripts/orchestrate_slice_waves.py`
- Modify: `modules/codebase-review-system/scripts/merge_gate.py`
- Modify: `modules/codebase-review-system/docs/USAGE.md`
- Modify: `modules/codebase-review-system/docs/PR_REVIEW_AND_MERGE_POLICY.md`
- Modify: `modules/agentic-dev-system/docs/EXAMPLES.md`
- Test: `modules/codebase-review-system/tests/test_orchestrator_dry_run.py`
- Test: `modules/codebase-review-system/tests/test_merge_gate.py`

- [x] Run focused tests for the existing review/merge edits.
- [x] Inspect gaps in docs and test coverage.
- [x] Confirm no additional failing tests were needed before production edits.
- [x] Confirm no additional production fixes were needed.
- [x] Re-run focused review/merge tests.

### Task 2: Run Publish-Readiness Validation

**Files:**
- Read: `AGENTS.md`
- Read: `scripts/install.py`
- Read: `configs/hooks/secret_scan.py`

- [x] Run both module test suites.
- [x] Compile Python files in `modules`, `scripts`, `tools`, and `configs`.
- [x] Run `python3 scripts/install.py --dry-run`.
- [x] Run a secret-pattern scan using the repository hook or equivalent local command.
- [x] Record any failures and fix only failures that block this repository from publishing.

### Task 3: Refresh Backlog Truth

**Files:**
- Modify: `modules/codebase-review-system/docs/V0_2_BACKLOG.md`

- [x] Compare backlog claims against current validators and orchestration code.
- [x] Update completed items so they are not listed as future work.
- [x] Keep remaining work concrete and testable.
- [x] Re-read the doc for stale or contradictory wording.

### Task 4: Add Post-Wave Summary And Cleanup Commands

**Files:**
- Modify: `modules/codebase-review-system/scripts/orchestrate_slice_waves.py`
- Modify: `modules/codebase-review-system/tests/test_orchestrator_dry_run.py`
- Modify: `modules/codebase-review-system/docs/USAGE.md`

- [x] Add failing tests for summary generation from run state.
- [x] Add failing tests for dry-run cleanup listing of old run directories and worktrees.
- [x] Implement summary writing after orchestration.
- [x] Implement cleanup/listing command behavior with dry-run safety.
- [x] Document summary and cleanup usage.
- [x] Run focused orchestrator tests.

### Task 5: Harden Hook Behavior

**Files:**
- Modify: `modules/codebase-review-system/hooks/slice_scope_guard.py`
- Modify: `modules/codebase-review-system/hooks/slop_guard.py`
- Modify: `modules/codebase-review-system/hooks/stop_summary_guard.py`
- Add or modify tests under `modules/codebase-review-system/tests/`
- Modify docs if hook inputs change.

- [x] Add failing tests for slice-state-aware scope enforcement.
- [x] Add failing tests for diff-aware slop checks.
- [x] Add failing tests for Codex-shaped stop-summary payloads.
- [x] Implement the smallest hook changes that satisfy those tests.
- [x] Run hook-focused and module tests.

### Task 6: Build Feature Implementation Task Generator

**Files:**
- Create or modify: `modules/codebase-review-system/scripts/feature_task_generator.py`
- Add tests under `modules/codebase-review-system/tests/`
- Add fixtures under `modules/codebase-review-system/fixtures/`
- Modify: `modules/codebase-review-system/docs/V0_2_BACKLOG.md`
- Modify usage docs as needed.

- [x] Add failing tests for generating epics, PR-sized task Markdown files, task CSV, and waves from a feature model.
- [x] Implement a minimal deterministic generator separate from review/refactor slices.
- [x] Include TDD plans, context bundles, allowed edit scopes, dependencies, parallel conflicts, verification commands, and acceptance criteria in generated tasks.
- [x] Validate generated output shape in tests.
- [x] Document how to run the generator.
- [x] Run full validation again.
