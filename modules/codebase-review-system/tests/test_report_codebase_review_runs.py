import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'report_codebase_review_runs.py'
PY = sys.executable


def run(cmd):
    return subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


class TestReportCodebaseReviewRuns(unittest.TestCase):
    def test_aggregates_summary_and_state_backed_runs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'runs'
            first = root / 'repo-20260529T120000Z'
            second = root / 'repo-20260529T130000Z'
            ignored = root / 'not-a-run'
            first.mkdir(parents=True)
            second.mkdir()
            ignored.mkdir()
            (first / 'run-summary.json').write_text(json.dumps({
                'repo': '/tmp/repo',
                'run_dir': str(first),
                'totals': {
                    'waves': 1,
                    'slices': 2,
                    'by_status': {'succeeded': 1, 'failed': 1},
                },
                'waves': [{'wave': '1', 'status': 'failed', 'slice_ids': ['SLICE-001', 'SLICE-002']}],
                'slices': [
                    {'id': 'SLICE-001', 'status': 'succeeded', 'pr_number': 10},
                    {'id': 'SLICE-002', 'status': 'failed', 'error': 'verification failed'},
                ],
            }))
            (first / 'run-state.json').write_text(json.dumps({
                'repo': '/tmp/repo',
                'run_dir': str(first),
                'slice_plan': '/tmp/repo/docs/agentic-system/review/slice-plan.json',
                'waves_path': '/tmp/repo/docs/agentic-system/review/waves.json',
                'execution_options': {
                    'allow_pr': True,
                    'allow_review_request': True,
                    'review_agents': 'codex,copilot',
                    'allow_merge': True,
                    'merge_method': 'squash',
                    'delete_branch': True,
                    'max_parallel': 999,
                    'setup_commands': ['make install'],
                },
                'waves': {'1': {'status': 'failed', 'slice_ids': ['SLICE-001', 'SLICE-002']}},
                'slices': {
                    'SLICE-001': {
                        'status': 'succeeded',
                        'branch': 'codebase-review/s1',
                        'worktree': '/tmp/worktrees/codebase-review-s1',
                        'pr_number': 10,
                    },
                    'SLICE-002': {
                        'status': 'failed',
                        'branch': 'codebase-review/s2',
                        'worktree': '/tmp/worktrees/codebase-review-s2',
                        'error': 'verification failed',
                    },
                },
            }))
            (second / 'run-state.json').write_text(json.dumps({
                'repo': '/tmp/repo',
                'run_dir': str(second),
                'waves': {'1': {'status': 'succeeded', 'slice_ids': ['SLICE-003']}},
                'slices': {'SLICE-003': {'status': 'pr_ready', 'pr_number': 11}},
            }))
            output_json = Path(td) / 'aggregate.json'
            output_md = Path(td) / 'aggregate.md'

            result = run([
                PY,
                str(SCRIPT),
                '--runs-root',
                str(root),
                '--output-json',
                str(output_json),
                '--output-md',
                str(output_md),
            ])

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn(str(output_json), result.stdout)
            aggregate = json.loads(output_json.read_text())
            markdown = output_md.read_text()

        self.assertEqual(aggregate['totals']['runs'], 2)
        self.assertEqual(aggregate['totals']['waves'], 2)
        self.assertEqual(aggregate['totals']['slices'], 3)
        self.assertEqual(aggregate['totals']['prs'], 2)
        self.assertEqual(aggregate['totals']['by_status']['succeeded'], 1)
        self.assertEqual(aggregate['totals']['by_status']['failed'], 1)
        self.assertEqual(aggregate['totals']['by_status']['pr_ready'], 1)
        self.assertEqual(aggregate['runs'][0]['failed_slices'], ['SLICE-002'])
        self.assertEqual(aggregate['runs'][1]['pr_numbers'], [11])
        self.assertEqual(len(aggregate['runs'][0]['resume_commands']), 1)
        resume = aggregate['runs'][0]['resume_commands'][0]
        self.assertIn(str(Path.home() / '.codex/codebase-review-factory/scripts/orchestrate_slice_waves.py'), resume)
        self.assertIn('/tmp/repo/docs/agentic-system/review/slice-plan.json', resume)
        self.assertIn('/tmp/repo/docs/agentic-system/review/waves.json', resume)
        self.assertIn(f'--run-dir {first}', resume)
        self.assertIn('--worktree-dir /tmp/worktrees', resume)
        self.assertIn('--max-parallel 999', resume)
        self.assertIn("--setup-command 'make install'", resume)
        self.assertIn('--allow-pr --allow-review-request', resume)
        self.assertIn('--review-agents codex,copilot', resume)
        self.assertIn('--allow-merge --merge-method squash --delete-branch', resume)
        self.assertIn('--resume --reuse-worktrees', resume)
        self.assertIn('## Runs', markdown)
        self.assertIn('repo-20260529T120000Z', markdown)
        self.assertIn('- PRs: 2', markdown)
        self.assertIn('failed: 1', markdown)
        self.assertIn('Resume:', markdown)


if __name__ == '__main__':
    unittest.main()
