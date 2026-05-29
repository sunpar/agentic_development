# Failure Handling

This reference supports `codebase-maintenance-orchestrator`.

## Procedure

Classify failures before acting: validation failure, Codex execution failure, verification failure, PR creation failure, review-thread blocker, CI blocker, or merge gate blocker. Fix only the class of failure that is inside the current slice scope.

## Commands

```bash
python3 ~/.codex/codebase-review-factory/scripts/validate_slice_plan.py docs/agentic-system/review/slice-plan.json --json
python3 ~/.codex/codebase-review-factory/scripts/poll_review_comments.py --pr 123 --output-json actionable-review-report.json --output-md actionable-review-report.md
python3 ~/.codex/codebase-review-factory/scripts/merge_gate.py --pr 123 --repo-path . --expected-head-sha HEAD --no-merge
```

## Output Contract

- State the failing command and exit status.
- Include the smallest relevant stderr/stdout excerpt.
- Identify whether the next action is resume, repair, request human input, or abandon the slice.
- Do not mark a slice complete when verification or active review threads remain unresolved.

## Good Example

`SLICE-003 failed because pytest returned 1 in tests/test_parser.py. No PR was merged. The next action is to resume the same worktree and repair within files_allowed_to_edit.`

## Bad Example

`Tests are flaky, so I marked the slice complete and moved on.`
