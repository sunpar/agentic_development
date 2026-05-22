---
name: repo-context-map
description: Generate a repo context map for later planning and implementation safety.
---

# Repo Context Map Skill

## Trigger
Use before generating tasks when repo structure, entry points, tests, and CI are required.

## Inputs
- Repository root.
- Optional source documents and feature description.

## Outputs
- `docs/agent-context/repo-map.md`
- `docs/agent-context/test-commands.md`
- `docs/agent-context/architecture-index.md`

## Procedure
1. Inspect package manager files (`package.json`, `pyproject.toml`, `requirements.txt`, `go.mod`, etc.).
2. Detect entry points, config files, CI files, major source dirs, and test dirs.
3. Detect risk and data-model hotspots.
4. Run lightweight read-only discovery commands when available.
5. Write three markdown files under `docs/agent-context/`.

## Guardrails
- Do not modify source files.
- If a package manager file is absent, note it explicitly.
- Keep mappings stable and concise.

## Success criteria
- All three target files exist and mention architecture boundaries, package manager, test/build/lint commands, and known unknowns.

## Prefer Superpowers
- Use `using-git-worktrees` and `test-driven-development` patterns for any repo with unknown behavior before task generation.

## Avoid scope creep
- Do not recommend architecture decisions or create implementation changes.
- Limit output to observability and context.

## Concrete artifact names
- `docs/agent-context/repo-map.md`
- `docs/agent-context/test-commands.md`
- `docs/agent-context/architecture-index.md`
