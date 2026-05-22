import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'orchestrate_slice_waves.py'
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
    (repo / 'src').mkdir()
    (repo / 'src' / 'a.txt').write_text('a\n')
    (repo / 'src' / 'b.txt').write_text('b\n')
    git(repo, 'add', '.')
    git(repo, 'commit', '-m', 'initial')
    return repo


def slice_item(sid, branch, path, deps=None):
    return {
        'id': sid,
        'feature_id': 'FEAT',
        'title': sid,
        'slice_type': 'refactor-simplify',
        'description': sid,
        'intended_behavior': 'unchanged',
        'why_this_slice_exists': 'test',
        'files_to_read': [path],
        'docs_to_read': [],
        'tests_to_read': [],
        'files_allowed_to_edit': [path],
        'files_not_allowed_to_edit': [],
        'entry_points': [path],
        'invariants': ['unchanged'],
        'non_goals': ['features'],
        'review_questions': ['safe?'],
        'refactor_targets': ['simplify'],
        'verification_commands': ['python3 -c "print(123)"'],
        'expected_pr_size': {'max_files_changed': 2, 'max_lines_changed_soft': 80},
        'dependencies': deps or [],
        'parallel_conflicts': [],
        'risk': 'low',
        'risk_notes': [],
        'acceptance_criteria': ['verification passes'],
        'branch': branch,
        'pr_title': f'[codebase-review] {sid}',
        'review_focus': ['scope'],
    }


def write_plan(path, slices, waves):
    path.write_text(json.dumps({'slices': slices, 'waves': waves}, indent=2))


def fake_codex_bin(bin_dir, body):
    codex = Path(bin_dir) / 'codex'
    codex.write_text('#!/usr/bin/env python3\n' + textwrap.dedent(body))
    codex.chmod(0o755)


def fake_gh_bin(bin_dir, fake_dir):
    gh = Path(bin_dir) / 'gh'
    gh.write_text('#!/usr/bin/env python3\n' + textwrap.dedent(f"""
        import json, pathlib, sys
        root = pathlib.Path({str(fake_dir)!r})
        args = sys.argv[1:]
        (root / 'gh-calls.log').open('a').write(' '.join(args) + '\\n')
        if args[:2] == ['auth', 'status']:
            raise SystemExit(0)
        if args[:2] == ['pr', 'view']:
            branch = args[2] if len(args) > 2 else ''
            after_create = root / 'after-create'
            if not after_create.exists():
                raise SystemExit(1)
            print(json.dumps({{
                'number': 123,
                'headRefName': branch,
                'baseRefName': (root / 'base.txt').read_text().strip(),
                'headRefOid': 'abc123',
                'body': (root / 'body.txt').read_text(),
                'state': 'OPEN',
            }}))
            raise SystemExit(0)
        if args[:2] == ['pr', 'create']:
            (root / 'after-create').write_text('1')
            raise SystemExit(0)
        if args[:2] == ['pr', 'comment']:
            raise SystemExit(0)
        print('unexpected gh command: ' + ' '.join(args), file=sys.stderr)
        raise SystemExit(99)
    """))
    gh.chmod(0o755)


