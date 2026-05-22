import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from support_paths import fixture_path, script_path


SCRIPT = script_path('emit_tasks_csv.py')
FIXTURE = fixture_path('sample_plan.valid.json')


class EmitTasksCsvTests(unittest.TestCase):
    def test_emit_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'tasks.csv'
            result = subprocess.run([sys.executable, str(SCRIPT), str(FIXTURE), '--output', str(out)], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0)
            self.assertTrue(out.exists())
            rows = list(csv.DictReader(out.read_text(encoding='utf-8').splitlines()))
            self.assertEqual(rows[0]['id'], 'T1')
            self.assertEqual(rows[0]['wave'], '1')

    def test_dry_run_output_does_not_write_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'tasks.csv'
            result = subprocess.run([sys.executable, str(SCRIPT), str(FIXTURE), '--output', str(out), '--dry-run'], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(out.exists())
            self.assertIn('DRY-RUN', result.stdout)


if __name__ == '__main__':
    unittest.main()
