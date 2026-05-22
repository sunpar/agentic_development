#!/usr/bin/env python3
"""Create an isolated git worktree for one review/refactor slice."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path


def run_capture(cmd):
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def repo_root():
    result = run_capture(['git', 'rev-parse', '--show-toplevel'])
    if result.returncode:
        return None
    return Path(result.stdout.strip())


def load_slice(plan_path, slice_id):
    plan = json.loads(Path(plan_path).expanduser().read_text(encoding='utf-8'))
    for item in plan.get('slices', []):
        if item.get('id') == slice_id:
            return item
    raise KeyError(f'slice not found: {slice_id}')


def branch_exists(branch):
    return subprocess.call(['git', 'show-ref', '--verify', f'refs/heads/{branch}'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def valid_branch_name(branch):
    return subprocess.call(['git', 'check-ref-format', '--branch', branch], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def sanitize_worktree_name(branch):
    return re.sub(r'[^a-zA-Z0-9_.-]', '-', branch).strip('-') or 'slice-worktree'


def run(cmd, dry_run):
    print('CMD:', ' '.join(cmd))
    if dry_run:
        return 0
    return subprocess.call(cmd)


def main():
    ap = argparse.ArgumentParser(description='Create or reuse one slice worktree.')
    ap.add_argument('slice_plan')
    ap.add_argument('slice_id')
    ap.add_argument('--branch')
    ap.add_argument('--worktree-dir', default=str(Path.home() / '.codex' / 'worktrees'))
    ap.add_argument('--base-ref', default='HEAD')
    ap.add_argument('--reuse', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    root = repo_root()
    if not root:
        print('ERROR: not inside git repo')
        return 2

    try:
        item = load_slice(args.slice_plan, args.slice_id)
    except KeyError as exc:
        print(f'ERROR: {exc}')
        return 1

    branch = args.branch or item.get('branch') or f'codebase-review/{args.slice_id.lower()}'
    if not valid_branch_name(branch):
        print(f'ERROR: invalid branch name: {branch}')
        return 2

    worktree_dir = Path(args.worktree_dir).expanduser()
    worktree_path = worktree_dir / sanitize_worktree_name(branch)
    existing_branch = branch_exists(branch)

    if worktree_path.exists():
        if not args.reuse:
            print(f'ERROR: worktree already exists at {worktree_path}')
            return 2
        print(f'INFO: reusing existing worktree at {worktree_path}')
    else:
        if args.dry_run:
            print(f'DRY-RUN: would create directory {worktree_dir}')
        else:
            worktree_dir.mkdir(parents=True, exist_ok=True)
        if existing_branch and not args.reuse:
            print(f'ERROR: branch already exists: {branch}')
            return 2
        base = os.path.expanduser(args.base_ref)
        if existing_branch:
            cmd = ['git', 'worktree', 'add', str(worktree_path), branch]
        else:
            cmd = ['git', 'worktree', 'add', '-b', branch, str(worktree_path), base]
        if run(cmd, args.dry_run):
            print('ERROR: failed to create worktree')
            return 3

    print(f'NEXT: run slice workflow in {worktree_path}')
    print(f'NEXT: branch: {branch}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
