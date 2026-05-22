---
name: api-contract-review
description: Audit API/schema/route/CLI contract changes for compatibility and migration needs.
---

# API Contract Review

## Trigger
Use on public contract or schema touching tasks.

## Inputs
- Diff and touched contract files.

## Outputs
- Compatibility assessment and migration notes.

## Procedure
1. Identify impacted contracts.
2. Check backward compatibility.
3. Review docs and migration impacts.
4. Suggest versioning and rollout plan.

## Guardrails
- Flag breaking changes clearly.
- Require migration plan for any compatibility removal.

## Success criteria
- No hidden compatibility regressions.
