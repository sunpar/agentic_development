# Troubleshooting

- Skill not found: run `python3 scripts/sync_skills.py` and restart Codex if needed.
- `gh` unavailable: install GitHub CLI and run `gh auth login`.
- Codex exec unsupported: use scripts with `--dry-run` and copy emitted prompts manually.
- Agent templates not active: copy a `.toml.template`, fill model/profile fields if required by your Codex version, then place it in `~/.codex/agents/`.
- Hooks too noisy: keep default warning mode or unset `CODEBASE_REVIEW_FACTORY_STRICT`.
