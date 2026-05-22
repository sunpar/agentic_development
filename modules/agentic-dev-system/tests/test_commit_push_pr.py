import os
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from support_paths import script_path


SCRIPT = script_path('commit_push_pr.py')


def load_module():
    spec = importlib.util.spec_from_file_location('commit_push_pr', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CommitPushPrTests(unittest.TestCase):
    def test_dry_run_stage_all_does_not_require_gh_auth_or_staging(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(['git', 'init'], cwd=repo, text=True, capture_output=True, check=True)
            subprocess.run(['git', 'checkout', '-b', 'agentic-test'], cwd=repo, text=True, capture_output=True, check=True)
            (repo / 'new.txt').write_text('hello\n', encoding='utf-8')
            env = os.environ.copy()
            env['GH_CONFIG_DIR'] = str(repo / '.missing-gh-config')

            result = subprocess.run([
                sys.executable,
                str(SCRIPT),
                '--stage-all',
                '--dry-run',
            ], cwd=repo, env=env, text=True, capture_output=True)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('DRY-RUN: would stage', result.stdout)
            self.assertIn('new.txt', result.stdout)
            staged = subprocess.run(['git', 'diff', '--name-only', '--cached'], cwd=repo, text=True, capture_output=True, check=True)
            self.assertEqual(staged.stdout.strip(), '')

    def test_current_pr_uses_gh_pr_list_head_not_view_head(self):
        module = load_module()
        calls = []

        def fake_run(cmd, check=True, capture=False):
            calls.append(cmd)

            class Result:
                returncode = 0
                stdout = '[{"number": 12, "url": "https://github.com/owner/repo/pull/12"}]'
                stderr = ''

            return Result()

        module.run = fake_run
        self.assertEqual(module.current_pr('feature/test'), 'https://github.com/owner/repo/pull/12')
        self.assertEqual(calls[0], ['gh', 'pr', 'list', '--head', 'feature/test', '--json', 'number,url', '--limit', '1'])


if __name__ == '__main__':
    unittest.main()
