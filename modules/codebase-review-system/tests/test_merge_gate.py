import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'merge_gate.py'
PY = sys.executable


def run(cmd, cwd=None, env=None):
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def git(cwd, *args):
    result = run(['git', *args], cwd=cwd)
    if result.returncode:
        raise AssertionError(result.stderr or result.stdout)
    return result


def make_repo(td):
    repo = Path(td) / 'repo'
    repo.mkdir()
    git(repo, 'init', '-b', 'main')
    git(repo, 'config', 'user.email', 'test@example.com')
    git(repo, 'config', 'user.name', 'Test User')
    (repo / 'x.txt').write_text('x\n')
    git(repo, 'add', '.')
    git(repo, 'commit', '-m', 'initial')
    return repo


def write_fake_gh(bin_dir):
    gh = Path(bin_dir) / 'gh'
    gh.write_text('#!/usr/bin/env python3\n' + textwrap.dedent(r'''
        import json, os, pathlib, sys
        root = pathlib.Path(os.environ['GH_FAKE_DIR'])
        args = sys.argv[1:]
        (root / 'calls.log').open('a').write(' '.join(args) + '\n')
        if args[:2] == ['repo', 'view']:
            print(json.dumps({'nameWithOwner': 'owner/repo'}))
            raise SystemExit(0)
        if args[:2] == ['pr', 'view']:
            views = root / 'views.json'
            if views.exists():
                count_file = root / 'view-count.txt'
                count = int(count_file.read_text()) if count_file.exists() else 0
                items = json.loads(views.read_text())
                count_file.write_text(str(count + 1))
                print(json.dumps(items[min(count, len(items) - 1)]))
                raise SystemExit(0)
            print((root / 'view.json').read_text())
            raise SystemExit(0)
        if args[:2] == ['pr', 'checks']:
            if '--required' in args and (root / 'no-required-checks').exists():
                print("no required checks reported on the 'branch' branch", file=sys.stderr)
                raise SystemExit(1)
            if '--required' not in args and (root / 'no-checks-once').exists():
                count_file = root / 'all-check-count.txt'
                count = int(count_file.read_text()) if count_file.exists() else 0
                count_file.write_text(str(count + 1))
                if count == 0:
                    print("no checks reported on the 'branch' branch", file=sys.stderr)
                    raise SystemExit(1)
            print((root / 'checks.json').read_text())
            raise SystemExit(int(os.environ.get('GH_CHECKS_RC', '0')))
        if args[:2] == ['api', 'graphql']:
            pages = root / 'threads_pages.json'
            if pages.exists():
                count_file = root / 'thread-count.txt'
                count = int(count_file.read_text()) if count_file.exists() else 0
                items = json.loads(pages.read_text())
                count_file.write_text(str(count + 1))
                print(json.dumps(items[min(count, len(items) - 1)]))
                raise SystemExit(0)
            print((root / 'threads.json').read_text())
            raise SystemExit(0)
        if args[:2] == ['pr', 'merge']:
            raise SystemExit(0)
        print('unexpected gh command: ' + ' '.join(args), file=sys.stderr)
        raise SystemExit(99)
    '''))
    gh.chmod(0o755)


def setup_fake_environment(td, view=None, checks=None, threads=None):
    fake = Path(td) / 'fake-gh'
    fake.mkdir()
    bin_dir = Path(td) / 'bin'
    bin_dir.mkdir()
    write_fake_gh(bin_dir)
    default_view = {
        'number': 123,
        'state': 'OPEN',
        'isDraft': False,
        'mergeable': 'MERGEABLE',
        'mergeStateStatus': 'CLEAN',
        'reviewDecision': 'APPROVED',
        'headRefOid': 'abc123',
        'headRefName': 'codebase-review/s1',
        'baseRefName': 'main',
        'url': 'https://example.test/pr/123',
    }
    (fake / 'view.json').write_text(json.dumps(view or default_view))
    (fake / 'checks.json').write_text(json.dumps(checks if checks is not None else [{'name': 'ci', 'bucket': 'pass', 'state': 'SUCCESS'}]))
    (fake / 'threads.json').write_text(json.dumps(threads if threads is not None else {'data': {'repository': {'pullRequest': {'reviewThreads': {'nodes': []}}}}}))
    env = {**os.environ, 'PATH': f'{bin_dir}{os.pathsep}{os.environ["PATH"]}', 'GH_FAKE_DIR': str(fake)}
    return fake, env


