# Installation

## Requirements

- macOS or Linux shell environment.
- Python 3.9+.
- Codex CLI installed and authenticated.
- GitHub CLI `gh` installed and authenticated for PR/review/merge automation.

Check GitHub auth:

```bash
gh auth status
```

## Safe Install

Preview first:

```bash
python3 scripts/install.py --dry-run
```

Install modules and skill discovery:

```bash
python3 scripts/install.py
```

Install optional global Codex config:

```bash
python3 scripts/install.py --install-global-config
```

The installer backs up existing files and directories using a timestamp suffix before replacing them.

## Installed Paths

Default paths:

```text
~/.codex/agentic-dev-system
~/.codex/codebase-review-factory
~/.codex/bin/run_agentic_review_refactor.sh
~/.agents/skills/agentic-dev-system
~/.agents/skills/codebase-review-factory
```

Override roots:

```bash
python3 scripts/install.py \
  --codex-home /custom/.codex \
  --agents-home /custom/.agents
```

Copy skills instead of symlinking:

```bash
python3 scripts/install.py --copy-skills
```

## Validate Install

```bash
python3 -B -m unittest discover ~/.codex/agentic-dev-system/tests
python3 -B -m unittest discover ~/.codex/codebase-review-factory/tests
python3 -m py_compile ~/.codex/agentic-dev-system/scripts/*.py ~/.codex/codebase-review-factory/scripts/*.py
```

