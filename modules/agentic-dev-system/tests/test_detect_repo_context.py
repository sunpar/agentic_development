import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from support_paths import script_path


SCRIPT = script_path('detect_repo_context.py')


class DetectRepoContextTests(unittest.TestCase):
    def test_dry_run_does_not_write_output_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'
            repo.mkdir()
            subprocess.run(['git', 'init'], cwd=repo, text=True, capture_output=True, check=True)
            out_dir = Path(tmp) / 'agent-context'

            result = subprocess.run([
                sys.executable,
                str(SCRIPT),
                '--repo', str(repo),
                '--out', str(out_dir),
                '--dry-run',
            ], text=True, capture_output=True)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(out_dir.exists())
            self.assertIn('DRY-RUN', result.stdout)


if __name__ == '__main__':
    unittest.main()
