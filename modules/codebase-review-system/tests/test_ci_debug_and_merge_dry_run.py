import json, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
PY=sys.executable

import unittest
class TestCiMerge(unittest.TestCase):
    def run_ci(self, *args):
        return subprocess.run(
            [PY, str(ROOT/'scripts/ci_debug_and_merge.py'), '--dry-run', *args],
            text=True,
            stdout=subprocess.PIPE,
        )

    def test_dry_run(self):
        result = self.run_ci()
        self.assertEqual(result.returncode, 0)
        self.assertIn('merge skipped: --allow-merge not provided', result.stdout)
        self.assertNotIn('gh pr merge', result.stdout)

    def test_allow_merge_is_rejected_by_legacy_helper(self):
        result = self.run_ci('--allow-merge')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('merge execution moved to merge_gate.py', result.stdout)
        self.assertNotIn('gh pr merge', result.stdout)

    def test_no_merge_overrides_allow_merge(self):
        result = self.run_ci('--allow-merge', '--no-merge')
        self.assertEqual(result.returncode, 0)
        self.assertIn('merge skipped', result.stdout)
        self.assertNotIn('gh pr merge', result.stdout)

    def test_pr_number_is_passed_to_checks_and_merge(self):
        result = self.run_ci('--pr', '123', '--allow-merge')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('gh pr checks 123 --watch=false', result.stdout)
        self.assertIn('merge execution moved to merge_gate.py', result.stdout)
        self.assertNotIn('gh pr merge', result.stdout)

    def test_pr_only_overrides_allow_merge(self):
        result = self.run_ci('--allow-merge', '--pr-only')
        self.assertEqual(result.returncode, 0)
        self.assertIn('merge skipped', result.stdout)
        self.assertNotIn('gh pr merge', result.stdout)

    def test_orchestrator_pr_only_overrides_allow_merge(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            slice_plan = td_path/'slice-plan.json'
            waves = td_path/'waves.json'
            plan = {
                'slices': [{
                    'id': 'SLICE-001',
                    'feature_id': 'FEAT',
                    'title': 'Slice',
                    'slice_type': 'refactor-simplify',
                    'description': 'desc',
                    'intended_behavior': 'unchanged',
                    'why_this_slice_exists': 'test',
                    'files_to_read': ['src/a.txt'],
                    'docs_to_read': [],
                    'tests_to_read': ['tests/test_slice.py'],
                    'files_allowed_to_edit': ['src/a.txt'],
                    'files_not_allowed_to_edit': [],
                    'entry_points': ['src/a.txt'],
                    'invariants': ['unchanged'],
                    'non_goals': ['features'],
                    'review_questions': ['safe?'],
                    'refactor_targets': ['simplify'],
                    'verification_commands': ['python3 -c "print(1)"'],
                    'expected_pr_size': {'max_files_changed': 1, 'max_lines_changed_soft': 20},
                    'dependencies': [],
                    'parallel_conflicts': [],
                    'risk': 'low',
                    'risk_notes': [],
                    'acceptance_criteria': ['passes'],
                    'branch': 'codebase-review/s1',
                    'pr_title': '[codebase-review] slice',
                    'review_focus': ['scope'],
                }],
            }
            waves_obj = {'waves': [{'wave': 1, 'slice_ids': ['SLICE-001'], 'integration_order': ['SLICE-001'], 'parallel_safety_rationale': 'single slice'}]}
            slice_plan.write_text(json.dumps({**plan, **waves_obj}))
            waves.write_text(json.dumps(waves_obj))
            result = subprocess.run(
                [
                    PY,
                    str(ROOT/'scripts/orchestrate_slice_waves.py'),
                    str(slice_plan),
                    str(waves),
                    '--dry-run',
                    '--allow-merge',
                    '--pr-only',
                ],
                text=True,
                stdout=subprocess.PIPE,
            )
        self.assertEqual(result.returncode, 0)
        self.assertIn('merge=disabled', result.stdout)
if __name__=='__main__': unittest.main()
