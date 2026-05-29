import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'feature_task_generator.py'
PY = sys.executable


def run(cmd, cwd=None):
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


class FeatureTaskGeneratorTests(unittest.TestCase):
    def test_generates_feature_implementation_tasks_and_artifacts(self):
        feature_model = {
            'repo': {
                'name': 'sample',
                'test_commands': ['python3 -m unittest'],
            },
            'features': [
                {
                    'id': 'FEAT-CORE',
                    'name': 'Core Flow',
                    'summary': 'Runs the core behavior.',
                    'intended_behavior': 'Process input deterministically.',
                    'code_paths': ['src/app.py'],
                    'docs': ['README.md'],
                    'tests': ['tests/test_app.py'],
                    'entry_points': ['src/app.py'],
                    'known_risks': ['low coverage'],
                    'related_features': [],
                },
                {
                    'id': 'FEAT-REPORTS',
                    'name': 'Reports',
                    'summary': 'Produces reports from core output.',
                    'intended_behavior': 'Render report output.',
                    'code_paths': ['src/reports.py'],
                    'docs': ['docs/reports.md'],
                    'tests': ['tests/test_reports.py'],
                    'entry_points': ['src/reports.py'],
                    'known_risks': [],
                    'related_features': ['FEAT-CORE'],
                },
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            model_path = td_path / 'feature-model.json'
            out_dir = td_path / 'implementation'
            model_path.write_text(json.dumps(feature_model), encoding='utf-8')

            result = run([PY, str(SCRIPT), str(model_path), '--output-dir', str(out_dir)])

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            plan = json.loads((out_dir / 'implementation-plan.json').read_text())
            with (out_dir / 'tasks.csv').open() as handle:
                rows = list(csv.DictReader(handle))
            task_markdown = (out_dir / 'tasks' / 'TASK-001.md').read_text()

        self.assertEqual([task['id'] for task in plan['tasks']], ['TASK-001', 'TASK-002'])
        self.assertEqual([epic['id'] for epic in plan['epics']], ['EPIC-001', 'EPIC-002'])
        self.assertEqual(plan['milestones'][0]['epic_ids'], ['EPIC-001', 'EPIC-002'])
        self.assertEqual(plan['releases'][0]['milestone_ids'], ['MILESTONE-001'])
        self.assertEqual(plan['tasks'][1]['dependencies'], ['TASK-001'])
        self.assertEqual(plan['waves'][1]['task_ids'], ['TASK-002'])
        self.assertEqual(rows[0]['id'], 'TASK-001')
        self.assertNotIn('slice_type', plan['tasks'][0])
        for key in [
            'context_bundle',
            'context_to_load',
            'write_set',
            'implementation_steps',
            'tests_to_write_first',
            'tdd_plan',
            'verification_commands',
            'acceptance_criteria',
            'parallel_conflicts',
        ]:
            self.assertIn(key, plan['tasks'][0])
        self.assertIn('Tests To Write First', task_markdown)
        self.assertIn('python3 -m unittest', task_markdown)


if __name__ == '__main__':
    unittest.main()
