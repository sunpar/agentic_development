import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'poll_review_comments.py'
PY = sys.executable


def run(cmd):
    return subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


class TestPollReviewComments(unittest.TestCase):
    def test_classifies_actionable_comments_and_provider_counts_from_input_json(self):
        payload = {
            'url': 'https://example.test/pr/7',
            'comments': [
                {
                    'id': 1,
                    'author': {'login': 'chatgpt-codex-connector'},
                    'body': 'Codex Review: No P1 findings.',
                    'createdAt': '2026-05-29T13:00:00Z',
                },
                {
                    'id': 2,
                    'author': {'login': 'chatgpt-codex-connector'},
                    'body': 'P1: must fix missing regression test before merge.',
                    'createdAt': '2026-05-29T13:01:00Z',
                },
                {
                    'id': 3,
                    'author': {'login': 'copilot-pull-request-reviewer'},
                    'body': 'Should fix: document the fallback path.',
                    'createdAt': '2026-05-29T13:02:00Z',
                },
            ],
            'reviews': [
                {
                    'id': 4,
                    'author': {'login': 'reviewer'},
                    'body': 'Changes requested: schema contract is too loose.',
                    'state': 'CHANGES_REQUESTED',
                    'submittedAt': '2026-05-29T13:03:00Z',
                }
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            input_json = td_path / 'pr.json'
            output_json = td_path / 'review-report.json'
            output_md = td_path / 'review-report.md'
            input_json.write_text(json.dumps(payload), encoding='utf-8')

            result = run([
                PY,
                str(SCRIPT),
                '--input-json',
                str(input_json),
                '--output-json',
                str(output_json),
                '--output-md',
                str(output_md),
            ])

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            report = json.loads(output_json.read_text())
            markdown = output_md.read_text()

        self.assertEqual(report['status'], 'ok')
        self.assertEqual(report['provider_counts'], {'codex': 2, 'copilot': 1, 'human': 1})
        self.assertEqual([item['id'] for item in report['actionable_comments']], ['comment-2', 'comment-3', 'review-4'])
        self.assertEqual(report['actionable_counts_by_severity']['must_fix'], 2)
        self.assertEqual(report['actionable_counts_by_severity']['should_fix'], 1)
        self.assertIn('## Actionable Review Comments', markdown)
        self.assertIn('codex: 2', markdown)
        self.assertIn('must_fix', markdown)


if __name__ == '__main__':
    unittest.main()
