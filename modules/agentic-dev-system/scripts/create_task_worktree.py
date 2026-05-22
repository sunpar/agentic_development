#!/usr/bin/env python3
"""Create an isolated git worktree for one task."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path


def repo_root():
    try:
        out = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True)
        return Path(out.strip())
    except Exception:
        return None


def load_task_from_file(path: Path):
    text = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    payload = {}
    for line in text:
        m = re.match(r"^([A-Za-z0-9_]+)\s*:\s*(.+)$", line.strip())
        if m:
            payload[m.group(1)] = m.group(2).strip(" '" + '"')
    if "id" not in payload:
        payload["id"] = path.stem
    return payload


def load_task_from_plan(plan_path: Path, task_id: str):
    data = json.loads(plan_path.read_text(encoding="utf-8"))
    for t in data.get("tasks", []):
        if t.get("id") == task_id:
            return t
    raise KeyError(f"task {task_id} not found in {plan_path}")


def branch_exists(branch: str) -> bool:
    return subprocess.call(["git", "show-ref", "--verify", f"refs/heads/{branch}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def valid_branch_name(branch: str) -> bool:
    return subprocess.call(["git", "check-ref-format", "--branch", branch], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def sanitize_worktree_name(branch: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "-", branch).strip("-") or "task-worktree"


def run(cmd: list[str], dry_run: bool):
    print("CMD:", " ".join(cmd))
    if dry_run:
        return 0
    return subprocess.call(cmd)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-file", default=None)
    parser.add_argument("--plan", default=None)
    parser.add_argument("--task-id", default=None)
    parser.add_argument("--branch", default=None)
    parser.add_argument("--worktree-dir", default=str(Path.home() / ".codex" / "worktrees"))
    parser.add_argument("--base-ref", default="HEAD")
    parser.add_argument("--reuse", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = repo_root()
    if not root:
        print("ERROR: not inside git repo")
        return 2

    if args.task_file:
        task = load_task_from_file(Path(args.task_file).expanduser())
    elif args.plan and args.task_id:
        task = load_task_from_plan(Path(args.plan).expanduser(), args.task_id)
    else:
        print("ERROR: provide either --task-file or both --plan and --task-id")
        return 2

    task_id = task.get("id")
    branch = args.branch or task.get("branch") or f"agentic-task-{task_id.lower()}"
    if not valid_branch_name(branch):
        print(f"ERROR: invalid branch name: {branch}")
        return 2
    base = os.path.expanduser(args.base_ref)

    worktree_dir = Path(args.worktree_dir).expanduser()
    worktree_path = worktree_dir / sanitize_worktree_name(branch)
    existing_branch = branch_exists(branch)

    if worktree_path.exists():
        if not args.reuse:
            print(f"ERROR: worktree already exists at {worktree_path}")
            return 2
        print(f"INFO: reusing existing worktree at {worktree_path}")
    else:
        if args.dry_run:
            print(f"DRY-RUN: would create directory {worktree_dir}")
        else:
            worktree_dir.mkdir(parents=True, exist_ok=True)
        if existing_branch and not args.reuse:
            print(f"ERROR: branch already exists: {branch}")
            return 2
        if existing_branch:
            cmd = ["git", "worktree", "add", str(worktree_path), branch]
        else:
            cmd = ["git", "worktree", "add", "-b", branch, str(worktree_path), base]
        if run(cmd, args.dry_run):
            print("ERROR: failed to create worktree")
            return 3

    print(f"NEXT: run task implementation in {worktree_path}")
    print(f"NEXT: branch: {branch}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
