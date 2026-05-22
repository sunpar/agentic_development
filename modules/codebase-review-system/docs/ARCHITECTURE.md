# Codebase Intelligence Module Architecture

This module is part of the Agentic Development System. The canonical architecture document is:

```text
~/.codex/agentic-dev-system/docs/ARCHITECTURE.md
```

Within that system, this module owns:

- repository inventory helpers,
- feature-model schemas and validators,
- reviewable slice schemas and validators,
- slice wave planning helpers,
- slice review/refactor skills,
- slice PR and review-loop helpers,
- CI debug and explicit merge-gate helpers,
- warning-first review/refactor hooks.

The directory name remains for compatibility with installed scripts and skill discovery.
