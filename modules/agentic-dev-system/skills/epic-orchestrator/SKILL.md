---
name: epic-orchestrator
description: Execute an epic plan wave-by-wave with dispatch, review, and merge checks.
---

# Epic Orchestrator

## Trigger
Use when a plan has multiple waves and needs end-to-end execution.

## Inputs
- `epic_id`, `plan.json`, and optional branch policy.

## Outputs
- Wave execution log and escalation list.
- Integration-ready state and blockers.

## Procedure
1. Validate plan and wave order.
2. For each wave: dispatch same-wave tasks, wait for each completion note.
3. Request task reviews where required.
4. Call `integration-merge-manager` in no-merge planning mode unless merge was explicitly opted in.
5. When merge is explicitly opted in, run post-wave verification after integration.
6. Do not silently skip failed tasks; report blockers and stop.

## Guardrails
- Never skip failed tasks.
- Never merge automatically; require explicit merge opt-in, and honor explicit `--no-merge` commands.
- Escalate blockers immediately.

## Success criteria
- Each wave either fully complete or explicitly failed with justification.

## Prefer Superpowers
- Coordinate subagents via `subagent-driven-development`.

## Avoid scope creep
- Do not start future waves before current wave pass criteria.

## Concrete artifact names
- `docs/agent-plans/<feature>/plan.json`
- Worktree/task completion notes
