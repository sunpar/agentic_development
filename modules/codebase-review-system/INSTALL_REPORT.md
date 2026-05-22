# Agentic Development System Codebase Intelligence Module Install Report

Generated: 2026-05-21T21:18:55

## Summary

Created the repository intelligence, slice review/refactor, and PR/CI compatibility module under `/Users/sunpar/.codex/codebase-review-factory`. No project repository was edited.

Current maturity note: this is a v0.1 scaffold. It includes inventory, validation, packaging, skills, agents, manual workflows, and dry-run planning helpers. Full feature-task generation and real parallel wave execution remain v0.2 work.

Important model policy update: module-controlled agents use a fixed role-specific model matrix. `wave-orchestrator` and `ci-debugger` use `gpt-5.3-codex-spark` with `model_reasoning_effort = "xhigh"`. `pr-review-manager` and `slice-refactorer` use `gpt-5.5` with `model_reasoning_effort = "medium"`. All other module agents and direct Codex slice runners use `gpt-5.5` with `model_reasoning_effort = "xhigh"`. This does not modify global Codex defaults in `~/.codex/config.toml`.

## Environment

- OS: macOS / Darwin arm64, observed via `uname` and `sw_vers`
- Shell: `/bin/zsh`
- `~/.codex`: found
- `~/.agents/skills`: found
- `~/.codex/config.toml`: found, not modified
- `~/.codex/AGENTS.md`: found, not modified
- `~/.codex/hooks.json`: found and valid JSON, not modified
- `~/.codex/agentic-dev-system`: found and reused as compatibility reference only
- `git`: found (`git version 2.50.1 (Apple Git-155)`)
- `gh`: found (`gh version 2.88.1`), authenticated as `sunpar`
- `python3`: found (`Python 3.9.6`)
- `codex`: found (`codex-cli 0.132.0`)
- `codex exec --help`: works
- `codex exec review --help`: works

## Skill And Agent Discovery

- Superpowers: found/discoverable under local skill/plugin paths.
- OpenAI curated GitHub skills found: github:gh-fix-ci, github:gh-address-comments.
- Requested curated skills not found in local scan: security-threat-model, playwright curated skill in openai-curated scan, screenshot, openai-docs, notion-spec-to-implementation.
- Custom agents: existing `~/.codex/agents` supported active TOML files; installed module agents there.
- `codex exec --help` does not expose a reliable `--agent` flag, so scripts keep `--codex-agent` as accepted metadata but do not depend on it.
- Hooks: optional warning-first hooks created under the module root only; `hooks.json` was not changed.

## Files Created Or Updated

Non-backup files under the module root: 116.

Key groups:

- `README.md`
- `INSTALL_REPORT.md`
- `docs/*.md`
- `schemas/*.schema.json`
- `fixtures/*.json`
- `skills/*/SKILL.md` and references
- `agents/*.toml.template`
- `prompts/*.md`
- `scripts/*.py`
- `hooks/*.py`
- `tests/*.py`

Skill entrypoints:

- `skills/codebase-deep-analyzer/SKILL.md`
- `skills/codebase-deslop/SKILL.md`
- `skills/codebase-maintenance-orchestrator/SKILL.md`
- `skills/codebase-review-evaluator/SKILL.md`
- `skills/feature-model-builder/SKILL.md`
- `skills/feature-model-refresh/SKILL.md`
- `skills/feature-slice-generator/SKILL.md`
- `skills/reviewable-slice-validator/SKILL.md`
- `skills/slice-agent-review-loop/SKILL.md`
- `skills/slice-ci-debug-and-merge/SKILL.md`
- `skills/slice-pr-lifecycle/SKILL.md`
- `skills/slice-refactor-workflow/SKILL.md`
- `skills/slice-review-workflow/SKILL.md`
- `skills/slice-wave-planner/SKILL.md`

Active module agents installed:

- `/Users/sunpar/.codex/agents/ci-debugger.toml`: model = "gpt-5.3-codex-spark", model_reasoning_effort = "xhigh"
- `/Users/sunpar/.codex/agents/codebase-analyst.toml`: model = "gpt-5.5", model_reasoning_effort = "xhigh"
- `/Users/sunpar/.codex/agents/feature-modeler.toml`: model = "gpt-5.5", model_reasoning_effort = "xhigh"
- `/Users/sunpar/.codex/agents/pr-review-manager.toml`: model = "gpt-5.5", model_reasoning_effort = "medium"
- `/Users/sunpar/.codex/agents/slice-generator.toml`: model = "gpt-5.5", model_reasoning_effort = "xhigh"
- `/Users/sunpar/.codex/agents/slice-refactorer.toml`: model = "gpt-5.5", model_reasoning_effort = "medium"
- `/Users/sunpar/.codex/agents/slice-reviewer.toml`: model = "gpt-5.5", model_reasoning_effort = "xhigh"
- `/Users/sunpar/.codex/agents/wave-orchestrator.toml`: model = "gpt-5.3-codex-spark", model_reasoning_effort = "xhigh"
- `/Users/sunpar/.codex/agents/wave-planner.toml`: model = "gpt-5.5", model_reasoning_effort = "xhigh"

