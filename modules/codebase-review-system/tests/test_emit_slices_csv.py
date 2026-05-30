import csv
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
PY=sys.executable

import tempfile, unittest
class TestCsv(unittest.TestCase):
    def test_emit(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as d:
            out=Path(d)/'slices.csv'
            self.assertEqual(subprocess.run([PY, str(ROOT/'scripts/emit_slices_csv.py'), str(ROOT/'fixtures/sample_slice_plan.valid.json'), '--output', str(out)]).returncode,0)
            self.assertIn('SLICE-001', out.read_text())

    def test_dry_run_outputs_csv_without_writing_file(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as d:
            out = Path(d) / 'slices.csv'
            result = subprocess.run(
                [
                    PY,
                    str(ROOT / 'scripts/emit_slices_csv.py'),
                    str(ROOT / 'fixtures/sample_slice_plan.valid.json'),
                    '--output',
                    str(out),
                    '--dry-run',
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(out.exists())
            self.assertIn('DRY-RUN', result.stdout)
            rows = list(csv.DictReader(result.stdout.splitlines()[1:]))
            self.assertEqual(rows[0]['id'], 'SLICE-001')
if __name__=='__main__': unittest.main()
