#!/usr/bin/env python3
"""Gate and optionally merge one GitHub pull request."""
from __future__ import annotations

import argparse
import datetime as _dt
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
        'latestReviews',
        'comments',
        'url',
    ])
    cmd = ['gh', 'pr', 'view']
    if pr:
        cmd.append(str(pr))
    cmd += ['--json', fields]
    return load_json_command(cmd, cwd=repo)


def required_checks_green(repo, pr, timeout, interval):
    deadline = time.time() + timeout if timeout > 0 else time.time()
    while True:
        try:
            checks = load_required_checks(repo, pr)
        except RuntimeError as exc:
            if 'no checks reported' not in str(exc):
                raise
            checks = []
            pending = ['checks not reported yet']
            bad = []
        else:
            pending = []
            bad = []
            for check in checks:
                bucket = str(check.get('bucket') or '').lower()
                state = str(check.get('state') or '').upper()
                if bucket in {'pass', 'skipping'} or state in {'SUCCESS', 'SKIPPED', 'NEUTRAL'}:
                    continue
                if bucket in {'pending', 'waiting'} or state in {'PENDING', 'QUEUED', 'IN_PROGRESS', 'EXPECTED'}:
                    pending.append(check.get('name') or state or bucket or 'unknown')
                else:
                    bad.append(check.get('name') or state or bucket or 'unknown')
        if bad:
            raise RuntimeError('required checks not green: ' + ', '.join(bad))
        if not pending:
            return checks
        if timeout <= 0 or time.time() >= deadline:
            raise subprocess.TimeoutExpired(['gh', 'pr', 'checks'], timeout)
        time.sleep(max(1, interval))


def load_required_checks(repo, pr):
    try:
        return load_checks(repo, pr, required=True)
    except RuntimeError as exc:
        if 'no required checks reported' not in str(exc):
            raise
        return load_checks(repo, pr, required=False)


def load_checks(repo, pr, required):
    cmd = ['gh', 'pr', 'checks']
    if pr:
        cmd.append(str(pr))
    if required:
        cmd.append('--required')
    cmd += ['--json', 'name,state,bucket']
    checks = load_json_command(cmd, cwd=repo)
    if not isinstance(checks, list):
        raise RuntimeError('gh pr checks returned non-list JSON')
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


def summarize_threads(threads, limit=5):
    summaries = []
    for thread in threads[:limit]:
        comments = ((thread.get('comments') or {}).get('nodes') or [])
        body = ''
        author = 'unknown'
        if comments:
            comment = comments[-1]
            author = (((comment.get('author') or {}).get('login')) or 'unknown')
            body = (comment.get('body') or '').splitlines()[0].strip()
        location = thread.get('path') or 'unknown path'
        line = thread.get('line') or thread.get('startLine')
        if line:
            location = f'{location}:{line}'
        summaries.append(f'{location} by {author}: {body[:180]}')
    if len(threads) > limit:
        summaries.append(f'... {len(threads) - limit} more')
    return '; '.join(summaries)


def validate_pr(view, expected_head_sha, final=True, allow_review_required=False):
    if str(view.get('state', '')).upper() != 'OPEN':
        raise RuntimeError(f'PR is not open: {view.get("state")}')
    if view.get('isDraft'):
        raise RuntimeError('PR is draft')
    if expected_head_sha and view.get('headRefOid') != expected_head_sha:
        raise RuntimeError(f'head SHA mismatch: expected {expected_head_sha}, got {view.get("headRefOid")}')
    mergeable = str(view.get('mergeable') or '').upper()
    merge_state = str(view.get('mergeStateStatus') or '').upper()
    blocking_states = {'DIRTY', 'BLOCKED', 'BEHIND'}
    if final:
        blocking_states |= {'UNKNOWN', 'UNSTABLE'}
    if mergeable != 'MERGEABLE' or merge_state in blocking_states:
        raise RuntimeError(f'PR mergeability is not clean: mergeable={mergeable} mergeStateStatus={merge_state}')
    decision = str(view.get('reviewDecision') or '').upper()
    blocked_decisions = {'CHANGES_REQUESTED', 'REVIEW_REQUIRED'}
    if allow_review_required:
        blocked_decisions.remove('REVIEW_REQUIRED')
    if decision in blocked_decisions:
        raise RuntimeError(f'PR review decision blocks merge: {decision}')


