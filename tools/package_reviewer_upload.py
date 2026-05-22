#!/usr/bin/env python3
"""Create a reviewer-facing upload archive for the Agentic Development System."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
import shutil
import tempfile
import zipfile
from pathlib import Path


HOME = Path.home()
CODEX_HOME = HOME / ".codex"
AGENTS_HOME = HOME / ".agents"
WORKSPACE = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = "agentic-development-system-review"

EXCLUDE_NAMES = {".DS_Store", ".pytest_cache", "__pycache__"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo"}


def excluded(path: Path) -> bool:
    name = path.name
    if name in EXCLUDE_NAMES:
        return True
    if any(name.endswith(suffix) for suffix in EXCLUDE_SUFFIXES):
        return True
    return (
        ".bak-" in name
        or ".bak." in name
        or ".backup." in name
        or name.endswith(".bak")
    )


def ignore(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if excluded(Path(name))}


def copy_path(src: Path, dst: Path) -> bool:
    if not src.exists() and not src.is_symlink():
        return False
    if dst.exists():
        if dst.is_dir() and not dst.is_symlink():
            shutil.rmtree(dst)
        else:
            dst.unlink()
    if src.is_symlink():
        target = src.resolve()
        if target.is_dir():
            shutil.copytree(target, dst, ignore=ignore)
        elif target.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, dst)
        return True
    if src.is_dir():
        shutil.copytree(src, dst, ignore=ignore)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return True


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def record_copy(src: Path, dst: Path, included: list[str], missing: list[str]) -> None:
    if copy_path(src, dst):
        included.append(f"{src} -> {dst.relative_to(dst.parents[1])}")
    else:
        missing.append(str(src))


def write_file_index(root: Path) -> None:
    files = sorted(
        str(path.relative_to(root))
        for path in root.rglob("*")
        if path.is_file() and not excluded(path)
    )
    write_text(root / "FILE_INDEX.txt", "\n".join(files) + "\n")


def write_discovery_manifest(root: Path) -> None:
    skills_root = AGENTS_HOME / "skills"
    lines = ["# Skill Discovery Snapshot", ""]
    if skills_root.exists():
        for child in sorted(skills_root.iterdir()):
            if child.is_symlink():
                lines.append(f"- `{child.name}` -> `{Path(os.path.realpath(child))}`")
            else:
                lines.append(f"- `{child.name}`")
    else:
        lines.append("- No `~/.agents/skills` directory found.")
    write_text(root / "SKILL_DISCOVERY.md", "\n".join(lines) + "\n")


def build_package(staging: Path) -> tuple[list[str], list[str]]:
    root = staging / PACKAGE_ROOT
    included: list[str] = []
    missing: list[str] = []

    # Reviewer-first visible layout.
    visible_sources = [
        (CODEX_HOME / "agentic-dev-system" / "README.md", root / "README.md"),
        (CODEX_HOME / "agentic-dev-system" / "docs", root / "docs"),
        (CODEX_HOME / "AGENTS.md", root / "configs" / "AGENTS.md"),
        (CODEX_HOME / "config.toml", root / "configs" / "config.toml"),
        (CODEX_HOME / "hooks.json", root / "configs" / "hooks.json"),
        (CODEX_HOME / "agents", root / "agents"),
        (CODEX_HOME / "hooks", root / "hooks"),
        (CODEX_HOME / "manual-workflows", root / "manual-workflows"),
        (CODEX_HOME / "skills", root / "skills" / "codex-skills"),
        (CODEX_HOME / "superpowers" / "skills", root / "skills" / "superpowers"),
        (CODEX_HOME / "agentic-dev-system" / "skills", root / "skills" / "agentic-dev-system"),
        (CODEX_HOME / "codebase-review-factory" / "skills", root / "skills" / "codebase-review-system"),
        (AGENTS_HOME / "skills", root / "skills-discovery"),
        (CODEX_HOME / "codebase-review-factory" / "schemas", root / "schemas" / "codebase-review-system"),
        (CODEX_HOME / "codebase-review-factory" / "prompts", root / "prompts" / "codebase-review-system"),
        (CODEX_HOME / "agentic-dev-system" / "scripts", root / "scripts" / "agentic-dev-system"),
        (CODEX_HOME / "codebase-review-factory" / "scripts", root / "scripts" / "codebase-review-system"),
        (CODEX_HOME / "agentic-dev-system" / "tests", root / "tests" / "agentic-dev-system"),
        (CODEX_HOME / "codebase-review-factory" / "tests", root / "tests" / "codebase-review-system"),
        (CODEX_HOME / "agentic-dev-system" / "fixtures", root / "fixtures" / "agentic-dev-system"),
        (CODEX_HOME / "codebase-review-factory" / "fixtures", root / "fixtures" / "codebase-review-system"),
        (CODEX_HOME / "agentic-dev-system", root / "modules" / "agentic-dev-system"),
        (CODEX_HOME / "codebase-review-factory", root / "modules" / "codebase-review-system"),
        (WORKSPACE / "scripts" / "package_agentic_system.py", root / "tools" / "package_agentic_system.py"),
        (WORKSPACE / "scripts" / "package_reviewer_upload.py", root / "tools" / "package_reviewer_upload.py"),
        (WORKSPACE / "scripts" / "run_agentic_review_refactor.sh", root / "tools" / "run_agentic_review_refactor.sh"),
    ]

    # Original layout, but without hidden top-level names.
    original_sources = [
        (CODEX_HOME / "AGENTS.md", root / "original-layout" / "dot-codex" / "AGENTS.md"),
        (CODEX_HOME / "config.toml", root / "original-layout" / "dot-codex" / "config.toml"),
        (CODEX_HOME / "hooks.json", root / "original-layout" / "dot-codex" / "hooks.json"),
        (CODEX_HOME / "agents", root / "original-layout" / "dot-codex" / "agents"),
        (CODEX_HOME / "hooks", root / "original-layout" / "dot-codex" / "hooks"),
        (CODEX_HOME / "manual-workflows", root / "original-layout" / "dot-codex" / "manual-workflows"),
        (CODEX_HOME / "skills", root / "original-layout" / "dot-codex" / "skills"),
        (CODEX_HOME / "superpowers" / "skills", root / "original-layout" / "dot-codex" / "superpowers" / "skills"),
        (CODEX_HOME / "agentic-dev-system", root / "original-layout" / "dot-codex" / "agentic-dev-system"),
        (CODEX_HOME / "codebase-review-factory", root / "original-layout" / "dot-codex" / "codebase-review-factory"),
        (AGENTS_HOME / "skills", root / "original-layout" / "dot-agents" / "skills"),
    ]

    for src, dst in visible_sources + original_sources:
        record_copy(src, dst, included, missing)

    write_discovery_manifest(root)
    write_reviewer_docs(root, included, missing)
    write_file_index(root)
    return included, missing


def write_reviewer_docs(root: Path, included: list[str], missing: list[str]) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    write_text(
        root / "REVIEWER_README.md",
        "# Agentic Development System Reviewer Package\n\n"
        "This archive is shaped for review, not direct installation. It exposes every relevant project category as a visible top-level directory and also includes an `original-layout/` copy of the local Codex layout without hidden top-level names.\n\n"
        "## Start Here\n\n"
        "1. `docs/ARCHITECTURE.md`\n"
        "2. `docs/CAPABILITIES.md`\n"
        "3. `docs/EXAMPLES.md`\n"
        "4. `FILE_INDEX.txt`\n"
        "5. `PACKAGE_MANIFEST.md`\n\n"
        "## Important Directories\n\n"
        "- `configs/`: `AGENTS.md`, `config.toml`, and `hooks.json`\n"
        "- `agents/`: active agent TOML files\n"
        "- `hooks/`: active hook scripts\n"
        "- `skills/`: all relevant skill trees, including custom project skills, local Codex skills, and Superpowers\n"
        "- `schemas/`: JSON schemas\n"
        "- `prompts/`: prompt templates\n"
        "- `scripts/`: executable helper scripts\n"
        "- `tests/`: validation tests\n"
        "- `fixtures/`: sample validation inputs\n"
        "- `manual-workflows/`: manual workflow docs and support scripts\n"
        "- `modules/`: complete compatibility module copies\n"
        "- `tools/run_agentic_review_refactor.sh`: one-shot repo inventory, feature-model, slice generation, and orchestration wrapper\n"
        "- `original-layout/`: review copy of the local `.codex` and `.agents` layout\n",
    )
    write_text(
        root / "PACKAGE_MANIFEST.md",
        "# Agentic Development System Upload Manifest\n\n"
        f"Generated: {now}\n\n"
        "## Included Paths\n\n"
        + "".join(f"- `{line}`\n" for line in included)
        + "\n## Missing Paths\n\n"
        + ("".join(f"- `{path}`\n" for path in missing) if missing else "- None\n")
        + "\n## Excluded Files\n\n"
        "- Timestamped backups matching `.bak-*`, `.bak.*`, `.backup.*`, or `.bak`\n"
        "- `__pycache__`\n"
        "- `.pytest_cache`\n"
        "- `.DS_Store`\n"
        "- Python bytecode files\n\n"
        "## Review Notes\n\n"
        "- `config.toml` is included because this is a review archive. It contains local paths, plugin metadata, connector IDs, and runtime settings.\n"
        "- Skill discovery symlinks were dereferenced into real directories so reviewers can inspect them without your machine's symlinks.\n"
        "- `original-layout/` mirrors the relevant local layout using visible directory names.\n",
    )


def zip_tree(source: Path, output: Path) -> None:
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file() and not excluded(path):
                archive.write(path, path.relative_to(source.parent))


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a reviewer-facing Agentic Development System upload zip.")
    parser.add_argument("--output", default=str(WORKSPACE / "agentic-development-system-review-complete.zip"))
    parser.add_argument("--keep-staging", action="store_true")
    args = parser.parse_args()

    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    if args.keep_staging:
        staging = WORKSPACE / "agentic-development-system-review-package"
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)
        build_package(staging)
        zip_tree(staging / PACKAGE_ROOT, output)
        print(staging / PACKAGE_ROOT)
    else:
        with tempfile.TemporaryDirectory(prefix="agentic-development-system-review-") as tmp:
            staging = Path(tmp)
            build_package(staging)
            zip_tree(staging / PACKAGE_ROOT, output)

    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
