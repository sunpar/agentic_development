import subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
PY=sys.executable

import unittest
class TestSync(unittest.TestCase):
    def test_dry_run(self):
        self.assertEqual(subprocess.run([PY, str(ROOT/'scripts/sync_skills.py'), '--dry-run']).returncode,0)
if __name__=='__main__': unittest.main()
