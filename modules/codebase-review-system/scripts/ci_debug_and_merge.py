#!/usr/bin/env python3
import argparse, subprocess


def run(c):
    print('+', ' '.join(c))
    return subprocess.run(c).returncode


def main():
    ap = argparse.ArgumentParser(description='Inspect PR checks and optionally run a manual gh merge command wrapper.')
    ap.add_argument('--allow-merge', action='store_true', help='opt in to printing/running the manual merge command after CI checks are inspected')
    ap.add_argument('--no-merge', '--pr-only', dest='no_merge', action='store_true', help='explicitly opt out of merging, even if --allow-merge is present')
    ap.add_argument('--merge-method', choices=['squash', 'merge', 'rebase'], default='squash')
    ap.add_argument('--pr', help='PR number, URL, or branch to inspect/merge; defaults to current branch PR')
    ap.add_argument('--auto-merge', action='store_true')
    ap.add_argument('--delete-branch', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    checks = ['gh', 'pr', 'checks']
    if args.pr:
        checks.append(args.pr)
    checks.append('--watch=false')
    if args.dry_run:
        print(' '.join(checks))
    else:
        rc = run(checks)
        if rc:
            return rc

    if args.no_merge:
        print('merge skipped: --no-merge/--pr-only provided')
        return 0
    if not args.allow_merge:
        print('merge skipped: --allow-merge not provided')
        return 0

    print('merge execution moved to merge_gate.py; this CI helper no longer performs PR merges')
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
