# Agentic Development Repository Instructions

- Keep this repository installable from a clean clone.
- Do not commit local Codex backups, caches, bytecode, or generated run directories.
- Treat `modules/agentic-dev-system` and `modules/codebase-review-system` as the source copies for installation.
- When editing installed or personal Codex copies such as `~/.codex/agentic-dev-system` or `~/.codex/codebase-review-factory`, mirror the same source changes into this repository before considering the work complete.
- Keep public config safe: global Codex config belongs in templates unless a user explicitly opts in through the installer.
- Before publishing, run the module test suites, Python compilation, installer dry-run, and a secret-pattern scan.
