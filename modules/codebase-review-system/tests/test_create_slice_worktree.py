import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
SCRIPT = ROOT / 'scripts' / 'create_slice_worktree.py'


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


class TestCreateSliceWorktree(unittest.TestCase):
    def make_repo(self, path):
        self.assertEqual(run(['git', 'init'], path).returncode, 0)
        self.assertEqual(run(['git', 'config', 'user.email', 'test@example.com'], path).returncode, 0)
        self.assertEqual(run(['git', 'config', 'user.name', 'Test User'], path).returncode, 0)
        (path/'README.md').write_text('test\n', encoding='utf-8')
        self.assertEqual(run(['git', 'add', 'README.md'], path).returncode, 0)
        self.assertEqual(run(['git', 'commit', '-m', 'init'], path).returncode, 0)

    def write_plan(self, path, branch='codebase-review/SLICE-001-review-core'):
        plan = {
            'slices': [
                {
                    'id': 'SLICE-001',
                    'branch': branch,
                }
            ]
        }
        path.write_text(json.dumps(plan), encoding='utf-8')

    def test_dry_run_uses_configurable_worktree_dir_and_base_ref(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / 'repo'
            repo.mkdir()
            self.make_repo(repo)
            plan = repo / 'slice-plan.json'
            self.write_plan(plan)
            worktrees = Path(td) / 'worktrees'
            result = run([PY, str(SCRIPT), str(plan), 'SLICE-001', '--worktree-dir', str(worktrees), '--base-ref', 'HEAD', '--dry-run'], repo)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('git worktree add -b codebase-review/SLICE-001-review-core', result.stdout)
        self.assertIn(str(worktrees / 'codebase-review-SLICE-001-review-core'), result.stdout)

    def test_existing_branch_requires_reuse(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / 'repo'
            repo.mkdir()
            self.make_repo(repo)
            self.assertEqual(run(['git', 'branch', 'codebase-review/SLICE-001-review-core'], repo).returncode, 0)
            plan = repo / 'slice-plan.json'
            self.write_plan(plan)
            result = run([PY, str(SCRIPT), str(plan), 'SLICE-001', '--dry-run'], repo)
        self.assertEqual(result.returncode, 2)
        self.assertIn('branch already exists', result.stdout)

    def test_reuse_existing_branch_does_not_reset_branch(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / 'repo'
            repo.mkdir()
            self.make_repo(repo)
            self.assertEqual(run(['git', 'branch', 'codebase-review/SLICE-001-review-core'], repo).returncode, 0)
            plan = repo / 'slice-plan.json'
            self.write_plan(plan)
            result = run([PY, str(SCRIPT), str(plan), 'SLICE-001', '--reuse', '--dry-run'], repo)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('git worktree add ', result.stdout)
        self.assertNotIn(' -b ', result.stdout)

    def test_invalid_branch_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / 'repo'
            repo.mkdir()
            self.make_repo(repo)
            plan = repo / 'slice-plan.json'
            self.write_plan(plan, '../bad')
            result = run([PY, str(SCRIPT), str(plan), 'SLICE-001', '--dry-run'], repo)
        self.assertEqual(result.returncode, 2)
        self.assertIn('invalid branch name', result.stdout)


if __name__ == '__main__':
    unittest.main()
