import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'build_feature_model.py'
PY = sys.executable


class BuildFeatureModelTests(unittest.TestCase):
    def test_infers_languages_and_test_commands_from_inventory_manifests(self):
        inventory = {
            'repo': {'name': 'demo', 'root': '/tmp/demo'},
            'source_roots': ['src'],
            'docs': ['README.md'],
            'tests': ['tests/test_app.py'],
            'schemas': [],
            'manifests': ['package.json', 'pyproject.toml'],
            'package_managers': ['npm', 'python'],
            'ci_files': ['.github/workflows/ci.yml'],
        }
        with tempfile.TemporaryDirectory() as td:
            inventory_path = Path(td) / 'repo-inventory.json'
            inventory_path.write_text(json.dumps(inventory), encoding='utf-8')

            result = subprocess.run(
                [PY, str(SCRIPT), str(inventory_path), '--dry-run'],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            model = json.loads(result.stdout)

        self.assertEqual(model['repo']['primary_languages'], ['JavaScript/TypeScript', 'Python'])
        self.assertEqual(model['repo']['test_commands'], ['npm test', 'python -m pytest'])
        self.assertEqual(model['repo']['package_managers'], ['npm', 'python'])


if __name__ == '__main__':
    unittest.main()
