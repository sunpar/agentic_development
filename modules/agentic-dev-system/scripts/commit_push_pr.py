#!/usr/bin/env python3
"""Commit staged changes, push, and create/update a PR using gh."""
from __future__ import annotations

import argparse
import os
import subprocess
import tempfile

PROTECTED_BRANCHES = {"main", "master", "trunk", "develop"}


def run(cmd: list[str], check=True, capture=False):
    kwargs = {"text": True}
    if capture:
        return subprocess.run(cmd, **kwargs, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check)
    return subprocess.run(cmd, **kwargs, check=check)


def git_branch():
    return subprocess.check_output(["git", "branch", "--show-current"], text=True).strip()


def git_status():
    out = run(["git", "status", "--short"], capture=True)
    return out.stdout.strip()


def staged_files():
    out = run(["git", "diff", "--name-only", "--cached"], capture=True)
    return [line for line in out.stdout.splitlines() if line.strip()]


def would_stage_files():
    tracked = run(["git", "diff", "--name-only"], capture=True)
    untracked = run(["git", "ls-files", "--others", "--exclude-standard"], capture=True)
    files = []
    for line in tracked.stdout.splitlines() + untracked.stdout.splitlines():
        if line.strip() and line not in files:
            files.append(line)
    return files


def has_gh():
    return subprocess.call(["which", "gh"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def gh_auth_ok():
    if not has_gh():
        return False
    return subprocess.call(["gh", "auth", "status"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def summarize(files):
    head = files[0] if files else "no"
    if len(files) <= 1:
        return f"chore({head}): implement task updates"
    return f"chore: implement updates in {len(files)} files"


def current_pr(branch: str):
    cp = run(["gh", "pr", "list", "--head", branch, "--json", "number,url", "--limit", "1"], check=False, capture=True)
    if cp.returncode != 0:
        return None
    import json
    j = json.loads(cp.stdout)
    if isinstance(j, list) and j:
        return j[0].get("url")
    if isinstance(j, dict):
        return j.get("url")
    return None


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--stage-all", action="store_true")
    p.add_argument("--force-protected", action="store_true")
    p.add_argument("--message")
    p.add_argument("--pr-title")
    p.add_argument("--pr-body")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    b = git_branch()
    if b in PROTECTED_BRANCHES and not args.force_protected:
        print(f"ERROR: protected branch '{b}' blocked")
        return 2

    if not args.dry_run and not gh_auth_ok():
        print("ERROR: gh not installed or unauthenticated")
        return 3

    st = git_status()
    print("git status:")
    print(st or "(clean)")

    files = staged_files()
    if args.stage_all:
        cmd = ["git", "add", "-A"]
        print("CMD:", " ".join(cmd))
        if args.dry_run:
            files = sorted(set(files + would_stage_files()))
            print("DRY-RUN: would stage:")
            for path in files:
                print(f" - {path}")
        else:
            run(cmd)
            files = staged_files()

    if not files:
        print("ERROR: nothing staged")
        return 2

    msg = args.message or summarize(files)
    if args.dry_run:
        print(f"DRY-RUN: would commit message '{msg}'")
    else:
        run(["git", "commit", "-m", msg])

    if args.dry_run:
        print(f"DRY-RUN: would push branch {b}")
        print("DRY-RUN: would create or update PR if needed")
        return 0
    else:
        run(["git", "push", "-u", "origin", b])

    pr_url = current_pr(b)
    if pr_url:
        print(f"INFO: existing PR {pr_url}")
        if args.pr_body:
            if args.dry_run:
                print("DRY-RUN: would update PR body")
            else:
                run(["gh", "pr", "edit", pr_url, "--body-file", args.pr_body])
        return 0

    title = args.pr_title or msg
    body = args.pr_body
    if args.dry_run:
        print(f"DRY-RUN: would create PR title='{title}'")
        return 0

    if body:
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as tf:
            with open(body, "r", encoding="utf-8") as src:
                tf.write(src.read())
            body_file = tf.name
    else:
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as tf:
            tf.write("### Summary\n")
            tf.write("- Scope: task implementation\n")
            tf.write("- Tests: run locally\n")
            body_file = tf.name

    result = run(["gh", "pr", "create", "--title", title, "--body-file", body_file], capture=False, check=False)
    if result.returncode != 0:
        print("ERROR: PR create failed")
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
