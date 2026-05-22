# Troubleshooting

## Skill discovery
- Verify `~/.agents/skills/agentic-dev-system` exists and is a symlink to `~/.codex/agentic-dev-system/skills`.
- Verify the target skill exists with `ls "$HOME/.agents/skills/agentic-dev-system"`.
- Re-run `python3 ~/.codex/agentic-dev-system/scripts/sync_skills.py --check`.

## Hooks blocking unexpectedly
- Check `AGENTIC_DEV_STRICT_HOOKS`.
- Warning-only mode: default.
- Strict mode: set `AGENTIC_DEV_STRICT_HOOKS=1`.

## Protected branch or publish issues
- Confirm branch with `git branch --show-current`.
- Use `--force-protected` only for explicit requests.
- Confirm `gh auth status` if publish scripts fail.
