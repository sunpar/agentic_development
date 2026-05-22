---
name: dependency-change-review
description: Validate dependency additions/upgrades for risk and security.
---

# Dependency Change Review

## Trigger
Use before dependency changes merge.

## Inputs
- Dependency diff and package metadata.

## Outputs
- Risk assessment and recommendation.

## Procedure
1. Check licenses and maintenance.
2. Evaluate supply-chain risk and transitive blowup.
3. Estimate native-build risk and bundle impact.
4. Decide if existing dependencies can satisfy requirement.

## Guardrails
- Do not approve unknown/new risky native dependencies without explicit justification.

## Success criteria
- Approved dependency changes include rationale and fallback plan.
