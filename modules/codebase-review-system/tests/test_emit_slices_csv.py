import subprocess, sys
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
if __name__=='__main__': unittest.main()
