# Prompt

Use slice-ci-debug-and-merge for one PR. Debug CI minimally. Treat ci_debug_and_merge.py as a CI check helper plus optional manual merge command wrapper, not as a complete merge gate. Merge only with explicit --allow-merge after separately verifying target PR, non-draft state, mergeability, required checks, review policy, unresolved review threads, unresolved must-fix comments, local cleanliness, and slice scope. If --no-merge or --pr-only is provided, leave the PR unmerged.
