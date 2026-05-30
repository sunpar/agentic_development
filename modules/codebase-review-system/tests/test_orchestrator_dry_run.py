import json
import hashlib
import importlib.util
import os
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import types
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
    (repo / '.gitignore').write_text('.venv/\n')
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
        'tests_to_read': [path],
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


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bound_state(repo, run_dir, plan, slices, waves=None):
    data = json.loads(Path(plan).read_text())
    return {
        'created_at': 'test',
        'repo': str(repo),
        'repo_remote_url': '',
        'run_dir': str(run_dir),
        'slice_plan': str(plan),
        'waves_path': str(plan),
        'slice_plan_sha256': file_sha256(plan),
        'waves_sha256': file_sha256(plan),
        'slice_branches': {
            item['id']: item.get('branch') or f'codebase-review/{item["id"].lower()}'
            for item in data.get('slices', [])
        },
        'waves': waves or {},
        'slices': slices,
    }


def fake_codex_bin(bin_dir, body):
    codex = Path(bin_dir) / 'codex'
    codex.write_text(
        '#!/usr/bin/env python3\n'
        'import sys\n'
        'if sys.argv[1:2] == ["--version"]:\n'
        '    print("codex fake")\n'
        '    raise SystemExit(0)\n'
        + textwrap.dedent(body)
    )
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


