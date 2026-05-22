---
name: refactor-performance
description: Improve measurable performance with evidence, without speculative rewrites.
---

# Refactor Performance

## Trigger
Use for clearly measurable performance bottlenecks.

## Inputs
- Profile output, benchmark data, and affected files.

## Outputs
- Performance-focused code changes plus evidence and fallback plan.

## Procedure
1. Identify measurable bottleneck and baseline metrics.
2. Implement minimal targeted optimization.
3. Add/retain benchmarks.
4. Confirm no regressions in existing correctness tests.

## Guardrails
- Avoid speculative optimization.
- Keep behavior intact.

## Success criteria
- Measured improvement and all required tests passing.

## Prefer Superpowers
- Use `verification-before-completion` for benchmark-based confidence checks.

## Avoid scope creep
- Do not refactor unrelated call paths.
