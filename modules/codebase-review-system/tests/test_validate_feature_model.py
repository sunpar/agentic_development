import subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
PY=sys.executable

import unittest
class TestFeatureModel(unittest.TestCase):
    def test_valid_and_invalid(self):
        self.assertEqual(subprocess.run([PY, str(ROOT/'scripts/validate_feature_model.py'), str(ROOT/'fixtures/sample_feature_model.valid.json')]).returncode, 0)
        self.assertNotEqual(subprocess.run([PY, str(ROOT/'scripts/validate_feature_model.py'), str(ROOT/'fixtures/sample_feature_model.invalid.json')]).returncode, 0)
if __name__=='__main__': unittest.main()
