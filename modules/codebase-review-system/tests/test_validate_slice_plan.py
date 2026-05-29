import json, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
PY=sys.executable

import unittest
class TestSlicePlan(unittest.TestCase):
    def test_valid_and_invalid(self):
        self.assertEqual(subprocess.run([PY, str(ROOT/'scripts/validate_slice_plan.py'), str(ROOT/'fixtures/sample_slice_plan.valid.json')]).returncode, 0)
        self.assertNotEqual(subprocess.run([PY, str(ROOT/'scripts/validate_slice_plan.py'), str(ROOT/'fixtures/sample_slice_plan.invalid.json')]).returncode, 0)

    def test_rejects_unknown_wave_slice(self):
        data = json.loads((ROOT/'fixtures/sample_slice_plan.valid.json').read_text())
        data['waves'][0]['slice_ids'] = ['SLICE-404']
        self.assertInvalid(data, 'waves[0].slice_ids unknown SLICE-404')

    def test_rejects_slice_missing_from_waves(self):
        data = json.loads((ROOT/'fixtures/sample_slice_plan.valid.json').read_text())
        data['waves'][0]['slice_ids'] = []
        data['waves'][0]['integration_order'] = []
        self.assertInvalid(data, 'SLICE-001 must appear in exactly one wave')

    def test_rejects_same_wave_edit_conflict(self):
        data = json.loads((ROOT/'fixtures/sample_slice_plan.valid.json').read_text())
        second = dict(data['slices'][0])
        second['id'] = 'SLICE-002'
        second['branch'] = 'codebase-review/SLICE-002-review-core-flow'
        data['slices'].append(second)
        data['waves'][0]['slice_ids'] = ['SLICE-001', 'SLICE-002']
        data['waves'][0]['integration_order'] = ['SLICE-001', 'SLICE-002']
        self.assertInvalid(data, 'same-wave edit conflict')

    def test_rejects_empty_context_and_test_plans(self):
        data = json.loads((ROOT/'fixtures/sample_slice_plan.valid.json').read_text())
        data['slices'][0]['files_to_read'] = []
        data['slices'][0]['tests_to_read'] = []
        data['slices'][0]['review_questions'] = []
        data['slices'][0]['acceptance_criteria'] = []

        self.assertInvalid(data, 'SLICE-001.files_to_read required')
        self.assertInvalid(data, 'SLICE-001.tests_to_read required')
        self.assertInvalid(data, 'SLICE-001.review_questions required')
        self.assertInvalid(data, 'SLICE-001.acceptance_criteria required')

    def test_schema_encodes_validator_constraints(self):
        schema = json.loads((ROOT/'schemas/slice_plan.schema.json').read_text())
        slice_schema = schema['properties']['slices']['items']
        props = slice_schema['properties']
        wave_schema = schema['properties']['waves']['items']

        self.assertIn('waves', schema['required'])
        self.assertEqual(schema['properties']['slices']['minItems'], 1)
        self.assertEqual(props['id']['pattern'], r'^[^\s]+$')
        self.assertEqual(props['slice_type']['enum'], [
            'review-only',
            'review-refactor',
            'refactor-simplify',
            'refactor-performance',
            'refactor-api-coherence',
            'refactor-dead-code',
        ])
        self.assertEqual(props['risk']['enum'], ['low', 'medium', 'high', 'critical'])
        self.assertEqual(props['files_to_read']['minItems'], 1)
        self.assertEqual(props['tests_to_read']['minItems'], 1)
        self.assertEqual(props['verification_commands']['minItems'], 1)
        self.assertEqual(props['expected_pr_size']['properties']['max_files_changed']['minimum'], 1)
        self.assertEqual(wave_schema['properties']['slice_ids']['minItems'], 1)

    def test_generated_slice_plan_serializes_slices(self):
        feature_model = {
            'repo': {'test_commands': ['python3 -m unittest']},
            'features': [
                {
                    'id': 'FEAT-1',
                    'name': 'Feature One',
                    'intended_behavior': 'Preserve behavior.',
                    'code_paths': ['src/a.py'],
                    'docs': ['README.md'],
                    'tests': ['tests/test_a.py'],
                    'entry_points': [],
                    'known_risks': [],
                },
                {
                    'id': 'FEAT-2',
                    'name': 'Feature Two',
                    'intended_behavior': 'Preserve behavior.',
                    'code_paths': ['src/b.py'],
                    'docs': ['README.md'],
                    'tests': ['tests/test_b.py'],
                    'entry_points': [],
                    'known_risks': [],
                },
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            model_path = td_path/'feature-model.json'
            out_dir = td_path/'review'
            model_path.write_text(json.dumps(feature_model), encoding='utf-8')
            result = subprocess.run([PY, str(ROOT/'scripts/generate_slice_plan.py'), str(model_path), '--output-dir', str(out_dir)], text=True, stdout=subprocess.PIPE)
            self.assertEqual(result.returncode, 0, result.stdout)
            plan = json.loads((out_dir/'slice-plan.json').read_text())
        self.assertEqual([[s] for s in ['SLICE-001', 'SLICE-002']], [wave['slice_ids'] for wave in plan['waves']])
        self.assertIn('serialized by default', plan['waves'][0]['parallel_safety_rationale'])

    def assertInvalid(self, data, expected):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)/'slice-plan.json'
            path.write_text(json.dumps(data), encoding='utf-8')
            result = subprocess.run([PY, str(ROOT/'scripts/validate_slice_plan.py'), str(path)], text=True, stdout=subprocess.PIPE)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(expected, result.stdout)
if __name__=='__main__': unittest.main()
