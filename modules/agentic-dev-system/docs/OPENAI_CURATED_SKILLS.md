# OpenAI Curated Skills

## Verified installed or available
- `gh-address-comments`: installed to `~/.codex/skills/gh-address-comments`
- `gh-fix-ci`: installed to `~/.codex/skills/gh-fix-ci`
- `security-threat-model`: installed to `~/.codex/skills/security-threat-model`
- `playwright`: already installed at `~/.codex/skills/playwright`
- `screenshot`: installed to `~/.codex/skills/screenshot`
- `openai-docs`: available as a system skill at `~/.codex/skills/.system/openai-docs`
- `notion-spec-to-implementation`: installed to `~/.codex/skills/notion-spec-to-implementation`

## Installer used
- Listing: `python3 ~/.codex/skills/.system/skill-installer/scripts/list-skills.py --format json`
- Install: `python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py --repo openai/skills --path skills/.curated/<skill-name>`

Restart Codex to pick up newly installed personal skills.
