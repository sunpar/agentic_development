#!/usr/bin/env python3
"""Create a clean zip for the consolidated Agentic Development System."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import shutil
import tempfile
import zipfile
from pathlib import Path


HOME = Path.home()
CODEX_HOME = HOME / ".codex"
AGENTS_HOME = HOME / ".agents"
WORKSPACE = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = "agentic-development-system"

EXCLUDE_NAMES = {
    ".DS_Store",
    ".pytest_cache",
    "__pycache__",
}
EXCLUDE_SUFFIXES = {
    ".pyc",
    ".pyo",
}


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


def build_package(staging: Path) -> tuple[list[str], list[str]]:
    root = staging / PACKAGE_ROOT
    included: list[str] = []
    missing: list[str] = []

    sources = [
        (CODEX_HOME / "agentic-dev-system" / "README.md", root / "README.md"),
        (CODEX_HOME / "agentic-dev-system" / "docs", root / "docs"),
        (CODEX_HOME / "AGENTS.md", root / ".codex" / "AGENTS.md"),
        (CODEX_HOME / "config.toml", root / ".codex" / "config.toml"),
        (CODEX_HOME / "hooks.json", root / ".codex" / "hooks.json"),
        (CODEX_HOME / "agents", root / ".codex" / "agents"),
        (CODEX_HOME / "hooks", root / ".codex" / "hooks"),
        (CODEX_HOME / "manual-workflows", root / ".codex" / "manual-workflows"),
        (CODEX_HOME / "skills" / "manual-workflow-loader", root / ".codex" / "skills" / "manual-workflow-loader"),
        (CODEX_HOME / "agentic-dev-system", root / ".codex" / "agentic-dev-system"),
        (CODEX_HOME / "codebase-review-factory", root / ".codex" / "codebase-review-factory"),
        (AGENTS_HOME / "skills", root / ".agents" / "skills"),
        (WORKSPACE / "scripts" / "package_agentic_system.py", root / "tools" / "package_agentic_system.py"),
    ]

    for src, dst in sources:
        if copy_path(src, dst):
            included.append(str(src))
        else:
            missing.append(str(src))

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    write_text(
        root / "PACKAGE_MANIFEST.md",
        "# Agentic Development System Package Manifest\n\n"
        f"Generated: {now}\n\n"
        "## Included Source Paths\n\n"
        + "".join(f"- `{path}`\n" for path in included)
        + "\n## Missing Source Paths\n\n"
        + ("".join(f"- `{path}`\n" for path in missing) if missing else "- None\n")
        + "\n## Excluded Files\n\n"
        "- Timestamped backups matching `.bak-*`, `.bak.*`, `.backup.*`, or `.bak`\n"
        "- `__pycache__`\n"
        "- `.pytest_cache`\n"
        "- `.DS_Store`\n"
        "- Python bytecode files\n"
        "\n## Compatibility Notes\n\n"
        "- Canonical docs are in `docs/` and mirrored from `.codex/agentic-dev-system/docs/`.\n"
        "- Runtime compatibility modules are under `.codex/agentic-dev-system/` and `.codex/codebase-review-factory/`.\n"
        "- Skill discovery symlinks should be recreated from `docs/SYMLINK_MANIFEST.md` after extraction.\n",
    )

    write_text(
        root / "INSTALL_NOTES.md",
        "# Install And Review Notes\n\n"
        "This zip is a consolidated review package, not an automatic installer.\n\n"
        "1. Review `docs/ARCHITECTURE.md`, `docs/CAPABILITIES.md`, and `docs/EXAMPLES.md`.\n"
        "2. Review `.codex/config.toml` before sharing or applying it elsewhere; it contains local trust paths, plugin metadata, app connector IDs, and runtime paths.\n"
        "3. Copy `.codex/agentic-dev-system` and `.codex/codebase-review-factory` into a target `~/.codex` only after backing up existing files.\n"
        "4. Copy `.codex/agents`, `.codex/hooks`, `.codex/manual-workflows`, `.codex/skills/manual-workflow-loader`, `AGENTS.md`, `config.toml`, and `hooks.json` only after reviewing local differences.\n"
        "5. Run the validation commands in `docs/EXAMPLES.md` before using the system on a project repository.\n",
    )
    return included, missing


def zip_tree(source: Path, output: Path) -> None:
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file() and not excluded(path):
                archive.write(path, path.relative_to(source.parent))


def main() -> int:
    parser = argparse.ArgumentParser(description="Create the Agentic Development System zip package.")
    parser.add_argument("--output", default=str(WORKSPACE / "agentic-development-system.zip"))
    parser.add_argument("--keep-staging", action="store_true")
    args = parser.parse_args()

    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    if args.keep_staging:
        staging = WORKSPACE / "agentic-development-system-package"
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)
        build_package(staging)
        zip_tree(staging / PACKAGE_ROOT, output)
        print(staging / PACKAGE_ROOT)
    else:
        with tempfile.TemporaryDirectory(prefix="agentic-development-system-") as tmp:
            staging = Path(tmp)
            build_package(staging)
            zip_tree(staging / PACKAGE_ROOT, output)

    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
