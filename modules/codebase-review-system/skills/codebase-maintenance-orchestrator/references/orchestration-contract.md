# Orchestration Contract

This reference supports `codebase-maintenance-orchestrator`.

## Procedure

1. Read repository instructions and confirm the target repo is not on a protected branch.
2. Validate the slice plan before execution.
3. Start with `--dry-run` and inspect wave order, merge mode, and worktree directory.
4. Run with external state under `~/.codex/runs/codebase-review/`.
5. Keep merge disabled unless the user explicitly asked for merge execution.
6. Write or preserve `run-state.json`, `run-summary.json`, and `run-summary.md`.

## Commands

```bash
python3 ~/.codex/codebase-review-factory/scripts/validate_slice_plan.py docs/agentic-system/review/slice-plan.json
python3 ~/.codex/codebase-review-factory/scripts/orchestrate_slice_waves.py docs/agentic-system/review/slice-plan.json docs/agentic-system/review/slice-plan.json --dry-run --no-merge
python3 ~/.codex/codebase-review-factory/scripts/report_codebase_review_runs.py --runs-root ~/.codex/runs/codebase-review --output-json ~/.codex/runs/codebase-review/report.json --output-md ~/.codex/runs/codebase-review/report.md
```

## Output Contract

- Report the run directory.
- Report wave and slice status totals.
- Include PR numbers when created.
- Include blocked wave or slice errors exactly enough for the next operator to resume.
- Keep generated run state outside the target repo unless the user requested an in-repo artifact.

## Good Example

`Wave 1 completed: SLICE-001 succeeded with PR #42, SLICE-002 failed verification in tests/test_api.py. Run state: ~/.codex/runs/codebase-review/repo-20260529T120000Z. Merge was disabled.`

## Bad Example

`Ran the wave. There were some issues.`
