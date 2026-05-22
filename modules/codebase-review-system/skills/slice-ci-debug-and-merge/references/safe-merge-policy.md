# Safe Merge Policy

This reference supports `slice-ci-debug-and-merge`.

Keep work evidence-based, bounded, and safe. Prefer concise artifacts that a human reviewer can audit. Cite files/docs used for claims. Avoid scope expansion. Use dry-run behavior for scripts before mutating target repositories.

Merging is opt-in by default. A merge script or workflow must receive explicit merge permission such as `--allow-merge` before merging. A no-merge command such as `--no-merge` or `--pr-only` is an explicit opt-out and must leave the PR unmerged even when other context suggests ship mode.