def parse_github_time(value):
    if not value:
        return None
    normalized = value.replace('Z', '+00:00')
    return _dt.datetime.fromisoformat(normalized)


def require_review_after(view, requested_at):
    if not requested_at:
        return
    requested = parse_github_time(requested_at)
    for review in view.get('latestReviews') or []:
        state = str(review.get('state') or '').upper()
        if state in {'PENDING', 'DISMISSED'}:
            continue
        submitted = parse_github_time(review.get('submittedAt'))
        if submitted and submitted >= requested:
            if state == 'CHANGES_REQUESTED':
                raise RuntimeError('review submitted after request blocks merge: CHANGES_REQUESTED')
            return
    comment = completed_codex_review_comment_after(view, requested)
    if comment:
        blocking = blocking_review_comments_after(view, requested)
        if blocking:
            raise RuntimeError('blocking review comments after requested review: ' + ', '.join(blocking))
        return
    raise RuntimeError('no completed review submitted after requested review')


def comment_created_at(comment):
    return parse_github_time(comment.get('createdAt'))


def comment_author_login(comment):
    return str(((comment.get('author') or {}).get('login')) or '')


def completed_codex_review_comment_after(view, requested):
    for comment in view.get('comments') or []:
        created = comment_created_at(comment)
        if not created or created < requested:
            continue
        author = comment_author_login(comment).lower()
        body = comment.get('body') or ''
        if 'codex' in author and 'codex review:' in body.lower():
            return comment
    return None


def blocking_review_comments_after(view, requested):
    pattern = re.compile(r'\b(must[- ]?fix|p0|p1|critical|block(?:er|ing)?|changes requested)\b', re.I)
    blocking = []
    for comment in view.get('comments') or []:
        created = comment_created_at(comment)
        if not created or created < requested:
            continue
        body = comment.get('body') or ''
        if pattern.search(body):
            blocking.append(comment_author_login(comment) or 'unknown')
    return blocking


def wait_for_required_review(repo, pr, requested_at, timeout_seconds, poll_seconds, expected_head_sha):
    deadline = time.time() + timeout_seconds if timeout_seconds > 0 else time.time()
    while True:
        view = pr_view(repo, pr)
        validate_pr(view, expected_head_sha, final=True, allow_review_required=True)
        try:
            require_review_after(view, requested_at)
            return view
        except RuntimeError as exc:
            if 'no completed review submitted after requested review' not in str(exc):
                raise
            if timeout_seconds <= 0 or time.time() >= deadline:
                raise
        time.sleep(max(1, poll_seconds))


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
                detail = summarize_threads(unresolved)
                raise RuntimeError(f'unresolved review threads: {len(unresolved)}' + (f': {detail}' if detail else ''))
            detail = summarize_threads(must_fix)
            raise RuntimeError(f'unresolved must-fix comments: {len(must_fix)}' + (f': {detail}' if detail else ''))
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
    ap.add_argument('--review-timeout-seconds', type=int, default=600)
    ap.add_argument('--review-thread-timeout-seconds', type=int, default=0)
    ap.add_argument('--require-review-after')
    ap.add_argument('--dry-run', action='store_true')
    return ap.parse_args()


def main():
    args = parse_args()
    repo = Path(args.repo_path).resolve()
    try:
        if not clean_local_state(repo):
            return fail('local state is not clean')
        view = pr_view(repo, args.pr)
        validate_pr(view, args.expected_head_sha, final=False, allow_review_required=bool(args.require_review_after))
        required_checks_green(repo, args.pr, args.ci_timeout_seconds, args.ci_poll_seconds)
        view = pr_view(repo, args.pr)
        validate_pr(view, args.expected_head_sha, final=True, allow_review_required=bool(args.require_review_after))
        if args.require_review_after:
            view = wait_for_required_review(
                repo,
                args.pr,
                args.require_review_after,
                args.review_timeout_seconds,
                args.ci_poll_seconds,
                args.expected_head_sha,
            )
        wait_for_review_threads_clear(repo, view.get('number') or args.pr, args.review_thread_timeout_seconds, args.ci_poll_seconds)

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
