# Wave Execution Contract

This reference supports `codebase-maintenance-orchestrator`.

## Procedure

Execute waves in ascending order. Slices within one wave may run concurrently only when `validate_slice_plan.py` accepts the plan and the wave rationale explains parallel safety. Stop later waves when any earlier wave fails.

## Commands

```bash
python3 ~/.codex/codebase-review-factory/scripts/orchestrate_slice_waves.py docs/agentic-system/review/slice-plan.json docs/agentic-system/review/waves.json --max-parallel 2 --allow-pr --allow-review-request --no-merge
python3 ~/.codex/codebase-review-factory/scripts/orchestrate_slice_waves.py docs/agentic-system/review/slice-plan.json docs/agentic-system/review/waves.json --resume --reuse-worktrees --no-merge
```

## Output Contract

- For each wave, record `running`, `succeeded`, or `failed`.
- For each slice, record branch, worktree path, status, changed files, PR number, verification results, and error text when failed.
- For repair attempts, record active thread counts before and after repair plus skipped active thread IDs.

## Good Example

`Wave 2 blocked because SLICE-004 failed its verification command. Later waves were not started. Resume command: orchestrate_slice_waves.py ... --resume --reuse-worktrees.`

## Bad Example

`Wave 2 failed, but I started wave 3 anyway because the slices looked unrelated.`
