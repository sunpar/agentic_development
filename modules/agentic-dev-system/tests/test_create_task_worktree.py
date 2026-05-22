import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from support_paths import script_path


SCRIPT = script_path('create_task_worktree.py')


class CreateTaskWorktreeTests(unittest.TestCase):
    def test_dry_run_does_not_create_worktree_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'
            repo.mkdir()
            subprocess.run(['git', 'init'], cwd=repo, text=True, capture_output=True, check=True)
            (repo / 'README.md').write_text('sample\n', encoding='utf-8')
            subprocess.run(['git', 'add', 'README.md'], cwd=repo, text=True, capture_output=True, check=True)
            subprocess.run(['git', 'commit', '-m', 'init'], cwd=repo, text=True, capture_output=True, check=True)

            plan = repo / 'plan.json'
            plan.write_text(json.dumps({
                'tasks': [{'id': 'T1', 'branch': 'agentic-t1'}],
            }), encoding='utf-8')
            worktrees = Path(tmp) / 'worktrees'

            result = subprocess.run([
                sys.executable,
                str(SCRIPT),
                '--plan', str(plan),
                '--task-id', 'T1',
                '--worktree-dir', str(worktrees),
                '--dry-run',
            ], cwd=repo, text=True, capture_output=True)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(worktrees.exists())
            self.assertIn('DRY-RUN', result.stdout)

    def test_slash_branch_name_is_preserved_but_worktree_path_is_sanitized(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'
            repo.mkdir()
            subprocess.run(['git', 'init'], cwd=repo, text=True, capture_output=True, check=True)
            (repo / 'README.md').write_text('sample\n', encoding='utf-8')
            subprocess.run(['git', 'add', 'README.md'], cwd=repo, text=True, capture_output=True, check=True)
            subprocess.run(['git', 'commit', '-m', 'init'], cwd=repo, text=True, capture_output=True, check=True)

            plan = repo / 'plan.json'
            plan.write_text(json.dumps({
                'tasks': [{'id': 'T1', 'branch': 'feature/e1-t1-health-route'}],
            }), encoding='utf-8')
            worktrees = Path(tmp) / 'worktrees'

            result = subprocess.run([
                sys.executable,
                str(SCRIPT),
                '--plan', str(plan),
                '--task-id', 'T1',
                '--worktree-dir', str(worktrees),
                '--dry-run',
            ], cwd=repo, text=True, capture_output=True)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('NEXT: branch: feature/e1-t1-health-route', result.stdout)
            self.assertIn(str(worktrees / 'feature-e1-t1-health-route'), result.stdout)

    def test_new_branch_uses_lowercase_b_not_reset_b(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'
            repo.mkdir()
            subprocess.run(['git', 'init'], cwd=repo, text=True, capture_output=True, check=True)
            (repo / 'README.md').write_text('sample\n', encoding='utf-8')
            subprocess.run(['git', 'add', 'README.md'], cwd=repo, text=True, capture_output=True, check=True)
            subprocess.run(['git', 'commit', '-m', 'init'], cwd=repo, text=True, capture_output=True, check=True)

            plan = repo / 'plan.json'
            plan.write_text(json.dumps({'tasks': [{'id': 'T1', 'branch': 'agentic-t1'}]}), encoding='utf-8')
            result = subprocess.run([
                sys.executable,
                str(SCRIPT),
                '--plan', str(plan),
                '--task-id', 'T1',
                '--worktree-dir', str(Path(tmp) / 'worktrees'),
                '--dry-run',
            ], cwd=repo, text=True, capture_output=True)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('git worktree add -b agentic-t1', result.stdout)
            self.assertNotIn(' -B ', result.stdout)

    def test_existing_branch_requires_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'
            repo.mkdir()
            subprocess.run(['git', 'init'], cwd=repo, text=True, capture_output=True, check=True)
            (repo / 'README.md').write_text('sample\n', encoding='utf-8')
            subprocess.run(['git', 'add', 'README.md'], cwd=repo, text=True, capture_output=True, check=True)
            subprocess.run(['git', 'commit', '-m', 'init'], cwd=repo, text=True, capture_output=True, check=True)
            subprocess.run(['git', 'branch', 'agentic-t1'], cwd=repo, text=True, capture_output=True, check=True)

            plan = repo / 'plan.json'
            plan.write_text(json.dumps({'tasks': [{'id': 'T1', 'branch': 'agentic-t1'}]}), encoding='utf-8')
            result = subprocess.run([
                sys.executable,
                str(SCRIPT),
                '--plan', str(plan),
                '--task-id', 'T1',
                '--worktree-dir', str(Path(tmp) / 'worktrees'),
                '--dry-run',
            ], cwd=repo, text=True, capture_output=True)

            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn('branch already exists', result.stdout)

    def test_reuse_existing_branch_does_not_reset_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'
            repo.mkdir()
            subprocess.run(['git', 'init'], cwd=repo, text=True, capture_output=True, check=True)
            (repo / 'README.md').write_text('sample\n', encoding='utf-8')
            subprocess.run(['git', 'add', 'README.md'], cwd=repo, text=True, capture_output=True, check=True)
            subprocess.run(['git', 'commit', '-m', 'init'], cwd=repo, text=True, capture_output=True, check=True)
            subprocess.run(['git', 'branch', 'agentic-t1'], cwd=repo, text=True, capture_output=True, check=True)

            plan = repo / 'plan.json'
            plan.write_text(json.dumps({'tasks': [{'id': 'T1', 'branch': 'agentic-t1'}]}), encoding='utf-8')
            result = subprocess.run([
                sys.executable,
                str(SCRIPT),
                '--plan', str(plan),
                '--task-id', 'T1',
                '--worktree-dir', str(Path(tmp) / 'worktrees'),
                '--reuse',
                '--dry-run',
            ], cwd=repo, text=True, capture_output=True)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('git worktree add', result.stdout)
            self.assertIn('agentic-t1', result.stdout)
            self.assertNotIn(' -B ', result.stdout)
            self.assertNotIn(' -b ', result.stdout)


if __name__ == '__main__':
    unittest.main()