class TestOrchestrator(unittest.TestCase):
    def test_dry_run(self):
        result = run([PY, str(SCRIPT), str(ROOT/'fixtures/sample_slice_plan.valid.json'), str(ROOT/'fixtures/sample_slice_plan.valid.json'), '--dry-run'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('waves=1', result.stdout)

    def test_list_shaped_waves_file(self):
        with tempfile.TemporaryDirectory() as td:
            waves = Path(td) / 'waves.json'
            waves.write_text('[{"wave": 1, "slice_ids": ["SLICE-001"], "integration_order": ["SLICE-001"], "parallel_safety_rationale": "single slice"}]')
            result = run([PY, str(SCRIPT), str(ROOT/'fixtures/sample_slice_plan.valid.json'), str(waves), '--dry-run'])
        self.assertEqual(result.returncode, 0)
        self.assertIn('waves=1', result.stdout)

    def test_external_waves_file_is_fully_validated(self):
        with tempfile.TemporaryDirectory() as td:
            plan = Path(td) / 'slice-plan.json'
            waves = Path(td) / 'waves.json'
            write_plan(
                plan,
                [
                    slice_item('SLICE-001', 'codebase-review/s1', 'src/a.txt'),
                    slice_item('SLICE-002', 'codebase-review/s2', 'src/b.txt', deps=['SLICE-001']),
                ],
                [
                    {'wave': 1, 'slice_ids': ['SLICE-001'], 'integration_order': ['SLICE-001'], 'parallel_safety_rationale': 'first'},
                    {'wave': 2, 'slice_ids': ['SLICE-002'], 'integration_order': ['SLICE-002'], 'parallel_safety_rationale': 'second'},
                ],
            )
            waves.write_text(json.dumps({
                'waves': [{
                    'wave': 1,
                    'slice_ids': ['SLICE-001', 'SLICE-002'],
                    'integration_order': ['SLICE-001', 'SLICE-002'],
                    'parallel_safety_rationale': 'different files',
                }]
            }))
            result = run([PY, str(SCRIPT), str(plan), str(waves), '--dry-run'])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('must be in an earlier wave', result.stderr + result.stdout)

    def test_pr_only_overrides_allow_merge(self):
        with tempfile.TemporaryDirectory() as td:
            plan = Path(td) / 'slice-plan.json'
            write_plan(
                plan,
                [slice_item('SLICE-001', 'codebase-review/s1', 'src/a.txt')],
                [{'wave': 1, 'slice_ids': ['SLICE-001'], 'integration_order': ['SLICE-001'], 'parallel_safety_rationale': 'single slice'}],
            )
            result = run([PY, str(SCRIPT), str(plan), str(plan), '--dry-run', '--allow-merge', '--pr-only'])
        self.assertEqual(result.returncode, 0)
        self.assertIn('merge=disabled', result.stdout)

    def test_allow_merge_requires_allow_pr(self):
        result = run([PY, str(SCRIPT), str(ROOT/'fixtures/sample_slice_plan.valid.json'), str(ROOT/'fixtures/sample_slice_plan.valid.json'), '--dry-run', '--allow-merge'])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('--allow-merge requires --allow-pr', result.stderr + result.stdout)

    def test_no_pr_overrides_allow_pr_for_review_request(self):
        result = run([
            PY,
            str(SCRIPT),
            str(ROOT/'fixtures/sample_slice_plan.valid.json'),
            str(ROOT/'fixtures/sample_slice_plan.valid.json'),
            '--dry-run',
            '--allow-pr',
            '--no-pr',
            '--allow-review-request',
        ])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('--allow-review-request requires --allow-pr', result.stderr + result.stdout)

    def test_executes_same_wave_slices_and_records_state(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            run_dir = Path(td) / 'run'
            worktrees = Path(td) / 'worktrees'
            plan = repo / 'slice-plan.json'
            write_plan(
                plan,
                [
                    slice_item('SLICE-001', 'codebase-review/s1', 'src/a.txt'),
                    slice_item('SLICE-002', 'codebase-review/s2', 'src/b.txt'),
                ],
                [{
                    'wave': 1,
                    'slice_ids': ['SLICE-001', 'SLICE-002'],
                    'integration_order': ['SLICE-001', 'SLICE-002'],
                    'parallel_safety_rationale': 'different files',
                }],
            )
            bin_dir = Path(td) / 'bin'
            bin_dir.mkdir()
            fake_codex_bin(bin_dir, """
                import pathlib, sys
                prompt = sys.argv[-1]
                if 'SLICE-001' in prompt:
                    pathlib.Path('src/a.txt').write_text('changed a\\n')
                elif 'SLICE-002' in prompt:
                    pathlib.Path('src/b.txt').write_text('changed b\\n')
                else:
                    raise SystemExit(7)
            """)
            env = {**os.environ, 'PATH': f'{bin_dir}{os.pathsep}{os.environ["PATH"]}'}
            result = run([
                PY, str(SCRIPT), str(plan), str(plan),
                '--max-parallel', '999',
                '--run-dir', str(run_dir),
                '--worktree-dir', str(worktrees),
            ], cwd=repo, env=env)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            state = json.loads((run_dir / 'run-state.json').read_text())
            self.assertEqual(state['slices']['SLICE-001']['status'], 'succeeded')
            self.assertEqual(state['slices']['SLICE-002']['status'], 'succeeded')
            self.assertFalse((repo / 'run-state.json').exists())

    def test_failed_slice_blocks_later_waves(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            run_dir = Path(td) / 'run'
            plan = repo / 'slice-plan.json'
            write_plan(
                plan,
                [
                    slice_item('SLICE-FAIL', 'codebase-review/fail', 'src/a.txt'),
                    slice_item('SLICE-LATER', 'codebase-review/later', 'src/b.txt', deps=['SLICE-FAIL']),
                ],
                [
                    {'wave': 1, 'slice_ids': ['SLICE-FAIL'], 'integration_order': ['SLICE-FAIL'], 'parallel_safety_rationale': 'single slice'},
                    {'wave': 2, 'slice_ids': ['SLICE-LATER'], 'integration_order': ['SLICE-LATER'], 'parallel_safety_rationale': 'after dependency'},
                ],
            )
            bin_dir = Path(td) / 'bin'
            bin_dir.mkdir()
            fake_codex_bin(bin_dir, """
                import pathlib, sys
                prompt = sys.argv[-1]
                pathlib.Path('codex-ran.txt').write_text(prompt)
                if 'SLICE-FAIL' in prompt:
                    raise SystemExit(9)
            """)
            env = {**os.environ, 'PATH': f'{bin_dir}{os.pathsep}{os.environ["PATH"]}'}
            result = run([PY, str(SCRIPT), str(plan), str(plan), '--run-dir', str(run_dir), '--worktree-dir', str(Path(td)/'worktrees')], cwd=repo, env=env)
            self.assertNotEqual(result.returncode, 0)
            state = json.loads((run_dir / 'run-state.json').read_text())
            self.assertEqual(state['slices']['SLICE-FAIL']['status'], 'failed')
            self.assertNotIn('SLICE-LATER', state['slices'])

    def test_out_of_scope_edit_fails_slice(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            run_dir = Path(td) / 'run'
            plan = repo / 'slice-plan.json'
            write_plan(
                plan,
                [slice_item('SLICE-001', 'codebase-review/s1', 'src/a.txt')],
                [{'wave': 1, 'slice_ids': ['SLICE-001'], 'integration_order': ['SLICE-001'], 'parallel_safety_rationale': 'single slice'}],
            )
            bin_dir = Path(td) / 'bin'
            bin_dir.mkdir()
            fake_codex_bin(bin_dir, """
                import pathlib
                pathlib.Path('outside.txt').write_text('bad\\n')
            """)
            env = {**os.environ, 'PATH': f'{bin_dir}{os.pathsep}{os.environ["PATH"]}'}
            result = run([PY, str(SCRIPT), str(plan), str(plan), '--run-dir', str(run_dir), '--worktree-dir', str(Path(td)/'worktrees')], cwd=repo, env=env)
            self.assertNotEqual(result.returncode, 0)
            state = json.loads((run_dir / 'run-state.json').read_text())
            self.assertIn('outside scope', state['slices']['SLICE-001']['error'])

    def test_out_of_scope_edit_created_by_verification_fails_slice(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            run_dir = Path(td) / 'run'
            plan = repo / 'slice-plan.json'
            item = slice_item('SLICE-001', 'codebase-review/s1', 'src/a.txt')
            item['verification_commands'] = ['python3 -c "open(\'outside.txt\', \'w\').write(\'bad\')"']
            write_plan(
                plan,
                [item],
                [{'wave': 1, 'slice_ids': ['SLICE-001'], 'integration_order': ['SLICE-001'], 'parallel_safety_rationale': 'single slice'}],
            )
            bin_dir = Path(td) / 'bin'
            bin_dir.mkdir()
            fake_codex_bin(bin_dir, """
                import pathlib
                pathlib.Path('src/a.txt').write_text('changed\\n')
            """)
            env = {**os.environ, 'PATH': f'{bin_dir}{os.pathsep}{os.environ["PATH"]}'}
            result = run([PY, str(SCRIPT), str(plan), str(plan), '--run-dir', str(run_dir), '--worktree-dir', str(Path(td)/'worktrees')], cwd=repo, env=env)
            self.assertNotEqual(result.returncode, 0)
            state = json.loads((run_dir / 'run-state.json').read_text())
            self.assertIn('outside scope', state['slices']['SLICE-001']['error'])

    def test_resume_skips_completed_slice(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            run_dir = Path(td) / 'run'
            plan = repo / 'slice-plan.json'
            counter = Path(td) / 'counter.txt'
            write_plan(
                plan,
                [slice_item('SLICE-001', 'codebase-review/s1', 'src/a.txt')],
                [{'wave': 1, 'slice_ids': ['SLICE-001'], 'integration_order': ['SLICE-001'], 'parallel_safety_rationale': 'single slice'}],
            )
            bin_dir = Path(td) / 'bin'
            bin_dir.mkdir()
            fake_codex_bin(bin_dir, f"""
                import pathlib
                counter = pathlib.Path({str(counter)!r})
                value = int(counter.read_text()) if counter.exists() else 0
                counter.write_text(str(value + 1))
                pathlib.Path('src/a.txt').write_text('changed\\n')
            """)
            env = {**os.environ, 'PATH': f'{bin_dir}{os.pathsep}{os.environ["PATH"]}'}
            first = run([PY, str(SCRIPT), str(plan), str(plan), '--run-dir', str(run_dir), '--worktree-dir', str(Path(td)/'worktrees')], cwd=repo, env=env)
            second = run([PY, str(SCRIPT), str(plan), str(plan), '--run-dir', str(run_dir), '--worktree-dir', str(Path(td)/'worktrees'), '--resume'], cwd=repo, env=env)
            self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
            self.assertEqual(second.returncode, 0, second.stderr + second.stdout)
            self.assertEqual(counter.read_text(), '1')

    def test_resume_skips_already_merged_slice_during_merge_loop(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            run_dir = Path(td) / 'run'
            worktree = Path(td) / 'worktrees' / 'codebase-review-s1'
            plan = repo / 'slice-plan.json'
            write_plan(
                plan,
                [slice_item('SLICE-001', 'codebase-review/s1', 'src/a.txt')],
                [{'wave': 1, 'slice_ids': ['SLICE-001'], 'integration_order': ['SLICE-001'], 'parallel_safety_rationale': 'single slice'}],
            )
            run_dir.mkdir()
            (run_dir / 'run-state.json').write_text(json.dumps({
                'created_at': 'test',
                'repo': str(repo),
                'run_dir': str(run_dir),
                'slice_plan': str(plan),
                'waves': {},
                'slices': {
                    'SLICE-001': {
                        'status': 'merged',
                        'branch': 'codebase-review/s1',
                        'worktree': str(worktree),
                        'head_sha': 'abc123',
                        'pr_number': 123,
                    }
                },
            }))
            bin_dir = Path(td) / 'bin'
            fake_dir = Path(td) / 'fake-gh'
            bin_dir.mkdir()
            fake_dir.mkdir()
            fake_codex_bin(bin_dir, "raise SystemExit(99)")
            fake_gh_bin(bin_dir, fake_dir)
            env = {**os.environ, 'PATH': f'{bin_dir}{os.pathsep}{os.environ["PATH"]}'}
            result = run([
                PY, str(SCRIPT), str(plan), str(plan),
                '--run-dir', str(run_dir),
                '--worktree-dir', str(Path(td)/'worktrees'),
                '--resume',
                '--allow-pr',
                '--allow-merge',
            ], cwd=repo, env=env)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertNotIn('pr merge', (fake_dir / 'gh-calls.log').read_text())

    def test_reused_worktree_must_be_clean(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            run_dir = Path(td) / 'run'
            worktrees = Path(td) / 'worktrees'
            plan = repo / 'slice-plan.json'
            write_plan(
                plan,
                [slice_item('SLICE-001', 'codebase-review/s1', 'src/a.txt')],
                [{'wave': 1, 'slice_ids': ['SLICE-001'], 'integration_order': ['SLICE-001'], 'parallel_safety_rationale': 'single slice'}],
            )
            git(repo, 'worktree', 'add', '-b', 'codebase-review/s1', str(worktrees / 'codebase-review-s1'), 'HEAD')
            (worktrees / 'codebase-review-s1' / 'src' / 'a.txt').write_text('dirty allowed change\\n')
            bin_dir = Path(td) / 'bin'
            bin_dir.mkdir()
            fake_codex_bin(bin_dir, "")
            env = {**os.environ, 'PATH': f'{bin_dir}{os.pathsep}{os.environ["PATH"]}'}
            result = run([
                PY, str(SCRIPT), str(plan), str(plan),
                '--run-dir', str(run_dir),
                '--worktree-dir', str(worktrees),
                '--reuse-worktrees',
            ], cwd=repo, env=env)
            self.assertNotEqual(result.returncode, 0)
            state = json.loads((run_dir / 'run-state.json').read_text())
            self.assertIn('not clean', state['slices']['SLICE-001']['error'])

    def test_allow_pr_uses_branch_base_from_base_ref(self):
        with tempfile.TemporaryDirectory() as td:
            bare = Path(td) / 'origin.git'
            git(Path(td), 'init', '--bare', str(bare))
            repo = make_repo(td)
            git(repo, 'remote', 'add', 'origin', str(bare))
            git(repo, 'push', '-u', 'origin', 'main')
            git(repo, 'checkout', '-b', 'release')
            git(repo, 'push', '-u', 'origin', 'release')
            git(repo, 'checkout', 'main')
            run_dir = Path(td) / 'run'
            plan = repo / 'slice-plan.json'
            write_plan(
                plan,
                [slice_item('SLICE-001', 'codebase-review/s1', 'src/a.txt')],
                [{'wave': 1, 'slice_ids': ['SLICE-001'], 'integration_order': ['SLICE-001'], 'parallel_safety_rationale': 'single slice'}],
            )
            bin_dir = Path(td) / 'bin'
            fake_dir = Path(td) / 'fake-gh'
            bin_dir.mkdir()
            fake_dir.mkdir()
            (fake_dir / 'base.txt').write_text('release')
            (fake_dir / 'body.txt').write_text('Slice-ID: SLICE-001')
            fake_codex_bin(bin_dir, """
                import pathlib
                pathlib.Path('src/a.txt').write_text('changed\\n')
            """)
            fake_gh_bin(bin_dir, fake_dir)
            env = {**os.environ, 'PATH': f'{bin_dir}{os.pathsep}{os.environ["PATH"]}'}
            result = run([
                PY, str(SCRIPT), str(plan), str(plan),
                '--run-dir', str(run_dir),
                '--worktree-dir', str(Path(td)/'worktrees'),
                '--base-ref', 'origin/release',
                '--allow-pr',
            ], cwd=repo, env=env)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn('--base release', (fake_dir / 'gh-calls.log').read_text())

    def test_codex_agent_is_rejected_until_supported(self):
        result = run([
            PY,
            str(SCRIPT),
            str(ROOT/'fixtures/sample_slice_plan.valid.json'),
            str(ROOT/'fixtures/sample_slice_plan.valid.json'),
            '--dry-run',
            '--codex-agent',
            'slice-reviewer',
        ])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('--codex-agent is not supported', result.stderr + result.stdout)


if __name__ == '__main__':
    unittest.main()
