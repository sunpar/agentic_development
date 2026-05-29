# Validation Rubric

This reference supports `reviewable-slice-validator`.

## Procedure

Validate structure first, then reviewability. A slice is reviewable only when it has a bounded write set, concrete context to read, concrete tests to inspect or write, clear non-goals, acceptance criteria, and verification commands that a reviewer can run.

## Commands

```bash
python3 ~/.codex/codebase-review-factory/scripts/validate_slice_plan.py docs/agentic-system/review/slice-plan.json --json
python3 ~/.codex/codebase-review-factory/scripts/emit_slices_csv.py docs/agentic-system/review/slice-plan.json --output docs/agentic-system/review/slices.csv
```

## Output Contract

- List blocking schema or validator errors first.
- Call out same-wave edit conflicts and dependency ordering errors.
- Identify oversized slices by write-set breadth or vague acceptance criteria.
- Recommend splitting, serializing, or adding missing context rather than widening scope.

## Good Example

`SLICE-002 is valid but should be serialized after SLICE-001 because both edit src/routes.py. Its tests_to_read and verification_commands are concrete.`

## Bad Example

`Looks good because the JSON has all required keys, even though files_allowed_to_edit is src/** and acceptance_criteria is "works".`
