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
            print((root / 'view.json').read_text())
            raise SystemExit(0)
        if args[:2] == ['pr', 'checks']:
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

    def test_ci_poll_seconds_is_passed_to_gh_interval(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            fake, env = setup_fake_environment(td)
            result = run([PY, str(SCRIPT), '--pr', '123', '--repo-path', str(repo), '--allow-merge', '--ci-poll-seconds', '7'], env=env)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn('pr checks 123 --required --watch --interval 7 --json name,state,bucket', (fake / 'calls.log').read_text())


if __name__ == '__main__':
    unittest.main()
