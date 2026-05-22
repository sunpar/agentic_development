---
name: wave-validator
description: Validate wave parallel safety and dependency ordering across task plans.
---

# Wave Validator

## Trigger
Use before dispatching any wave.

## Inputs
- `plan.json`

## Outputs
- Validation report of dependency order and same-wave safety.

## Procedure
1. Check dependency IDs exist.
2. Enforce dependency order and compute wave topological constraints.
3. For each wave, verify same-wave tasks have no dependency edges.
4. Check write-set overlap; allow only if explicit merge-safe metadata exists.
5. Flag schema/config/public API/dependency-change risks crossing same-wave.

## Guardrails
- Fail on dependency cycles.
- Fail if same-wave global config/schema migration tasks overlap.

## Success criteria
- A clean wave schedule where no unsafe parallel edges exist.

## Prefer Superpowers
- Use `using-git-worktrees` and `subagent-driven-development` for independent validation tasks.

## Avoid scope creep
- Do not reorder for convenience; only for safety violations.

## Concrete artifact names
- `docs/agent-plans/<feature>/plan.json`
