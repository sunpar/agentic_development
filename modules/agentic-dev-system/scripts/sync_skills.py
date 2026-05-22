#!/usr/bin/env python3
"""Synchronize local skill discovery for the Agentic Development System."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil


def discover_skill_dirs(src: Path) -> list[str]:
    out = []
    if not src.exists():
        return out
    for child in sorted(p for p in src.iterdir() if p.is_dir()):
        if (child / "SKILL.md").exists():
            out.append(child.name)
    return out


def ensure_link(src: Path, dst: Path, dry_run: bool) -> int:
    if dst.exists() or dst.is_symlink():
        current = Path(os.path.realpath(dst))
        if dst.is_symlink() and current == src:
            print(f"OK: existing symlink already points to {src}")
            return 0
        backup = backup_path(dst)
        kind = "symlink" if dst.is_symlink() else "non-symlink"
        if dry_run:
            print(f"DRY-RUN: would move existing {kind} {dst} to {backup}")
            print(f"DRY-RUN: would create symlink {dst} -> {src}")
            return 0
        if dst.is_symlink():
            dst.rename(backup)
        else:
            shutil.move(str(dst), str(backup))
        print(f"BACKUP: moved existing {kind} {dst} to {backup}")

    if dry_run:
        print(f"DRY-RUN: would create symlink {dst} -> {src}")
        return 0

    dst.symlink_to(src)
    print(f"LINK: {dst} -> {src}")
    return 0


def backup_path(path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    candidate = path.with_name(f"{path.name}.backup.{stamp}")
    counter = 1
    while candidate.exists() or candidate.is_symlink():
        candidate = path.with_name(f"{path.name}.backup.{stamp}.{counter}")
        counter += 1
    return candidate


def validate_discovery(dst: Path) -> int:
    if not dst.exists():
        print(f"ERROR: {dst} missing")
        return 1
    src = Path(os.path.realpath(dst))
    discovered = discover_skill_dirs(src)
    if not discovered:
        print(f"WARNING: no SKILL.md files found under {src}")
        return 1
    print(f"DISCOVERED: {len(discovered)} skills")
    for name in discovered:
        print(f" - {name}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--check", action="store_true", help="Only validate the existing discovery link.")
    parser.add_argument("--check-superpowers", action="store_true", help="Only validate the Superpowers discovery link.")
    parser.add_argument("--codex-dir", default=str(Path.home() / ".codex"))
    parser.add_argument("--agents-skills-dir", default=str(Path.home() / ".agents" / "skills"))
    args = parser.parse_args()

    codex_home = Path(args.codex_dir).expanduser()
    skills_root = codex_home / "agentic-dev-system" / "skills"
    agents_root = Path(args.agents_skills_dir).expanduser()
    link = agents_root / "agentic-dev-system"

    if args.check_superpowers:
        return validate_discovery(agents_root / "superpowers")

    if not skills_root.exists():
        print(f"ERROR: source skills missing at {skills_root}")
        return 2

    if args.check:
        return validate_discovery(link)

    if args.dry_run:
        if not agents_root.exists():
            print(f"DRY-RUN: would create directory {agents_root}")
    else:
        agents_root.mkdir(parents=True, exist_ok=True)
    if ensure_link(skills_root, link, args.dry_run):
        return 1
    if args.dry_run:
        print("DRY-RUN: skipped discovery validation because link is virtual")
        return 0
    return validate_discovery(link)


if __name__ == "__main__":
    raise SystemExit(main())
