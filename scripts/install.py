#!/usr/bin/env python3
"""Install the Agentic Development System into a local Codex setup."""
from __future__ import annotations

import argparse
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXCLUDE_NAMES = {".DS_Store", ".pytest_cache", "__pycache__"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo"}


def timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def excluded(path: Path) -> bool:
    name = path.name
    return (
        name in EXCLUDE_NAMES
        or any(name.endswith(suffix) for suffix in EXCLUDE_SUFFIXES)
        or ".bak-" in name
        or ".bak." in name
        or ".backup." in name
        or name.endswith(".bak")
    )


def ignore(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if excluded(Path(name))}


def log(message: str) -> None:
    print(message)


def log_action(message: str, dry_run: bool) -> None:
    log(f"[dry-run] {message}" if dry_run else message)


def backup_existing(path: Path, dry_run: bool) -> None:
    if not path.exists() and not path.is_symlink():
        return
    backup = path.with_name(path.name + ".bak." + timestamp())
    log_action(f"backup {path} -> {backup}", dry_run)
    if dry_run:
        return
    path.rename(backup)


def copy_clean(src: Path, dst: Path, dry_run: bool) -> None:
    if not src.exists():
        raise FileNotFoundError(src)
    backup_existing(dst, dry_run)
    log_action(f"copy {src} -> {dst}", dry_run)
    if dry_run:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst, ignore=ignore)
    else:
        shutil.copy2(src, dst)


def ensure_symlink_or_copy(src: Path, dst: Path, copy: bool, dry_run: bool) -> None:
    backup_existing(dst, dry_run)
    if copy:
        log_action(f"copy skills {src} -> {dst}", dry_run)
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, dst, ignore=ignore)
        return
    log_action(f"symlink {dst} -> {src}", dry_run)
    if dry_run:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(src, dst)


def install_modules(codex_home: Path, agents_home: Path, copy_skills: bool, dry_run: bool) -> None:
    agentic_dst = codex_home / "agentic-dev-system"
    review_dst = codex_home / "codebase-review-factory"
    copy_clean(ROOT / "modules" / "agentic-dev-system", agentic_dst, dry_run)
    copy_clean(ROOT / "modules" / "codebase-review-system", review_dst, dry_run)

    skills_root = agents_home / "skills"
    ensure_symlink_or_copy(agentic_dst / "skills", skills_root / "agentic-dev-system", copy_skills, dry_run)
    ensure_symlink_or_copy(review_dst / "skills", skills_root / "codebase-review-factory", copy_skills, dry_run)

    bin_dir = codex_home / "bin"
    copy_clean(ROOT / "scripts" / "run_agentic_review_refactor.sh", bin_dir / "run_agentic_review_refactor.sh", dry_run)


def install_global_config(codex_home: Path, dry_run: bool) -> None:
    copy_clean(ROOT / "configs" / "AGENTS.md", codex_home / "AGENTS.md", dry_run)
    copy_clean(ROOT / "configs" / "hooks.json", codex_home / "hooks.json", dry_run)
    copy_clean(ROOT / "configs" / "agents", codex_home / "agents", dry_run)
    copy_clean(ROOT / "configs" / "hooks", codex_home / "hooks", dry_run)


def main() -> int:
    parser = argparse.ArgumentParser(description="Install Agentic Development System into Codex.")
    parser.add_argument("--codex-home", default=str(Path.home() / ".codex"))
    parser.add_argument("--agents-home", default=str(Path.home() / ".agents"))
    parser.add_argument("--copy-skills", action="store_true", help="Copy skill directories instead of symlinking them.")
    parser.add_argument("--install-global-config", action="store_true", help="Install AGENTS.md, hooks.json, agent TOMLs, and hooks with backups.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    codex_home = Path(args.codex_home).expanduser().resolve()
    agents_home = Path(args.agents_home).expanduser().resolve()

    install_modules(codex_home, agents_home, args.copy_skills, args.dry_run)
    if args.install_global_config:
        install_global_config(codex_home, args.dry_run)
    else:
        log("skip global config; pass --install-global-config to install configs/AGENTS.md, hooks.json, agents, and hooks")

    log("install complete" if not args.dry_run else "dry run complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
