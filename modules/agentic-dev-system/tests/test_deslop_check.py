import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from support_paths import script_path

SCRIPT = script_path('deslop_check.py')


class DeslopCheckTests(unittest.TestCase):
    def test_warning_mode_detects(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            p = tmp_path / 'sample.py'
            p.write_text('''\n# This function does this every time.\nprint("hello")\n''', encoding='utf-8')
            result = subprocess.run([sys.executable, str(SCRIPT), '--json', str(tmp_path / 'out.json'), str(p)], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0)

    def test_strict_mode_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            p = tmp_path / 'sample.py'
            p.write_text('''\n# This function does this every time.\nprint("hello")\n''', encoding='utf-8')
            result = subprocess.run([sys.executable, str(SCRIPT), '--strict', str(p)], text=True, capture_output=True)
            self.assertEqual(result.returncode, 1)

    def test_no_paths_outside_git_repo_does_not_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, str(SCRIPT)], cwd=tmp, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('No obvious slop detected', result.stdout)


if __name__ == '__main__':
    unittest.main()
