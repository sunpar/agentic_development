# Skill Discovery Manifest

The Agentic Development System keeps two compatibility skill collections discoverable under `~/.agents/skills`.

| Discovery path | Target | Purpose |
| --- | --- | --- |
| `~/.agents/skills/agentic-dev-system` | `~/.codex/agentic-dev-system/skills` | Initial build, task planning, task execution, review, integration, PR, and shared cleanup skills |
| `~/.agents/skills/codebase-review-factory` | `~/.codex/codebase-review-factory/skills` | Repository intelligence, feature modeling, slice review/refactor, slice PR, and CI/merge skills |

## Validate Discovery

```bash
python3 ~/.codex/agentic-dev-system/scripts/sync_skills.py --check
python3 ~/.codex/codebase-review-factory/scripts/sync_skills.py --dry-run
```

## Repair Discovery

```bash
python3 ~/.codex/agentic-dev-system/scripts/sync_skills.py
python3 ~/.codex/codebase-review-factory/scripts/sync_skills.py
```

Do not replace existing non-symlink skill directories without a backup. The sync scripts back up conflicting discovery paths before replacement.
