#!/usr/bin/env python3
"""Merge all task branches for a wave and run verification commands."""
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, text=True, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def split_command(cmd: str):
    return shlex.split(cmd)


def collect_task_list(plan, wave):
    tasks = {}
    for t in plan.get("tasks", []):
        if int(t.get("wave", -1)) == wave:
            tasks[t.get("id")] = t
    wave_block = None
    for w in plan.get("waves", []):
        if int(w.get("wave", -1)) == wave:
            wave_block = w
            break
    order = wave_block.get("task_ids", []) if wave_block else []
    return [tasks[i] for i in order if i in tasks]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--plan", required=True)
    p.add_argument("--wave", required=True, type=int)
    p.add_argument("--integration-branch", default=None)
    p.add_argument("--workdir", default=".")
    p.add_argument("--dry-run", action="store_true")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--merge", action="store_true", help="Execute merges. Required for merge side effects.")
    mode.add_argument("--no-merge", action="store_true", help="Explicitly skip merge side effects and print the plan.")
    args = p.parse_args()

    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    workdir = Path(args.workdir).resolve()
    tasks = collect_task_list(plan, args.wave)
    if not tasks:
        print("ERROR: no tasks in wave")
        return 1

    integration = args.integration_branch or f"wave-{args.wave}-integration"
    baseline = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=workdir)
    if baseline.returncode != 0:
        print("ERROR: not in git repo")
        return 2
    head = baseline.stdout.strip()

    print(f"MERGE WAVE {args.wave} into {integration} from base {head}")
    if not args.merge:
        reason = "DRY-RUN" if args.dry_run else "MERGE DISABLED"
        print(f"{reason}: pass --merge to execute merges")
        for t in tasks:
            print(f"{reason}: would merge --no-ff {t.get('branch')}")
            for cmd in t.get("verification_commands", []):
                print(f"{reason}: would verify: {cmd}")
        return 0

    if args.dry_run:
        print(f"DRY-RUN: git switch/create {integration}")
        for t in tasks:
            print(f"DRY-RUN: git merge --no-ff {t.get('branch')}")
            for cmd in t.get("verification_commands", []):
                print(f"DRY-RUN: verify: {cmd}")
        return 0

    if run(["git", "checkout", "-b", integration, head], cwd=workdir).returncode != 0:
        if run(["git", "checkout", integration], cwd=workdir).returncode != 0:
            print(f"ERROR: cannot prepare integration branch {integration}")
            return 3

    for task in tasks:
        branch = task.get("branch")
        if not branch:
            print(f"ERROR: task {task.get('id')} has no branch")
            return 4
        rc = run(["git", "merge", "--no-ff", branch], cwd=workdir)
        if rc.returncode != 0:
            print(f"ERROR: merge failed for {branch}")
            print(rc.stderr)
            return 5
        for cmd in task.get("verification_commands", []):
            out = run(split_command(cmd), cwd=workdir)
            if out.returncode != 0:
                print(f"ERROR: verification failed after {branch}: {cmd}")
                print(out.stderr)
                return 6

    print("SUMMARY: wave merged successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
