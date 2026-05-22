# Install Report

- Date: 2026-05-21 (local)
- Base OS: macOS (Darwin)
- Setup target: `~/.codex/agentic-dev-system`
- Current project surface: Agentic Development System, with `~/.codex/codebase-review-factory` retained as a compatibility module for codebase intelligence and slice workflows.

## Setup results
- Backed up existing files before overwrite:
  - `~/.codex/config.toml.bak.20260521T224457Z`
  - `~/.codex/AGENTS.md.bak.20260521T224457Z`
  - `~/.codex/config.toml.bak.20260522T011516Z`
  - `~/.codex/config.toml.bak.20260522T020330Z`
  - `~/.codex/agents/*.toml.bak.20260522T011516Z` for changed agent definitions
  - `~/.codex/agents/{deslop-reviewer,integration-manager,pr-automation,refactorer}.toml.bak.20260522T014107Z`
  - `~/.codex/agents/integration-manager.toml.bak.20260522T020330Z`
  - `~/.codex/hooks/*.py.bak.20260522T011516Z`
  - `~/.codex/superpowers.bak.20260522T020330Z`
  - `~/.codex/hooks.json.bak.20260522T034048Z`
  - `~/.codex/hooks/*.py.bak.20260522T034048Z`
  - `~/.codex/agentic-dev-system/{scripts,skills,tests,INSTALL_REPORT.md}*.bak.20260522T034048Z` for files changed in the review-fix pass
  - `~/.codex/agentic-dev-system/{scripts,skills,docs,tests,README.md,INSTALL_REPORT.md}*.bak.20260522T123722Z` for files changed in the stabilization pass
  - `~/.codex/agentic-dev-system/fixtures/sample_plan.valid.json.bak.20260522T123722Z`
- Created directories under `~/.codex/agentic-dev-system` and `~/.codex/hooks`.
- Created new agent definitions under `~/.codex/agents/`.
- Created `~/.agents/skills/agentic-dev-system` symlink.
- Created `~/.agents/skills/superpowers` symlink to local Superpowers source.
- Superpowers source detected in plugin cache and documented (not reinstalled).
- Repointed broken `~/.codex/superpowers` bridge to `~/.codex/plugins/cache/openai-curated/superpowers/004da724`.
- Updated global profiles to use `gpt-5.5` with `model_reasoning_effort = "xhigh"`.
- Applied agent model exceptions requested on 2026-05-21:
  - `deslop-reviewer.toml`: `gpt-5.3-codex-spark`, xhigh
  - `integration-manager.toml`: `gpt-5.3-codex-spark`, xhigh
  - `pr-automation.toml`: `gpt-5.5`, medium
  - `refactorer.toml`: `gpt-5.5`, medium
- Changed global default `sandbox_mode` from `danger-full-access` to `workspace-write`.
- Installed OpenAI curated skills:
  - `gh-address-comments`
  - `gh-fix-ci`
  - `security-threat-model`
  - `screenshot`
  - `notion-spec-to-implementation`
- Verified `playwright` was already installed and `openai-docs` was available as a system skill.

## Fixes after review
- Strengthened plan validation for future-wave dependencies, unknown wave task IDs, same-wave risky write sets, and malformed list fields.
- Fixed `sync_skills.py --dry-run` so it does not create directories, added conflict backup/replacement, and added `--check`.
- Fixed `deslop_check.py` so pathless scans outside git repositories do not crash.
- Added `--help` support to hook scripts and suppressed raw git errors outside repositories.
- Made merge execution opt-in: `merge_wave.py` plans by default, executes only with `--merge`, and accepts explicit `--no-merge`.
- Fixed review findings from subagent review:
  - `sync_skills.py` now backs up conflicting symlinks before replacement.
  - `integration-manager.toml` now states merge execution is opt-in and honors `--merge`/`--no-merge`.
  - `commit_push_pr.py --dry-run --stage-all` previews local staging without requiring GitHub auth or mutating the index.
  - Superpowers discovery now validates through `~/.agents/skills/superpowers`.
