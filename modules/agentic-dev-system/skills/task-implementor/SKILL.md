---
name: task-implementor
description: Implement one generated task in strict worktree isolation and TDD style.
---

# Task Implementor

## Trigger
Use when an implementation-ready task is assigned.

## Inputs
- Single task specification.
- Task file or JSON entry from `plan.json`.
- Repository context and read-only constraints.

## Outputs
- Code changes for one task.
- Completion note.

## Procedure
1. Create/use git worktree and task branch.
2. Load all read/write sets from task spec.
3. Write tests listed in `tests_to_write_first` first.
4. Implement only requested behavior.
5. Run verification commands.
6. Write completion note with tests, risks, deviations.

## Guardrails
- No behavior beyond the task objective.
- Use `using-git-worktrees` for isolation.
- Run in warning-first strictness and stop only on true blockers.

## Success criteria
- Tests are added/updated for requested behavior and pass.
- Completion note exists and references command evidence.

## Prefer Superpowers
- Use `using-git-worktrees` and `test-driven-development` as the default sequence.

## Avoid scope creep
- Do not touch unrelated files or dependency updates.

## Concrete artifact names
- `docs/agent-plans/<feature>/tasks/<TASK-ID>.md` (task file)
- `docs/agent-output/<TASK-ID>.md` (completion note)