## Symlink/Junction Status

`/Users/sunpar/.agents/skills/codebase-review-factory` -> `/Users/sunpar/.codex/codebase-review-factory/skills`

Status: created and currently points to module skills.

## Backups Made

Backup files may be present under the module root because existing personal files are backed up before overwrite. Upload packages should be created with `scripts/package_upload.py`, which excludes backup files and local caches.

Notable backup suffixes include `.bak-20260521-211414`, `.bak-20260521-211557`, and `.bak-20260521-211620`. These were created before overwriting generated files during the setup iteration.

Latest INSTALL_REPORT backup: `None`

## Validation Run

Commands run and observed results:

```bash
python3 -m unittest discover ~/.codex/codebase-review-factory/tests
# PASS: Ran 7 tests, OK

python3 ~/.codex/codebase-review-factory/scripts/validate_feature_model.py ~/.codex/codebase-review-factory/fixtures/sample_feature_model.valid.json
# PASS: VALID, rc=0

python3 ~/.codex/codebase-review-factory/scripts/validate_feature_model.py ~/.codex/codebase-review-factory/fixtures/sample_feature_model.invalid.json
# PASS: INVALID as expected, rc=1

python3 ~/.codex/codebase-review-factory/scripts/validate_slice_plan.py ~/.codex/codebase-review-factory/fixtures/sample_slice_plan.valid.json
# PASS: VALID, rc=0

python3 ~/.codex/codebase-review-factory/scripts/validate_slice_plan.py ~/.codex/codebase-review-factory/fixtures/sample_slice_plan.invalid.json
# PASS: INVALID as expected, rc=1

python3 ~/.codex/codebase-review-factory/scripts/orchestrate_slice_waves.py --help
# PASS

python3 ~/.codex/codebase-review-factory/scripts/ci_debug_and_merge.py --help
# PASS

python3 ~/.codex/codebase-review-factory/scripts/package_upload.py --help
# PASS

python3 -m py_compile ~/.codex/codebase-review-factory/scripts/*.py ~/.codex/codebase-review-factory/hooks/*.py
# PASS

for f in ~/.codex/codebase-review-factory/scripts/*.py; do python3 "$f" --help >/dev/null; done
# PASS
```

Model-policy dry run:

```bash
python3 ~/.codex/codebase-review-factory/scripts/run_slice_with_codex.py ~/.codex/codebase-review-factory/fixtures/sample_slice_plan.valid.json SLICE-001 --dry-run
# emitted: codex exec --model gpt-5.5 -c 'model_reasoning_effort="xhigh"' ...
```

## Scripts Skipped

No requested script was skipped. Some scripts are conservative placeholders for orchestration and emit prompts/dry-run plans instead of automatically performing broad remote operations.

## Safety Notes

- No project repository was edited.
- `~/.codex/config.toml`, `~/.codex/AGENTS.md`, and `~/.codex/hooks.json` were not modified.
- No danger-full-access configuration was created.
- Merge remains opt-in via `--allow-merge`; `--no-merge` and `--pr-only` explicitly force PR-only behavior.
- Upload archives created by `scripts/package_upload.py` exclude `.bak-*`, `.bak.*`, `__pycache__`, `.pytest_cache`, and `.DS_Store`.
- Hooks are warning-first and only strict when `CODEBASE_REVIEW_FACTORY_STRICT=1` is set.
- Strict hooks now perform concrete checks when configured instead of unconditional no-op exits.
- Active module agents use read-only or workspace-write sandbox policies; no active module agent uses danger-full-access.

## Manual Steps

1. Restart Codex if the skill registry does not immediately show the new module skills.
2. Verify skill discovery:

```bash
ls -l ~/.agents/skills/codebase-review-factory
find ~/.agents/skills/codebase-review-factory -maxdepth 2 -name SKILL.md | sort
```

3. Verify module tests any time:

```bash
python3 -m unittest discover ~/.codex/codebase-review-factory/tests
```

4. Before using in a target repo, start with dry-run commands and inspect generated prompts/artifacts.

## First Use Example

From a target repository:

```bash
python3 ~/.codex/codebase-review-factory/scripts/detect_repo_inventory.py --dry-run
python3 ~/.codex/codebase-review-factory/scripts/detect_repo_inventory.py --output docs/agentic-system/repo-inventory.json
```

Then invoke the relevant skills from `~/.codex/agentic-dev-system/docs/EXAMPLES.md` or this module's `docs/SAMPLE_PROMPTS.md`.
