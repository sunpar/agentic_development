# Agentic Development System

This is the single project surface for the local Codex development system. It coordinates initial feature builds, task execution, review, granular refactor slices, PR review loops, CI repair, and explicit merge handoff.

The installed directories are kept for compatibility:

- `~/.codex/agentic-dev-system`: canonical docs, build-planning skills, task execution scripts, review/PR helpers, tests, and fixtures.
- `~/.codex/codebase-review-factory`: repository analysis, feature-model, slice-review, slice-refactor, PR lifecycle, CI, packaging, schemas, and hooks.

Use the system as one lifecycle:

1. Map the repository and user goal.
2. For new work, generate implementation tasks and waves.
3. Implement tasks in isolated worktrees with TDD.
4. Review each task, remove slop, and integrate waves only after explicit approval.
5. Build or refresh a feature model from the resulting codebase.
6. Generate granular review/refactor slices for targeted maintenance.
7. Run slice PRs through review, CI repair, and explicit merge gates.
8. Refresh docs, feature models, release notes, and follow-up task lists.

## Canonical Docs

- Architecture: `~/.codex/agentic-dev-system/docs/ARCHITECTURE.md`
- Features and capabilities: `~/.codex/agentic-dev-system/docs/CAPABILITIES.md`
- Run examples: `~/.codex/agentic-dev-system/docs/EXAMPLES.md`
- Usage quickstart: `~/.codex/agentic-dev-system/docs/USAGE.md`
- Skill index: `~/.codex/agentic-dev-system/docs/SKILL_INDEX.md`

## Safety Defaults

- Work should happen in isolated task or slice worktrees.
- Protected branches are refused by mutating helpers.
- Merge execution is opt-in. `--no-merge` and `--pr-only` force PR-only behavior.
- Hooks are warning-first unless strict mode is explicitly enabled.
- Existing compatibility paths and symlinks remain valid so installed skills do not break.

## Validation

```bash
python3 -B -m unittest discover ~/.codex/agentic-dev-system/tests
python3 -B -m unittest discover ~/.codex/codebase-review-factory/tests
python3 -B ~/.codex/agentic-dev-system/scripts/sync_skills.py --check
python3 ~/.codex/codebase-review-factory/scripts/sync_skills.py --dry-run
```
