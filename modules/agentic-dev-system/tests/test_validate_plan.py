import json
import subprocess
import sys
import unittest
import tempfile
from pathlib import Path

from support_paths import fixture_path, script_path


SCRIPT = script_path('validate_plan.py')
VALID = fixture_path('sample_plan.valid.json')
INVALID = fixture_path('sample_plan.invalid.json')


class ValidatePlanTests(unittest.TestCase):
    def run_script(self, path):
        return subprocess.run([sys.executable, str(SCRIPT), str(path), '--json'], text=True, capture_output=True)

    def write_plan(self, plan):
        tmp = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False)
        with tmp:
            json.dump(plan, tmp)
        return Path(tmp.name)

    def minimal_task(self, task_id, wave, **overrides):
        task = {
            'id': task_id,
            'epic_id': 'E1',
            'wave': wave,
            'title': task_id,
            'branch': f'branch-{task_id.lower()}',
            'objective': 'Do one reviewable thing.',
            'non_goals': [],
            'context_to_load': [],
            'read_set': [],
            'write_set': [f'src/{task_id.lower()}.py'],
            'dependencies': [],
            'parallel_conflicts': [],
            'implementation_steps': ['Write test', 'Implement'],
            'tests_to_write_first': ['pytest'],
            'verification_commands': ['pytest'],
            'acceptance_criteria': ['Works'],
            'review_focus': ['Correctness'],
            'rollback_notes': 'Revert branch.',
        }
        task.update(overrides)
        return task

    def minimal_plan(self, tasks, waves):
        return {
            'feature': 'validation-test',
            'source_documents': [],
            'assumptions': [],
            'open_questions': [],
            'epics': [{'id': 'E1', 'title': 'Epic', 'description': 'Epic scope'}],
            'tasks': tasks,
            'waves': waves,
        }

    def test_valid_plan_ok(self):
        result = self.run_script(VALID)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload.get('valid'))

    def test_invalid_plan_fails(self):
        result = self.run_script(INVALID)
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertFalse(payload.get('valid'))
        self.assertGreater(len(payload.get('errors', [])), 0)

    def test_dependency_must_be_in_earlier_wave(self):
        plan = self.minimal_plan(
            [
                self.minimal_task('T1', 1, dependencies=['T2']),
                self.minimal_task('T2', 2),
            ],
            [
                {'wave': 1, 'task_ids': ['T1'], 'post_wave_verification': ['pytest']},
                {'wave': 2, 'task_ids': ['T2'], 'post_wave_verification': ['pytest']},
            ],
        )
        result = self.run_script(self.write_plan(plan))
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertTrue(any('later wave' in e for e in payload['errors']))

    def test_wave_task_ids_must_exist(self):
        plan = self.minimal_plan(
            [self.minimal_task('T1', 1)],
            [{'wave': 1, 'task_ids': ['T1', 'T_MISSING'], 'post_wave_verification': ['pytest']}],
        )
        result = self.run_script(self.write_plan(plan))
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertTrue(any('unknown task' in e for e in payload['errors']))

    def test_risky_same_wave_write_is_invalid(self):
        plan = self.minimal_plan(
            [
                self.minimal_task('T1', 1, write_set=['db/schema.sql']),
                self.minimal_task('T2', 1, write_set=['src/feature.py']),
            ],
            [{'wave': 1, 'task_ids': ['T1', 'T2'], 'post_wave_verification': ['pytest']}],
        )
        result = self.run_script(self.write_plan(plan))
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertTrue(any('risky write set' in e for e in payload['errors']))

    def test_task_must_appear_in_exactly_one_wave(self):
        plan = self.minimal_plan(
            [self.minimal_task('T1', 1)],
            [{'wave': 1, 'task_ids': [], 'post_wave_verification': ['pytest']}],
        )
        result = self.run_script(self.write_plan(plan))
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertTrue(any('appears in 0 wave buckets' in e for e in payload['errors']))

    def test_task_cannot_appear_in_multiple_waves(self):
        plan = self.minimal_plan(
            [self.minimal_task('T1', 1)],
            [
                {'wave': 1, 'task_ids': ['T1'], 'post_wave_verification': ['pytest']},
                {'wave': 2, 'task_ids': ['T1'], 'post_wave_verification': ['pytest']},
            ],
        )
        result = self.run_script(self.write_plan(plan))
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertTrue(any('appears in 2 wave buckets' in e for e in payload['errors']))

    def test_wave_requires_post_wave_verification(self):
        plan = self.minimal_plan(
            [self.minimal_task('T1', 1)],
            [{'wave': 1, 'task_ids': ['T1']}],
        )
        result = self.run_script(self.write_plan(plan))
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertTrue(any('post_wave_verification must be a non-empty list' in e for e in payload['errors']))

    def test_required_list_fields_must_be_lists(self):
        plan = self.minimal_plan(
            [self.minimal_task('T1', 1, read_set='src/app.py')],
            [{'wave': 1, 'task_ids': ['T1'], 'post_wave_verification': ['pytest']}],
        )
        result = self.run_script(self.write_plan(plan))
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertTrue(any('task T1 read_set must be a list' in e for e in payload['errors']))

    def test_duplicate_write_paths_are_invalid(self):
        plan = self.minimal_plan(
            [self.minimal_task('T1', 1, write_set=['src/app.py', 'src/app.py'])],
            [{'wave': 1, 'task_ids': ['T1'], 'post_wave_verification': ['pytest']}],
        )
        result = self.run_script(self.write_plan(plan))
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertTrue(any('duplicate write_set paths' in e for e in payload['errors']))

    def test_simple_glob_path_overlap_in_same_wave_is_invalid(self):
        plan = self.minimal_plan(
            [
                self.minimal_task('T1', 1, write_set=['src/foo/*']),
                self.minimal_task('T2', 1, write_set=['src/foo/bar.py']),
            ],
            [{'wave': 1, 'task_ids': ['T1', 'T2'], 'post_wave_verification': ['pytest']}],
        )
        result = self.run_script(self.write_plan(plan))
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertTrue(any('path overlap' in e for e in payload['errors']))

    def test_merge_safe_requires_reason(self):
        plan = self.minimal_plan(
            [self.minimal_task('T1', 1, merge_safe=True)],
            [{'wave': 1, 'task_ids': ['T1'], 'post_wave_verification': ['pytest']}],
        )
        result = self.run_script(self.write_plan(plan))
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertTrue(any('merge_safe_reason' in e for e in payload['errors']))

    def test_branch_name_allows_slashes_but_rejects_invalid_refs(self):
        plan = self.minimal_plan(
            [self.minimal_task('T1', 1, branch='bad..branch')],
            [{'wave': 1, 'task_ids': ['T1'], 'post_wave_verification': ['pytest']}],
        )
        result = self.run_script(self.write_plan(plan))
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertTrue(any('invalid branch' in e for e in payload['errors']))

    def test_one_way_parallel_conflict_blocks_same_wave(self):
        plan = self.minimal_plan(
            [
                self.minimal_task('T1', 1, parallel_conflicts=['T2']),
                self.minimal_task('T2', 1),
            ],
            [{'wave': 1, 'task_ids': ['T1', 'T2'], 'post_wave_verification': ['pytest']}],
        )
        result = self.run_script(self.write_plan(plan))
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertTrue(any('parallel_conflicts' in e and 'same wave' in e for e in payload['errors']))

    def test_two_way_parallel_conflict_blocks_same_wave(self):
        plan = self.minimal_plan(
            [
                self.minimal_task('T1', 1, parallel_conflicts=['T2']),
                self.minimal_task('T2', 1, parallel_conflicts=['T1']),
            ],
            [{'wave': 1, 'task_ids': ['T1', 'T2'], 'post_wave_verification': ['pytest']}],
        )
        result = self.run_script(self.write_plan(plan))
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertGreaterEqual(sum('parallel_conflicts' in e for e in payload['errors']), 1)

    def test_parallel_conflict_missing_task_id_is_invalid(self):
        plan = self.minimal_plan(
            [self.minimal_task('T1', 1, parallel_conflicts=['T_MISSING'])],
            [{'wave': 1, 'task_ids': ['T1'], 'post_wave_verification': ['pytest']}],
        )
        result = self.run_script(self.write_plan(plan))
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertTrue(any('missing parallel_conflicts task T_MISSING' in e for e in payload['errors']))

    def test_parallel_conflict_across_waves_is_allowed(self):
        plan = self.minimal_plan(
            [
                self.minimal_task('T1', 1, parallel_conflicts=['T2']),
                self.minimal_task('T2', 2),
            ],
            [
                {'wave': 1, 'task_ids': ['T1'], 'post_wave_verification': ['pytest']},
                {'wave': 2, 'task_ids': ['T2'], 'post_wave_verification': ['pytest']},
            ],
        )
        result = self.run_script(self.write_plan(plan))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
