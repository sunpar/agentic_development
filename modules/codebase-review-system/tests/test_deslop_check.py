import subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
PY=sys.executable

import tempfile, unittest
class TestDeslop(unittest.TestCase):
    def test_strict_fails(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as d:
            p=Path(d)/'x.md'; p.write_text('As requested, this is robust.\n')
            self.assertNotEqual(subprocess.run([PY, str(ROOT/'scripts/deslop_check.py'), str(p), '--strict']).returncode,0)
if __name__=='__main__': unittest.main()
