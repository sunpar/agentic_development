import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'update_feature_model.py'
PY = sys.executable


class UpdateFeatureModelTests(unittest.TestCase):
    def test_status_note_is_not_duplicated(self):
        data = {
            'repo': {'name': 'demo'},
            'unknowns': ['updated'],
        }
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'feature-model.json'
            path.write_text(json.dumps(data), encoding='utf-8')

            result = subprocess.run(
                [PY, str(SCRIPT), str(path), '--status-note', 'updated'],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            updated = json.loads(path.read_text(encoding='utf-8'))

        self.assertEqual(updated['unknowns'], ['updated'])

    def test_dry_run_does_not_write_file(self):
        data = {'unknowns': []}
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'feature-model.json'
            path.write_text(json.dumps(data), encoding='utf-8')

            result = subprocess.run(
                [PY, str(SCRIPT), str(path), '--status-note', 'new note', '--dry-run'],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            dry_run_data = json.loads(result.stdout)
            persisted = json.loads(path.read_text(encoding='utf-8'))

        self.assertEqual(dry_run_data['unknowns'], ['new note'])
        self.assertEqual(persisted['unknowns'], [])


if __name__ == '__main__':
    unittest.main()