def load_orchestrator_module():
    spec = importlib.util.spec_from_file_location('orchestrate_slice_waves_for_test', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestOrchestrator(unittest.TestCase):
    def test_dry_run(self):
        result = run([PY, str(SCRIPT), str(ROOT/'fixtures/sample_slice_plan.valid.json'), str(ROOT/'fixtures/sample_slice_plan.valid.json'), '--dry-run'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('waves=1', result.stdout)

    def test_review_timeout_defaults_are_bounded(self):
        module = load_orchestrator_module()
        old_argv = sys.argv
        try:
            sys.argv = ['orchestrate_slice_waves.py', 'slice-plan.json', 'waves.json']
            args = module.parse_args()
        finally:
            sys.argv = old_argv
        self.assertEqual(args.review_timeout_seconds, 600)
        self.assertEqual(args.review_agent_timeout_seconds, 600)
        self.assertEqual(args.review_thread_timeout_seconds, 0)

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
            self.assertEqual(state['execution_options']['max_parallel'], 999)
            self.assertFalse(state['execution_options']['allow_pr'])
            self.assertEqual(state['slices']['SLICE-001']['status'], 'succeeded')
            self.assertEqual(state['slices']['SLICE-002']['status'], 'succeeded')
            self.assertFalse((repo / 'run-state.json').exists())
            summary = json.loads((run_dir / 'run-summary.json').read_text())
            self.assertEqual(summary['slice_plan'], str(plan.resolve()))
            self.assertEqual(summary['waves_path'], str(plan.resolve()))
            self.assertEqual(summary['slice_branches']['SLICE-001'], 'codebase-review/s1')
            self.assertEqual(summary['execution_options']['max_parallel'], 999)
            self.assertEqual(summary['totals']['slices'], 2)
            self.assertEqual(summary['totals']['by_status']['succeeded'], 2)
            self.assertEqual(summary['waves'][0]['status'], 'succeeded')
            self.assertEqual(summary['slices'][0]['worktree'], str((worktrees / 'codebase-review-s1').resolve()))
            self.assertIn('SLICE-001', (run_dir / 'run-summary.md').read_text())

    def test_cleanup_artifacts_dry_run_lists_old_runs_and_worktrees_without_removing(self):
        with tempfile.TemporaryDirectory() as td:
            runs_root = Path(td) / 'runs'
            worktrees = Path(td) / 'worktrees'
            old_run = runs_root / 'repo-20200101T000000Z'
            new_run = runs_root / 'repo-new'
            old_worktree = worktrees / 'codebase-review-old'
            new_worktree = worktrees / 'codebase-review-new'
            for path in [old_run, new_run, old_worktree, new_worktree]:
                path.mkdir(parents=True)
            (old_run / 'run-state.json').write_text('{}\n')
            (new_run / 'run-state.json').write_text('{}\n')
            old_time = time.time() - (60 * 60 * 24 * 40)
            os.utime(old_run, (old_time, old_time))
            os.utime(old_worktree, (old_time, old_time))

            result = run([
                PY,
                str(SCRIPT),
                '--cleanup-artifacts',
                '--dry-run',
                '--runs-root',
                str(runs_root),
                '--worktree-dir',
                str(worktrees),
                '--cleanup-older-than-days',
                '30',
            ])

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn(f'[dry-run] remove run_dir {old_run}', result.stdout)
            self.assertIn(f'[dry-run] remove worktree {old_worktree}', result.stdout)
            self.assertNotIn(str(new_run), result.stdout)
            self.assertNotIn(str(new_worktree), result.stdout)
            self.assertTrue(old_run.exists())
            self.assertTrue(old_worktree.exists())

    def test_cleanup_artifacts_removes_worktrees_through_git(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            worktrees = Path(td) / 'worktrees'
            old_worktree = worktrees / 'codebase-review-old'
            git(repo, 'worktree', 'add', '-b', 'codebase-review/old', str(old_worktree), 'HEAD')
            old_time = time.time() - (60 * 60 * 24 * 40)
            os.utime(old_worktree, (old_time, old_time))

            result = run([
                PY,
                str(SCRIPT),
                '--cleanup-artifacts',
                '--confirm-cleanup',
                '--runs-root',
                str(Path(td) / 'runs'),
                '--worktree-dir',
                str(worktrees),
                '--cleanup-older-than-days',
                '30',
            ])

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertFalse(old_worktree.exists())
            self.assertNotIn(str(old_worktree), git(repo, 'worktree', 'list', '--porcelain').stdout)

    def test_uses_first_working_codex_binary_from_path(self):
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
            bad_bin = Path(td) / 'bad-bin'
            good_bin = Path(td) / 'good-bin'
            bad_bin.mkdir()
            good_bin.mkdir()
            broken = bad_bin / 'codex'
            broken.write_text('#!/usr/bin/env python3\nimport sys\nprint("broken", file=sys.stderr)\nraise SystemExit(1)\n')
            broken.chmod(0o755)
            fake_codex_bin(good_bin, """
                import pathlib
                pathlib.Path('src/a.txt').write_text('changed\\n')
            """)
            env = {**os.environ, 'PATH': f'{bad_bin}{os.pathsep}{good_bin}{os.pathsep}{os.environ["PATH"]}'}
            result = run([
                PY, str(SCRIPT), str(plan), str(plan),
                '--run-dir', str(run_dir),
                '--worktree-dir', str(worktrees),
            ], cwd=repo, env=env)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            state = json.loads((run_dir / 'run-state.json').read_text())
            self.assertEqual(Path(state['codex_bin']), (good_bin / 'codex').resolve())
            self.assertEqual(state['slices']['SLICE-001']['status'], 'succeeded')

    def test_setup_command_runs_before_codex_and_verification(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            run_dir = Path(td) / 'run'
            worktrees = Path(td) / 'worktrees'
            plan = repo / 'slice-plan.json'
            item = slice_item('SLICE-001', 'codebase-review/s1', 'src/a.txt')
            item['verification_commands'] = ['python3 -c "import pathlib; assert pathlib.Path(\'.venv/setup.txt\').read_text() == \'ready\'"']
            write_plan(
                plan,
                [item],
                [{'wave': 1, 'slice_ids': ['SLICE-001'], 'integration_order': ['SLICE-001'], 'parallel_safety_rationale': 'single slice'}],
            )
            bin_dir = Path(td) / 'bin'
            bin_dir.mkdir()
            fake_codex_bin(bin_dir, """
                import pathlib
                assert pathlib.Path('.venv/setup.txt').read_text() == 'ready'
                pathlib.Path('src/a.txt').write_text('changed\\n')
            """)
            env = {**os.environ, 'PATH': f'{bin_dir}{os.pathsep}{os.environ["PATH"]}'}
            result = run([
                PY, str(SCRIPT), str(plan), str(plan),
                '--run-dir', str(run_dir),
                '--worktree-dir', str(worktrees),
                '--setup-command', 'mkdir -p .venv && python3 -c "open(\'.venv/setup.txt\', \'w\').write(\'ready\')"',
            ], cwd=repo, env=env)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            state = json.loads((run_dir / 'run-state.json').read_text())
            self.assertEqual(state['slices']['SLICE-001']['status'], 'succeeded')
            self.assertEqual(state['slices']['SLICE-001']['setup'][0]['returncode'], 0)
            self.assertTrue((run_dir / 'slices' / 'SLICE-001' / 'setup.json').exists())

    def test_codex_gets_run_dir_as_additional_writable_dir(self):
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
            bin_dir = Path(td) / 'bin'
            bin_dir.mkdir()
            fake_codex_bin(bin_dir, """
                import json, pathlib, sys
                pathlib.Path('src/a.txt').write_text(json.dumps(sys.argv))
            """)
            env = {**os.environ, 'PATH': f'{bin_dir}{os.pathsep}{os.environ["PATH"]}'}
            result = run([
                PY, str(SCRIPT), str(plan), str(plan),
                '--run-dir', str(run_dir),
                '--worktree-dir', str(worktrees),
            ], cwd=repo, env=env)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            worktree = worktrees / 'codebase-review-s1'
            argv = json.loads((worktree / 'src' / 'a.txt').read_text())
            self.assertIn('--add-dir', argv)
            self.assertEqual(argv[argv.index('--add-dir') + 1], str(run_dir.resolve()))

    def test_verification_uses_worktree_venv_python(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            run_dir = Path(td) / 'run'
            worktrees = Path(td) / 'worktrees'
            plan = repo / 'slice-plan.json'
            item = slice_item('SLICE-001', 'codebase-review/s1', 'src/a.txt')
            item['verification_commands'] = ['python -c "open(\'src/a.txt\').read()"']
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
            setup_command = (
                "mkdir -p .venv/bin && "
                "cat > .venv/bin/python <<'SH'\n"
                "#!/bin/sh\n"
                "echo used > .venv/used-python\n"
                "exec python3 \"$@\"\n"
                "SH\n"
                'chmod +x .venv/bin/python'
            )
            env = {**os.environ, 'PATH': f'{bin_dir}{os.pathsep}{os.environ["PATH"]}'}
            result = run([
                PY, str(SCRIPT), str(plan), str(plan),
                '--run-dir', str(run_dir),
                '--worktree-dir', str(worktrees),
                '--setup-command', setup_command,
            ], cwd=repo, env=env)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            worktree = worktrees / 'codebase-review-s1'
            self.assertEqual((worktree / '.venv' / 'used-python').read_text().strip(), 'used')

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
            self.assertIn('SLICE-FAIL failed: codex exited 9', result.stderr + result.stdout)
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

    def test_out_of_scope_rename_source_fails_slice(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            (repo / 'config.yml').write_text('secret: false\n')
            git(repo, 'add', 'config.yml')
            git(repo, 'commit', '-m', 'add config')
            run_dir = Path(td) / 'run'
            plan = repo / 'slice-plan.json'
            write_plan(
                plan,
                [slice_item('SLICE-001', 'codebase-review/s1', 'src/config.yml')],
                [{'wave': 1, 'slice_ids': ['SLICE-001'], 'integration_order': ['SLICE-001'], 'parallel_safety_rationale': 'single slice'}],
            )
            bin_dir = Path(td) / 'bin'
            bin_dir.mkdir()
            fake_codex_bin(bin_dir, """
                import subprocess
                subprocess.run(['git', 'mv', 'config.yml', 'src/config.yml'], check=True)
            """)
            env = {**os.environ, 'PATH': f'{bin_dir}{os.pathsep}{os.environ["PATH"]}'}
            result = run([
                PY, str(SCRIPT), str(plan), str(plan),
                '--run-dir', str(run_dir),
                '--worktree-dir', str(Path(td)/'worktrees'),
            ], cwd=repo, env=env)
            self.assertNotEqual(result.returncode, 0)
            state = json.loads((run_dir / 'run-state.json').read_text())
            self.assertIn('outside scope', state['slices']['SLICE-001']['error'])
            self.assertIn('config.yml', state['slices']['SLICE-001']['error'])

    def test_legacy_slice_artifacts_are_moved_to_run_dir(self):
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
            bin_dir = Path(td) / 'bin'
            bin_dir.mkdir()
            fake_codex_bin(bin_dir, """
                import pathlib
                pathlib.Path('src/a.txt').write_text('changed\\n')
                out = pathlib.Path('docs/agentic-system')
                out.mkdir(parents=True)
                (out / 'SLICE-001.review-result.json').write_text('{}\\n')
                (out / 'SLICE-001.refactor-result.json').write_text('{}\\n')
            """)
            env = {**os.environ, 'PATH': f'{bin_dir}{os.pathsep}{os.environ["PATH"]}'}
            result = run([
                PY, str(SCRIPT), str(plan), str(plan),
                '--run-dir', str(run_dir),
                '--worktree-dir', str(worktrees),
            ], cwd=repo, env=env)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            state = json.loads((run_dir / 'run-state.json').read_text())
            self.assertEqual(state['slices']['SLICE-001']['status'], 'succeeded')
            slice_dir = run_dir / 'slices' / 'SLICE-001'
            self.assertTrue((slice_dir / 'SLICE-001.review-result.json').exists())
            self.assertTrue((slice_dir / 'SLICE-001.refactor-result.json').exists())
            worktree = worktrees / 'codebase-review-s1'
            self.assertFalse((worktree / 'docs' / 'agentic-system' / 'SLICE-001.review-result.json').exists())
            self.assertEqual(run(['git', 'status', '--porcelain'], cwd=worktree).stdout.rstrip(), ' M src/a.txt')

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

    def test_resume_rejects_state_with_plan_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            run_dir = Path(td) / 'run'
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
                'repo_remote_url': '',
                'run_dir': str(run_dir),
                'slice_plan': str(plan),
                'slice_plan_sha256': 'not-the-current-plan',
                'waves_sha256': 'not-the-current-waves',
                'slice_branches': {'SLICE-001': 'codebase-review/s1'},
                'waves': {},
                'slices': {
                    'SLICE-001': {
                        'status': 'merged',
                        'branch': 'codebase-review/s1',
                    }
                },
            }))
            bin_dir = Path(td) / 'bin'
            bin_dir.mkdir()
            fake_codex_bin(bin_dir, "raise SystemExit(99)")
            env = {**os.environ, 'PATH': f'{bin_dir}{os.pathsep}{os.environ["PATH"]}'}
            result = run([
                PY, str(SCRIPT), str(plan), str(plan),
                '--run-dir', str(run_dir),
                '--worktree-dir', str(Path(td)/'worktrees'),
                '--resume',
            ], cwd=repo, env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('run-state slice plan hash mismatch', result.stderr + result.stdout)

    def test_resume_rejects_legacy_state_with_saved_slice_progress_without_hashes(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            run_dir = Path(td) / 'run'
            plan = repo / 'slice-plan.json'
            write_plan(
                plan,
                [slice_item('SLICE-001', 'codebase-review/s1', 'src/a.txt')],
                [{'wave': 1, 'slice_ids': ['SLICE-001'], 'integration_order': ['SLICE-001'], 'parallel_safety_rationale': 'single slice'}],
            )
            run_dir.mkdir()
            (run_dir / 'run-state.json').write_text(json.dumps({
                'created_at': 'legacy',
                'repo': str(repo),
                'run_dir': str(run_dir),
                'slice_plan': str(plan),
                'waves': {},
                'slices': {
                    'SLICE-001': {
                        'status': 'pr_ready',
                        'branch': 'codebase-review/s1',
                        'worktree': '/tmp/old-worktree',
                        'head_sha': 'old',
                        'pr_number': 999,
                    }
                },
            }))
            bin_dir = Path(td) / 'bin'
            bin_dir.mkdir()
            fake_codex_bin(bin_dir, "raise SystemExit(99)")
            env = {**os.environ, 'PATH': f'{bin_dir}{os.pathsep}{os.environ["PATH"]}'}
            result = run([
                PY, str(SCRIPT), str(plan), str(plan),
                '--run-dir', str(run_dir),
                '--worktree-dir', str(Path(td)/'worktrees'),
                '--resume',
                '--allow-pr',
                '--allow-merge',
            ], cwd=repo, env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('run-state is missing binding metadata', result.stderr + result.stdout)

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
            (run_dir / 'run-state.json').write_text(json.dumps(bound_state(
                repo,
                run_dir,
                plan,
                {
                    'SLICE-001': {
                        'status': 'merged',
                        'branch': 'codebase-review/s1',
                        'worktree': str(worktree),
                        'head_sha': 'abc123',
                        'pr_number': 123,
                    }
                },
            )))
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

    def test_merge_slice_requires_review_after_requested_timestamp(self):
        with tempfile.TemporaryDirectory() as td:
            module = load_orchestrator_module()
            run_dir = Path(td) / 'run'
            slice_dir = run_dir / 'slices' / 'SLICE-001'
            slice_dir.mkdir(parents=True)
            calls = []

            def fake_run_cmd(cmd, cwd=None, timeout=None):
                calls.append(cmd)
                return types.SimpleNamespace(returncode=0, stdout='', stderr='')

            module.run_cmd = fake_run_cmd
            args = types.SimpleNamespace(
                merge_method='squash',
                ci_timeout_seconds=1,
                ci_poll_seconds=1,
                review_timeout_seconds=1,
                delete_branch=False,
                allow_review_request=True,
            )
            state = {
                'slices': {
                    'SLICE-001': {
                        'status': 'pr_ready',
                        'pr_number': 123,
                        'worktree': str(Path(td)),
                        'head_sha': 'abc123',
                        'review_requested_at': '2026-05-22T13:00:00Z',
                    }
                }
            }
            result = module.merge_slice({'id': 'SLICE-001'}, args, run_dir, state)
            self.assertTrue(result)
            self.assertIn('--require-review-after', calls[0])
            self.assertEqual(calls[0][calls[0].index('--require-review-after') + 1], '2026-05-22T13:00:00Z')
            self.assertIn('--review-thread-timeout-seconds', calls[0])
            self.assertEqual(calls[0][calls[0].index('--review-thread-timeout-seconds') + 1], '0')

    def test_merge_slice_blocks_review_request_without_timestamp(self):
        with tempfile.TemporaryDirectory() as td:
            module = load_orchestrator_module()
            run_dir = Path(td) / 'run'
            (run_dir / 'slices' / 'SLICE-001').mkdir(parents=True)
            args = types.SimpleNamespace(
                merge_method='squash',
                ci_timeout_seconds=1,
                ci_poll_seconds=1,
                review_timeout_seconds=1,
                delete_branch=False,
                allow_review_request=True,
            )
            state = {
                'slices': {
                    'SLICE-001': {
                        'status': 'pr_ready',
                        'pr_number': 123,
                        'worktree': str(Path(td)),
                        'head_sha': 'abc123',
                    }
                }
            }
            with self.assertRaisesRegex(RuntimeError, 'review request timestamp missing'):
                module.merge_slice({'id': 'SLICE-001'}, args, run_dir, state)

    def test_merge_slice_repairs_unresolved_review_threads_and_retries_gate(self):
        with tempfile.TemporaryDirectory() as td:
            module = load_orchestrator_module()
            run_dir = Path(td) / 'run'
            (run_dir / 'slices' / 'SLICE-001').mkdir(parents=True)
            merge_calls = []
            repairs = []

            def fake_run_cmd(cmd, cwd=None, timeout=None):
                merge_calls.append(cmd)
                if len(merge_calls) == 1:
                    return types.SimpleNamespace(returncode=1, stdout='', stderr='ERROR: unresolved review threads: 1: src/a.txt:1 by codex: fix this')
                return types.SimpleNamespace(returncode=0, stdout='', stderr='')

            def fake_repair(slice_item, args, repair_run_dir, plan_copy, state, attempt):
                repairs.append((slice_item['id'], attempt, str(plan_copy)))
                state['slices']['SLICE-001']['head_sha'] = 'new-head'
                state['slices']['SLICE-001']['review_requested_at'] = '2026-05-22T14:00:00Z'
                return True

            module.run_cmd = fake_run_cmd
            module.repair_review_threads = fake_repair
            args = types.SimpleNamespace(
                merge_method='squash',
                ci_timeout_seconds=1,
                ci_poll_seconds=1,
                review_timeout_seconds=1,
                review_repair_attempts=1,
                delete_branch=False,
                allow_review_request=True,
            )
            state = {
                'slices': {
                    'SLICE-001': {
                        'status': 'pr_ready',
                        'pr_number': 123,
                        'worktree': str(Path(td)),
                        'head_sha': 'old-head',
                        'review_requested_at': '2026-05-22T13:00:00Z',
                    }
                }
            }
            result = module.merge_slice({'id': 'SLICE-001'}, args, run_dir, state)
            self.assertTrue(result)
            self.assertEqual(repairs, [('SLICE-001', 1, str(run_dir / 'slice-plan.json'))])
            self.assertEqual(len(merge_calls), 2)
            self.assertEqual(merge_calls[1][merge_calls[1].index('--expected-head-sha') + 1], 'new-head')
            self.assertEqual(merge_calls[1][merge_calls[1].index('--require-review-after') + 1], '2026-05-22T14:00:00Z')

    def test_request_reviews_requests_codex_and_copilot_and_waits_for_each(self):
        with tempfile.TemporaryDirectory() as td:
            module = load_orchestrator_module()
            calls = []
            calls_lock = threading.Lock()
            copilot_request_started = threading.Event()

            def fake_run_cmd(cmd, cwd=None, timeout=None):
                with calls_lock:
                    calls.append(cmd)
                if cmd[:3] == ['gh', 'pr', 'comment']:
                    if not copilot_request_started.wait(1):
                        return types.SimpleNamespace(returncode=98, stdout='', stderr='codex request started before copilot request was submitted')
                    return types.SimpleNamespace(returncode=0, stdout='', stderr='')
                if cmd[:3] == ['gh', 'pr', 'edit']:
                    copilot_request_started.set()
                    return types.SimpleNamespace(returncode=0, stdout='', stderr='')
                if cmd[:3] == ['gh', 'pr', 'view']:
                    payload = {
                        'latestReviews': [
                            {
                                'author': {'login': 'codex-reviewer'},
                                'submittedAt': '2026-05-22T14:00:01Z',
                                'state': 'COMMENTED',
                            },
                            {
                                'author': {'login': 'copilot-pull-request-reviewer'},
                                'submittedAt': '2026-05-22T14:00:02Z',
                                'state': 'COMMENTED',
                            },
                        ],
                        'comments': [],
                    }
                    return types.SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr='')
                return types.SimpleNamespace(returncode=99, stdout='', stderr='unexpected')

            module.run_cmd = fake_run_cmd
            module.now_utc = lambda: '2026-05-22T14:00:00Z'
            args = types.SimpleNamespace(
                review_agents='codex,copilot',
                review_agent_timeout_seconds=5,
                review_agent_poll_seconds=0,
            )

            result = module.request_reviews(Path(td), 123, slice_item('SLICE-001', 'codebase-review/s1', 'src/a.txt'), args)

            self.assertEqual(result['requested_at'], '2026-05-22T14:00:00Z')
            self.assertEqual(set(result['agents']), {'codex', 'copilot'})
            self.assertEqual(result['agents']['codex']['status'], 'completed')
            self.assertEqual(result['agents']['copilot']['status'], 'completed')
            self.assertEqual(result['completed_agents'], ['codex', 'copilot'])
            self.assertEqual(result['timed_out_agents'], [])
            self.assertEqual(result['review_gate_required_at'], '2026-05-22T14:00:00Z')
            self.assertIn(['gh', 'pr', 'comment', '123', '--body'], [call[:5] for call in calls])
            self.assertIn(['gh', 'pr', 'edit', '123', '--add-reviewer', '@copilot'], calls)

    def test_request_reviews_records_timeout_without_failing(self):
        with tempfile.TemporaryDirectory() as td:
            module = load_orchestrator_module()

            def fake_run_cmd(cmd, cwd=None, timeout=None):
                if cmd[:3] == ['gh', 'pr', 'comment']:
                    return types.SimpleNamespace(returncode=0, stdout='', stderr='')
                if cmd[:3] == ['gh', 'pr', 'view']:
                    return types.SimpleNamespace(returncode=0, stdout=json.dumps({'latestReviews': [], 'comments': []}), stderr='')
                return types.SimpleNamespace(returncode=99, stdout='', stderr='unexpected')

            module.run_cmd = fake_run_cmd
            module.now_utc = lambda: '2026-05-22T14:00:00Z'
            args = types.SimpleNamespace(
                review_agents='codex',
                review_agent_timeout_seconds=0,
                review_agent_poll_seconds=0,
            )

            result = module.request_reviews(Path(td), 123, slice_item('SLICE-001', 'codebase-review/s1', 'src/a.txt'), args)

            self.assertEqual(result['agents']['codex']['status'], 'timed_out')
            self.assertEqual(result['timed_out_agents'], ['codex'])
            self.assertEqual(result['completed_agents'], [])
            self.assertIsNone(result['review_gate_required_at'])

    def test_request_reviews_records_failed_agent_without_failing(self):
        with tempfile.TemporaryDirectory() as td:
            module = load_orchestrator_module()

            def fake_run_cmd(cmd, cwd=None, timeout=None):
                if cmd[:3] == ['gh', 'pr', 'comment']:
                    return types.SimpleNamespace(returncode=0, stdout='', stderr='')
                if cmd[:3] == ['gh', 'pr', 'edit']:
                    return types.SimpleNamespace(returncode=1, stdout='', stderr='unsupported reviewer')
                if cmd[:3] == ['gh', 'pr', 'view']:
                    payload = {
                        'latestReviews': [{
                            'author': {'login': 'codex-reviewer'},
                            'submittedAt': '2026-05-22T14:00:01Z',
                            'state': 'COMMENTED',
                        }],
                        'comments': [],
                    }
                    return types.SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr='')
                return types.SimpleNamespace(returncode=99, stdout='', stderr='unexpected')

            module.run_cmd = fake_run_cmd
            module.now_utc = lambda: '2026-05-22T14:00:00Z'
            args = types.SimpleNamespace(
                review_agents='codex,copilot',
                review_agent_timeout_seconds=0,
                review_agent_poll_seconds=0,
            )

            result = module.request_reviews(Path(td), 123, slice_item('SLICE-001', 'codebase-review/s1', 'src/a.txt'), args)

            self.assertEqual(result['completed_agents'], ['codex'])
            self.assertEqual(result['failed_agents'], ['copilot'])
            self.assertEqual(result['agents']['copilot']['status'], 'failed')
            self.assertIn('unsupported reviewer', result['agents']['copilot']['error'])
            self.assertEqual(result['review_gate_required_at'], '2026-05-22T14:00:00Z')

    def test_review_repair_resolves_only_threads_no_longer_active(self):
        with tempfile.TemporaryDirectory() as td:
            module = load_orchestrator_module()
            run_dir = Path(td) / 'run'
            worktree = Path(td) / 'worktree'
            run_dir.mkdir()
            worktree.mkdir()
            thread_one = {'id': 'thread-one', 'path': 'src/a.txt'}
            thread_two = {'id': 'thread-two', 'path': 'src/b.txt'}
            active_thread_calls = [[thread_one, thread_two], [thread_two]]
            resolved = []

            module.active_review_threads = lambda *_args: active_thread_calls.pop(0)
            module.codex_command = lambda *_args, **_kwargs: ['codex-fake']
            module.run_cmd = lambda *_args, **_kwargs: types.SimpleNamespace(returncode=0, stdout='', stderr='')
            module.move_legacy_slice_artifacts = lambda *_args: []
            module.changed_files_in_scope = lambda *_args: ['src/a.txt']
            module.verification_results = lambda *_args: []
            module.fail_on_verification = lambda *_args: None
            module.commit_slice = lambda *_args, **_kwargs: 'new-head'
            module.push_branch = lambda *_args: None
            module.resolve_review_thread = lambda _worktree, thread_id: resolved.append(thread_id) or {'thread_id': thread_id}
            args = types.SimpleNamespace(resolve_review_threads=True, allow_review_request=False)
            state = {
                'slices': {
                    'SLICE-001': {
                        'worktree': str(worktree),
                        'pr_number': 123,
                        'head_sha': 'old-head',
                    }
                }
            }

            result = module.repair_review_threads(
                slice_item('SLICE-001', 'codebase-review/s1', 'src/a.txt'),
                args,
                run_dir,
                run_dir / 'slice-plan.json',
                state,
                1,
            )

            self.assertTrue(result)
            self.assertEqual(resolved, ['thread-one'])
            repair = state['slices']['SLICE-001']['review_repair_attempts'][0]
            self.assertEqual(repair['active_thread_count_after_repair'], 1)
            self.assertEqual(repair['skipped_active_threads'], ['thread-two'])

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

    def test_resume_resets_clean_stale_reused_worktree_before_running(self):
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
            old_head = git(worktrees / 'codebase-review-s1', 'rev-parse', 'HEAD').stdout.strip()
            (repo / 'src' / 'b.txt').write_text('base moved\n')
            git(repo, 'add', 'src/b.txt')
            git(repo, 'commit', '-m', 'advance base')
            new_base = git(repo, 'rev-parse', 'main').stdout.strip()
            run_dir.mkdir()
            (run_dir / 'run-state.json').write_text(json.dumps(bound_state(
                repo,
                run_dir,
                plan,
                {
                    'SLICE-001': {
                        'status': 'failed',
                        'branch': 'codebase-review/s1',
                        'error': 'interrupted before codex made changes',
                    }
                },
            )))
            bin_dir = Path(td) / 'bin'
            bin_dir.mkdir()
            fake_codex_bin(bin_dir, """
                import pathlib
                pathlib.Path('src/a.txt').write_text('changed after reset\\n')
            """)
            env = {**os.environ, 'PATH': f'{bin_dir}{os.pathsep}{os.environ["PATH"]}'}
            result = run([
                PY, str(SCRIPT), str(plan), str(plan),
                '--run-dir', str(run_dir),
                '--worktree-dir', str(worktrees),
                '--resume',
                '--reuse-worktrees',
                '--base-ref', 'main',
            ], cwd=repo, env=env)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            state = json.loads((run_dir / 'run-state.json').read_text())
            slice_state = state['slices']['SLICE-001']
            self.assertEqual(slice_state['status'], 'succeeded')
            self.assertEqual(slice_state['base_sha'], new_base)
            self.assertEqual(slice_state['reused_stale_worktree_reset']['old_head'], old_head)
            self.assertEqual(slice_state['reused_stale_worktree_reset']['new_head'], new_base)

    def test_resume_can_continue_failed_slice_with_scoped_dirty_worktree(self):
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
            worktree = worktrees / 'codebase-review-s1'
            (worktree / 'src' / 'a.txt').write_text('dirty allowed change\n')
            artifact_dir = worktree / 'docs' / 'agentic-system'
            artifact_dir.mkdir(parents=True)
            (artifact_dir / 'SLICE-001.review-result.json').write_text('{}\n')
            run_dir.mkdir()
            (run_dir / 'run-state.json').write_text(json.dumps(bound_state(
                repo,
                run_dir,
                plan,
                {
                    'SLICE-001': {
                        'status': 'failed',
                        'branch': 'codebase-review/s1',
                        'base_ref': 'origin/main',
                        'error': 'outside scope changes: docs/agentic-system/',
                    }
                },
            )))
            bin_dir = Path(td) / 'bin'
            bin_dir.mkdir()
            fake_codex_bin(bin_dir, "raise SystemExit(99)")
            env = {**os.environ, 'PATH': f'{bin_dir}{os.pathsep}{os.environ["PATH"]}'}
            result = run([
                PY, str(SCRIPT), str(plan), str(plan),
                '--run-dir', str(run_dir),
                '--worktree-dir', str(worktrees),
                '--resume',
                '--reuse-worktrees',
            ], cwd=repo, env=env)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            state = json.loads((run_dir / 'run-state.json').read_text())
            self.assertEqual(state['slices']['SLICE-001']['status'], 'succeeded')
            self.assertTrue(state['slices']['SLICE-001']['resumed_from_dirty_worktree'])
            self.assertTrue((run_dir / 'slices' / 'SLICE-001' / 'SLICE-001.review-result.json').exists())

    def test_resume_refuses_dirty_running_slice_worktree(self):
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
            worktree = worktrees / 'codebase-review-s1'
            (worktree / 'src' / 'a.txt').write_text('partial interrupted edit\n')
            run_dir.mkdir()
            (run_dir / 'run-state.json').write_text(json.dumps(bound_state(
                repo,
                run_dir,
                plan,
                {
                    'SLICE-001': {
                        'status': 'running',
                        'branch': 'codebase-review/s1',
                        'error': None,
                    }
                },
            )))
            bin_dir = Path(td) / 'bin'
            bin_dir.mkdir()
            fake_codex_bin(bin_dir, """
                raise SystemExit(99)
            """)
            env = {**os.environ, 'PATH': f'{bin_dir}{os.pathsep}{os.environ["PATH"]}'}
            result = run([
                PY, str(SCRIPT), str(plan), str(plan),
                '--run-dir', str(run_dir),
                '--worktree-dir', str(worktrees),
                '--resume',
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
