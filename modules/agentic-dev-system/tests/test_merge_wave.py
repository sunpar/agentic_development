import json
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from support_paths import script_path


SCRIPT = script_path('merge_wave.py')


def load_module():
    spec = importlib.util.spec_from_file_location('merge_wave', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MergeWaveTests(unittest.TestCase):
    def test_merge_is_noop_without_explicit_merge_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'
            repo.mkdir()
            subprocess.run(['git', 'init'], cwd=repo, text=True, capture_output=True, check=True)
            (repo / 'README.md').write_text('sample\n', encoding='utf-8')
            subprocess.run(['git', 'add', 'README.md'], cwd=repo, text=True, capture_output=True, check=True)
            subprocess.run(['git', 'commit', '-m', 'init'], cwd=repo, text=True, capture_output=True, check=True)
            plan = Path(tmp) / 'plan.json'
            plan.write_text(json.dumps({
                'tasks': [{'id': 'T1', 'wave': 1, 'branch': 'task-t1', 'verification_commands': []}],
                'waves': [{'wave': 1, 'task_ids': ['T1']}],
            }), encoding='utf-8')

            result = subprocess.run([
                sys.executable,
                str(SCRIPT),
                '--plan', str(plan),
                '--wave', '1',
                '--workdir', str(repo),
            ], text=True, capture_output=True)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('MERGE DISABLED', result.stdout)
            branches = subprocess.run(['git', 'branch', '--list', 'wave-1-integration'], cwd=repo, text=True, capture_output=True, check=True)
            self.assertEqual(branches.stdout.strip(), '')

    def test_merge_and_no_merge_are_mutually_exclusive(self):
        result = subprocess.run([
            sys.executable,
            str(SCRIPT),
            '--plan', '/tmp/missing.json',
            '--wave', '1',
            '--merge',
            '--no-merge',
        ], text=True, capture_output=True)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn('not allowed with argument', result.stderr)

    def test_verification_command_split_preserves_quoted_args(self):
        module = load_module()
        self.assertEqual(
            module.split_command('python -c "print(1)"'),
            ['python', '-c', 'print(1)'],
        )


if __name__ == '__main__':
    unittest.main()
