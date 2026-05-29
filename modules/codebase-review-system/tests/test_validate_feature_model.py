import json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
PY=sys.executable

import unittest
class TestFeatureModel(unittest.TestCase):
    def test_valid_and_invalid(self):
        self.assertEqual(subprocess.run([PY, str(ROOT/'scripts/validate_feature_model.py'), str(ROOT/'fixtures/sample_feature_model.valid.json')]).returncode, 0)
        self.assertNotEqual(subprocess.run([PY, str(ROOT/'scripts/validate_feature_model.py'), str(ROOT/'fixtures/sample_feature_model.invalid.json')]).returncode, 0)

    def test_schema_encodes_validator_constraints(self):
        schema = json.loads((ROOT/'schemas/feature_model.schema.json').read_text())
        feature_schema = schema['properties']['features']['items']
        repo_schema = schema['properties']['repo']

        self.assertEqual(schema['properties']['features']['minItems'], 1)
        self.assertEqual(schema['properties']['evidence']['minItems'], 1)
        self.assertEqual(feature_schema['properties']['id']['pattern'], r'^[^\s]+$')
        self.assertEqual(feature_schema['properties']['confidence']['enum'], ['high', 'medium', 'low'])
        self.assertEqual(feature_schema['properties']['code_paths']['minItems'], 1)
        self.assertEqual(repo_schema['properties']['test_commands']['type'], 'array')
if __name__=='__main__': unittest.main()