- Fixed runtime issues from external review:
  - Rewrote `~/.codex/hooks.json` to the nested top-level `hooks` schema with `PreToolUse` and `Stop` hook groups; removed `PreStop`.
  - Updated hook scripts to tolerate Codex hook JSON on stdin; `tool_policy.py` now inspects `tool_input.command`.
  - Updated `request_review_and_poll.py` to emit exact `@codex review` trigger text, provider-specific Copilot text, `--pr-number`, `--repo`, and dry-run operation without GitHub auth.
  - Updated `commit_push_pr.py` existing PR detection to use `gh pr list --head ... --limit 1`.
  - Strengthened `validate_plan.py` for wave membership, post-wave verification, list-field types, duplicate writes, simple glob/path overlap, branch ref validation, and `merge_safe_reason`.
  - Updated `create_task_worktree.py` to preserve slash-based Git branch names while sanitizing only worktree directory names.
  - Updated `merge_wave.py` verification command parsing to use `shlex.split`.
  - Updated `task-generator` guidance so generated tasks include implementation guidance without over-prescribing exact code.
- Fixed stabilization findings from the follow-up review:
  - `validate_plan.py` now enforces `parallel_conflicts` as task IDs, rejects missing conflict IDs, and blocks conflicting tasks in the same wave.
  - `create_task_worktree.py` no longer uses `git worktree add -B`; new branches use `-b`, existing branches require `--reuse`, and reuse adds the existing branch without resetting it.
  - Added `scripts/address_review_comments_prompt.py` to convert collected review comments into a scoped Codex follow-up prompt and normalized JSON summary.
  - Updated `request-agent-review` skill/docs to separate review request/polling from review-comment resolution.
  - Added test path portability via `FACTORY_ROOT`, `CODEX_HOME`, and `AGENTS_HOME`.
  - Added `docs/SYMLINK_MANIFEST.md`; upload packages should use the manifest rather than archived absolute symlinks.
  - Verified the build-agent model matrix only: `planner`, `implementor`, `reviewer` use `gpt-5.5`/xhigh; `refactorer`, `pr-automation` use `gpt-5.5`/medium; `deslop-reviewer`, `integration-manager` use `gpt-5.3-codex-spark`/xhigh.

## Consolidation update
- Added canonical Agentic Development System docs:
  - `docs/ARCHITECTURE.md`
  - `docs/CAPABILITIES.md`
  - `docs/EXAMPLES.md`
- Updated active README, usage, prompt, skill-index, and symlink docs to describe one coordinated system spanning initial builds and targeted review/refactor slices.
- Kept existing compatibility roots and skill-discovery symlinks intact so installed scripts and skills continue to work.

## Manual follow-ups
- Restart Codex to pick up newly installed personal skills.
- For upload/review, use the latest `agentic-dev-system-portable-upload-*.zip`; portable packages omit absolute symlink entries and include `docs/SYMLINK_MANIFEST.md`.

## Validation
- `python3 -B -m unittest discover ~/.codex/agentic-dev-system/tests`: 53 tests passed.
- Portable test mode passed with temporary copied `FACTORY_ROOT`, `CODEX_HOME`, and `AGENTS_HOME`: 53 tests passed with the Superpowers symlink check skipped when no install-time symlink was present.
- `python3 -B ~/.codex/agentic-dev-system/scripts/validate_plan.py ~/.codex/agentic-dev-system/fixtures/sample_plan.valid.json`: `valid=True`.
- `python3 -B ~/.codex/agentic-dev-system/scripts/validate_plan.py ~/.codex/agentic-dev-system/fixtures/sample_plan.invalid.json`: failed as expected with validation errors.
- `python3 -B ~/.codex/agentic-dev-system/scripts/request_review_and_poll.py --dry-run --provider codex --focus correctness --pr-number 7 --repo owner/repo`: emitted `@codex review for correctness` without requiring GitHub auth.
- `python3 -B -m py_compile ~/.codex/hooks/*.py ~/.codex/agentic-dev-system/scripts/*.py`: passed.
- Help verified for all scripts under `~/.codex/agentic-dev-system/scripts`.
- `python3 -B ~/.codex/agentic-dev-system/scripts/sync_skills.py --check`: discovered 21 custom skills.
- `python3 -B ~/.codex/agentic-dev-system/scripts/sync_skills.py --check-superpowers`: discovered 14 Superpowers skills.
- Build-agent model matrix check passed.
