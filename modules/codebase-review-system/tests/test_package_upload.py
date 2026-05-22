import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

import unittest


class TestPackageUpload(unittest.TestCase):
    def test_dry_run(self):
        result = subprocess.run(
            [PY, str(ROOT/'scripts/package_upload.py'), '--dry-run'],
            text=True,
            stdout=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn('would include:', result.stdout)


if __name__ == '__main__':
    unittest.main()
