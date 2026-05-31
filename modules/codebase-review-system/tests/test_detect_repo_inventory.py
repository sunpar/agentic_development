import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'detect_repo_inventory.py'
PY = sys.executable


class DetectRepoInventoryTests(unittest.TestCase):
    def test_dry_run_infers_package_managers_from_manifests(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / 'repo'
            repo.mkdir()
            (repo / 'package.json').write_text('{"scripts":{"test":"jest"}}\n', encoding='utf-8')
            (repo / 'pyproject.toml').write_text('[project]\nname = "demo"\n', encoding='utf-8')

            result = subprocess.run(
                [PY, str(SCRIPT), '--dry-run'],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            inventory = json.loads(result.stdout)

        self.assertEqual(inventory['package_managers'], ['npm', 'python'])
        self.assertEqual(inventory['manifests'], ['package.json', 'pyproject.toml'])

    def test_package_json_does_not_add_npm_when_stronger_js_lockfile_exists(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / 'repo'
            repo.mkdir()
            (repo / 'package.json').write_text('{"scripts":{"test":"vitest"}}\n', encoding='utf-8')
            (repo / 'pnpm-lock.yaml').write_text('lockfileVersion: 9\n', encoding='utf-8')

            result = subprocess.run(
                [PY, str(SCRIPT), '--dry-run'],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            inventory = json.loads(result.stdout)

        self.assertEqual(inventory['package_managers'], ['pnpm'])


if __name__ == '__main__':
    unittest.main()
