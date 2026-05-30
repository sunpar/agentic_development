import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'run_slice_with_codex.py'
FIXTURE = ROOT / 'fixtures' / 'sample_slice_plan.valid.json'
PY = sys.executable


class RunSliceWithCodexTests(unittest.TestCase):
    def test_missing_slice_id_returns_clear_error(self):
        result = subprocess.run(
            [PY, str(SCRIPT), str(FIXTURE), 'SLICE-404', '--dry-run'],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('slice SLICE-404 not found', result.stderr)
        self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()
