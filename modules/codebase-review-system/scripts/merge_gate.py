#!/usr/bin/env python3
"""Gate and optionally merge one GitHub pull request."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path


def run_cmd(cmd, cwd=None, timeout=None):
    return subprocess.run(
        cmd,
        cwd=cwd,
        timeout=timeout,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def fail(message):
    print(f'ERROR: {message}', file=sys.stderr)
    return 1


def load_json_command(cmd, cwd=None, timeout=None):
    result = run_cmd(cmd, cwd=cwd, timeout=timeout)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout or 'command failed: ' + ' '.join(cmd))
    try:
        return json.loads(result.stdout or '{}')
    except json.JSONDecodeError as exc:
        raise RuntimeError(f'invalid JSON from {" ".join(cmd)}: {exc}') from exc


def clean_local_state(repo):
    result = run_cmd(['git', 'status', '--porcelain'], cwd=repo)
    if result.returncode:
        raise RuntimeError(result.stderr or 'git status failed')
    return result.stdout.strip() == ''


def repo_owner_name(repo):
    data = load_json_command(['gh', 'repo', 'view', '--json', 'nameWithOwner'], cwd=repo)
    value = data.get('nameWithOwner') or ''
    if '/' not in value:
        raise RuntimeError('could not resolve GitHub owner/repo')
    owner, name = value.split('/', 1)
    return owner, name


def pr_view(repo, pr):
    fields = ','.join([
        'number',
        'state',
        'isDraft',
        'mergeable',
        'mergeStateStatus',
        'reviewDecision',
        'headRefOid',
        'headRefName',
        'baseRefName',
        'url',
    ])
    cmd = ['gh', 'pr', 'view']
    if pr:
        cmd.append(str(pr))
    cmd += ['--json', fields]
    return load_json_command(cmd, cwd=repo)


def required_checks_green(repo, pr, timeout, interval):
    cmd = ['gh', 'pr', 'checks']
    if pr:
        cmd.append(str(pr))
    cmd += ['--required', '--watch', '--interval', str(interval), '--json', 'name,state,bucket']
    checks = load_json_command(cmd, cwd=repo, timeout=timeout)
    if not isinstance(checks, list):
        raise RuntimeError('gh pr checks returned non-list JSON')
    bad = []
    for check in checks:
        bucket = str(check.get('bucket') or '').lower()
        state = str(check.get('state') or '').upper()
        if bucket not in {'pass', 'skipping'} and state not in {'SUCCESS', 'SKIPPED', 'NEUTRAL'}:
            bad.append(check.get('name') or state or bucket or 'unknown')
    if bad:
        raise RuntimeError('required checks not green: ' + ', '.join(bad))
    return checks


def review_threads(repo, pr_number):
    owner, name = repo_owner_name(repo)
    query = '''
query($owner:String!, $name:String!, $number:Int!, $after:String) {
  repository(owner:$owner, name:$name) {
    pullRequest(number:$number) {
      reviewThreads(first:100, after:$after) {
        nodes {
          isResolved
          isOutdated
          comments(first:20) {
            nodes {
              body
              author { login }
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
  }
}
'''
    threads = []
    after = ''
    while True:
        cmd = [
            'gh', 'api', 'graphql',
            '-f', f'owner={owner}',
            '-f', f'name={name}',
            '-F', f'number={int(pr_number)}',
            '-f', 'query=' + query,
        ]
        if after:
            cmd += ['-f', f'after={after}']
        data = load_json_command(cmd, cwd=repo)
        page = (((data.get('data') or {}).get('repository') or {}).get('pullRequest') or {}).get('reviewThreads', {})
        threads.extend(page.get('nodes') or [])
        page_info = page.get('pageInfo') or {}
        if not page_info.get('hasNextPage'):
            return threads
        after = page_info.get('endCursor') or ''
        if not after:
            raise RuntimeError('review thread pagination missing endCursor')


def unresolved_threads(threads):
    unresolved = []
    for thread in threads:
        if thread.get('isResolved') is False and not thread.get('isOutdated'):
            unresolved.append(thread)
    return unresolved


def unresolved_must_fix_threads(threads):
    pattern = re.compile(r'\b(must[- ]?fix|p0|p1|critical|block(?:er|ing)?)\b', re.I)
    matches = []
    for thread in unresolved_threads(threads):
        comments = ((thread.get('comments') or {}).get('nodes') or [])
        if any(pattern.search(comment.get('body') or '') for comment in comments):
            matches.append(thread)
    return matches


def validate_pr(view, expected_head_sha):
    if str(view.get('state', '')).upper() != 'OPEN':
        raise RuntimeError(f'PR is not open: {view.get("state")}')
    if view.get('isDraft'):
        raise RuntimeError('PR is draft')
    if expected_head_sha and view.get('headRefOid') != expected_head_sha:
        raise RuntimeError(f'head SHA mismatch: expected {expected_head_sha}, got {view.get("headRefOid")}')
    mergeable = str(view.get('mergeable') or '').upper()
    merge_state = str(view.get('mergeStateStatus') or '').upper()
    if mergeable != 'MERGEABLE' or merge_state in {'UNKNOWN', 'DIRTY', 'BLOCKED', 'BEHIND', 'UNSTABLE'}:
        raise RuntimeError(f'PR mergeability is not clean: mergeable={mergeable} mergeStateStatus={merge_state}')
    decision = str(view.get('reviewDecision') or '').upper()
    if decision in {'CHANGES_REQUESTED', 'REVIEW_REQUIRED'}:
        raise RuntimeError(f'PR review decision blocks merge: {decision}')


def merge_command(pr, method, head_sha, delete_branch):
    flag = {'squash': '--squash', 'merge': '--merge', 'rebase': '--rebase'}[method]
    cmd = ['gh', 'pr', 'merge']
    if pr:
        cmd.append(str(pr))
    cmd += [flag, '--match-head-commit', head_sha]
    if delete_branch:
        cmd.append('--delete-branch')
    return cmd


def wait_for_review_threads_clear(repo, pr_number, timeout_seconds, poll_seconds):
    deadline = time.time() + timeout_seconds if timeout_seconds > 0 else time.time()
    while True:
        threads = review_threads(repo, pr_number)
        unresolved = unresolved_threads(threads)
        must_fix = unresolved_must_fix_threads(threads)
        if not unresolved and not must_fix:
            return
        if timeout_seconds <= 0 or time.time() >= deadline:
            if unresolved:
                raise RuntimeError(f'unresolved review threads: {len(unresolved)}')
            raise RuntimeError(f'unresolved must-fix comments: {len(must_fix)}')
        time.sleep(max(1, poll_seconds))


def parse_args():
    ap = argparse.ArgumentParser(description='Verify PR gates and optionally merge.')
    ap.add_argument('--pr', required=True, help='PR number, URL, or branch')
    ap.add_argument('--repo-path', default='.')
    ap.add_argument('--allow-merge', action='store_true')
    ap.add_argument('--no-merge', '--pr-only', dest='no_merge', action='store_true')
    ap.add_argument('--merge-method', choices=['squash', 'merge', 'rebase'], default='squash')
    ap.add_argument('--delete-branch', action='store_true')
    ap.add_argument('--expected-head-sha')
    ap.add_argument('--ci-timeout-seconds', type=int, default=1800)
    ap.add_argument('--ci-poll-seconds', type=int, default=15)
    ap.add_argument('--review-timeout-seconds', type=int, default=0)
    ap.add_argument('--dry-run', action='store_true')
    return ap.parse_args()


def main():
    args = parse_args()
    repo = Path(args.repo_path).resolve()
    try:
        if not clean_local_state(repo):
            return fail('local state is not clean')
        view = pr_view(repo, args.pr)
        validate_pr(view, args.expected_head_sha)
        required_checks_green(repo, args.pr, args.ci_timeout_seconds, args.ci_poll_seconds)
        wait_for_review_threads_clear(repo, view.get('number') or args.pr, args.review_timeout_seconds, args.ci_poll_seconds)

        if args.no_merge:
            print('merge skipped: --no-merge/--pr-only provided')
            return 0
        if not args.allow_merge:
            print('merge skipped: --allow-merge not provided')
            return 0

        cmd = merge_command(args.pr, args.merge_method, view.get('headRefOid'), args.delete_branch)
        if args.dry_run:
            print(' '.join(cmd))
            return 0
        result = run_cmd(cmd, cwd=repo)
        if result.returncode:
            return fail(result.stderr or result.stdout or 'gh pr merge failed')
        if result.stdout:
            print(result.stdout, end='')
        return 0
    except subprocess.TimeoutExpired:
        return fail('required checks timed out')
    except Exception as exc:  # noqa: BLE001 - CLI reports gate failure
        return fail(str(exc))


if __name__ == '__main__':
    raise SystemExit(main())