class TestMergeGate(unittest.TestCase):
    def test_successful_merge_uses_head_sha_and_method(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            fake, env = setup_fake_environment(td)
            result = run([PY, str(SCRIPT), '--pr', '123', '--repo-path', str(repo), '--allow-merge', '--merge-method', 'squash'], env=env)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            calls = (fake / 'calls.log').read_text()
            self.assertIn('pr merge 123 --squash --match-head-commit abc123', calls)

    def test_delete_branch_is_opt_in(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            fake, env = setup_fake_environment(td)
            result = run([PY, str(SCRIPT), '--pr', '123', '--repo-path', str(repo), '--allow-merge', '--delete-branch'], env=env)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn('--delete-branch', (fake / 'calls.log').read_text())

    def test_draft_pr_blocks_merge(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            _, env = setup_fake_environment(td, view={'number': 123, 'state': 'OPEN', 'isDraft': True, 'mergeable': 'MERGEABLE', 'mergeStateStatus': 'CLEAN', 'reviewDecision': 'APPROVED', 'headRefOid': 'abc123'})
            result = run([PY, str(SCRIPT), '--pr', '123', '--repo-path', str(repo), '--allow-merge'], env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('draft', result.stderr + result.stdout)

    def test_changes_requested_blocks_merge(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            _, env = setup_fake_environment(td, view={'number': 123, 'state': 'OPEN', 'isDraft': False, 'mergeable': 'MERGEABLE', 'mergeStateStatus': 'CLEAN', 'reviewDecision': 'CHANGES_REQUESTED', 'headRefOid': 'abc123'})
            result = run([PY, str(SCRIPT), '--pr', '123', '--repo-path', str(repo), '--allow-merge'], env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('CHANGES_REQUESTED', result.stderr + result.stdout)

    def test_failed_required_check_blocks_merge(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            _, env = setup_fake_environment(td, checks=[{'name': 'ci', 'bucket': 'fail', 'state': 'FAILURE'}])
            result = run([PY, str(SCRIPT), '--pr', '123', '--repo-path', str(repo), '--allow-merge'], env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('required checks not green', result.stderr + result.stdout)

    def test_unresolved_review_thread_blocks_merge(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            threads = {'data': {'repository': {'pullRequest': {'reviewThreads': {'nodes': [{'isResolved': False, 'isOutdated': False, 'comments': {'nodes': [{'body': 'must fix this'}]}}]}}}}}
            _, env = setup_fake_environment(td, threads=threads)
            result = run([PY, str(SCRIPT), '--pr', '123', '--repo-path', str(repo), '--allow-merge'], env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('unresolved review threads', result.stderr + result.stdout)

    def test_paginated_unresolved_review_thread_blocks_merge(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            fake, env = setup_fake_environment(td)
            pages = [
                {'data': {'repository': {'pullRequest': {'reviewThreads': {'nodes': [], 'pageInfo': {'hasNextPage': True, 'endCursor': 'cursor-1'}}}}}},
                {'data': {'repository': {'pullRequest': {'reviewThreads': {'nodes': [{'isResolved': False, 'isOutdated': False, 'comments': {'nodes': [{'body': 'must fix later page'}]}}], 'pageInfo': {'hasNextPage': False, 'endCursor': None}}}}}},
            ]
            (fake / 'threads_pages.json').write_text(json.dumps(pages))
            result = run([PY, str(SCRIPT), '--pr', '123', '--repo-path', str(repo), '--allow-merge'], env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('unresolved review threads', result.stderr + result.stdout)
            self.assertEqual((fake / 'thread-count.txt').read_text(), '2')

    def test_dirty_repo_blocks_merge(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            (repo / 'dirty.txt').write_text('dirty\n')
            _, env = setup_fake_environment(td)
            result = run([PY, str(SCRIPT), '--pr', '123', '--repo-path', str(repo), '--allow-merge'], env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('local state is not clean', result.stderr + result.stdout)

    def test_stale_head_blocks_merge(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            _, env = setup_fake_environment(td)
            result = run([PY, str(SCRIPT), '--pr', '123', '--repo-path', str(repo), '--allow-merge', '--expected-head-sha', 'other'], env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('head SHA mismatch', result.stderr + result.stdout)

    def test_unknown_mergeability_blocks_merge(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            _, env = setup_fake_environment(td, view={'number': 123, 'state': 'OPEN', 'isDraft': False, 'mergeable': 'UNKNOWN', 'mergeStateStatus': 'UNKNOWN', 'reviewDecision': 'APPROVED', 'headRefOid': 'abc123'})
            result = run([PY, str(SCRIPT), '--pr', '123', '--repo-path', str(repo), '--allow-merge'], env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('mergeability', result.stderr + result.stdout)

    def test_ci_poll_seconds_uses_json_polling_without_watch(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            fake, env = setup_fake_environment(td)
            result = run([PY, str(SCRIPT), '--pr', '123', '--repo-path', str(repo), '--allow-merge', '--ci-poll-seconds', '7'], env=env)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            calls = (fake / 'calls.log').read_text()
            self.assertIn('pr checks 123 --required --json name,state,bucket', calls)
            self.assertNotIn('--watch', calls)

    def test_no_required_checks_falls_back_to_all_pr_checks(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            fake, env = setup_fake_environment(td)
            (fake / 'no-required-checks').write_text('1')
            result = run([PY, str(SCRIPT), '--pr', '123', '--repo-path', str(repo), '--allow-merge'], env=env)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            calls = (fake / 'calls.log').read_text()
            self.assertIn('pr checks 123 --required --json name,state,bucket', calls)
            self.assertIn('pr checks 123 --json name,state,bucket', calls)

    def test_transient_no_checks_reported_is_polled_after_pr_creation(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            fake, env = setup_fake_environment(td)
            (fake / 'no-required-checks').write_text('1')
            (fake / 'no-checks-once').write_text('1')
            result = run([
                PY,
                str(SCRIPT),
                '--pr',
                '123',
                '--repo-path',
                str(repo),
                '--allow-merge',
                '--ci-timeout-seconds',
                '2',
                '--ci-poll-seconds',
                '1',
            ], env=env)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual((fake / 'all-check-count.txt').read_text(), '2')

    def test_unstable_merge_state_before_checks_is_rechecked_after_ci(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            fake, env = setup_fake_environment(td)
            unstable = {
                'number': 123,
                'state': 'OPEN',
                'isDraft': False,
                'mergeable': 'MERGEABLE',
                'mergeStateStatus': 'UNSTABLE',
                'reviewDecision': 'APPROVED',
                'headRefOid': 'abc123',
                'headRefName': 'codebase-review/s1',
                'baseRefName': 'main',
                'url': 'https://example.test/pr/123',
            }
            clean = dict(unstable)
            clean['mergeStateStatus'] = 'CLEAN'
            (fake / 'views.json').write_text(json.dumps([unstable, clean]))
            result = run([PY, str(SCRIPT), '--pr', '123', '--repo-path', str(repo), '--allow-merge'], env=env)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual((fake / 'view-count.txt').read_text(), '2')

    def test_require_review_after_blocks_when_no_review_submitted_after_request(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            view = {
                'number': 123,
                'state': 'OPEN',
                'isDraft': False,
                'mergeable': 'MERGEABLE',
                'mergeStateStatus': 'CLEAN',
                'reviewDecision': 'APPROVED',
                'headRefOid': 'abc123',
                'latestReviews': [],
            }
            _, env = setup_fake_environment(td, view=view)
            result = run([
                PY,
                str(SCRIPT),
                '--pr',
                '123',
                '--repo-path',
                str(repo),
                '--allow-merge',
                '--review-timeout-seconds',
                '0',
                '--require-review-after',
                '2026-05-22T13:00:00Z',
            ], env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('no completed review submitted after requested review', result.stderr + result.stdout)

    def test_require_review_after_accepts_later_completed_review(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            view = {
                'number': 123,
                'state': 'OPEN',
                'isDraft': False,
                'mergeable': 'MERGEABLE',
                'mergeStateStatus': 'CLEAN',
                'reviewDecision': 'APPROVED',
                'headRefOid': 'abc123',
                'latestReviews': [{
                    'author': {'login': 'codex'},
                    'state': 'COMMENTED',
                    'submittedAt': '2026-05-22T13:01:00Z',
                }],
            }
            _, env = setup_fake_environment(td, view=view)
            result = run([
                PY,
                str(SCRIPT),
                '--pr',
                '123',
                '--repo-path',
                str(repo),
                '--allow-merge',
                '--require-review-after',
                '2026-05-22T13:00:00Z',
            ], env=env)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_require_review_after_waits_through_review_required_decision(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            fake, env = setup_fake_environment(td)
            waiting = {
                'number': 123,
                'state': 'OPEN',
                'isDraft': False,
                'mergeable': 'MERGEABLE',
                'mergeStateStatus': 'CLEAN',
                'reviewDecision': 'REVIEW_REQUIRED',
                'headRefOid': 'abc123',
                'latestReviews': [],
            }
            approved = dict(waiting)
            approved['reviewDecision'] = 'APPROVED'
            approved['latestReviews'] = [{
                'author': {'login': 'codex'},
                'state': 'COMMENTED',
                'submittedAt': '2026-05-22T13:01:00Z',
            }]
            (fake / 'views.json').write_text(json.dumps([waiting, waiting, approved, approved]))
            result = run([
                PY,
                str(SCRIPT),
                '--pr',
                '123',
                '--repo-path',
                str(repo),
                '--allow-merge',
                '--review-timeout-seconds',
                '2',
                '--ci-poll-seconds',
                '1',
                '--require-review-after',
                '2026-05-22T13:00:00Z',
            ], env=env)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertGreaterEqual(int((fake / 'view-count.txt').read_text()), 3)


if __name__ == '__main__':
    unittest.main()
