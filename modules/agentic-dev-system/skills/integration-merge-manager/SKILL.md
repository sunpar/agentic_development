---
name: integration-merge-manager
description: Merge one wave's task branches one-by-one with verification.
---

# Integration Merge Manager

## Trigger
Use when all tasks in a wave are implementation-complete and reviewed.

## Inputs
- Wave id and task list.
- Branch names from each task.

## Outputs
- Wave integration summary.
- Merge status and failing verification commands.

## Procedure
1. Treat merging as opt-in: do not merge unless the user explicitly asks to merge or passes `--merge`.
2. If merge is not opted in, produce the planned merge order and verification commands only.
3. When opted in, merge each task branch into the wave integration branch in order.
4. Run post-merge verification after each merge.
5. Stop on failure and report the blocking branch.
6. Resolve conflicts only when asked.

## Guardrails
- One branch merge at a time.
- Default to no merge side effects; `--no-merge` is the explicit opt-out/no-op command path.
- Never bypass failed verification.

## Success criteria
- Wave branch cleanly merges with all checks passing.

## Prefer Superpowers
- Use `finishing-a-development-branch` and `verification-before-completion` patterns.

## Avoid scope creep
- Do not merge beyond the selected wave.

## Concrete artifact names
- Wave summary markdown under `docs/agent-plans/<feature>/waves/`
