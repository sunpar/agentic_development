# Wave Rules

- Same-wave tasks must not depend on each other.
- Same-wave write sets should be disjoint unless explicitly merge-safe.
- Same-wave tasks should not touch global config, schema migrations, dependency changes, generated files, or public contracts unless safe.
- A wave cannot start until all prior waves complete.
