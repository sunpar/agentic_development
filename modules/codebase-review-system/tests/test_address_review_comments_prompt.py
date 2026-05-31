import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'address_review_comments_prompt.py'
PY = sys.executable


class AddressReviewCommentsPromptTests(unittest.TestCase):
    def test_renders_structured_prompt_from_actionable_comments(self):
        payload = {
            'pr': 42,
            'pr_url': 'https://github.com/example/repo/pull/42',
            'actionable': [
                {
                    'source': 'review',
                    'author': 'codex',
                    'url': 'https://example.test/comment',
                    'body': 'Must fix missing regression test before merge.',
                },
                {
                    'source': 'issue-comment',
                    'author': 'human',
                    'body': 'Please clarify whether this is in scope.',
                },
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'comments.json'
            path.write_text(json.dumps(payload), encoding='utf-8')

            result = subprocess.run(
                [PY, str(SCRIPT), str(path), '--slice-id', 'SLICE-001'],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn('# Address PR Review Comments', result.stdout)
        self.assertIn('Slice: SLICE-001', result.stdout)
        self.assertIn('## Must Fix', result.stdout)
        self.assertIn('Must fix missing regression test before merge.', result.stdout)
        self.assertIn('## Needs Clarification', result.stdout)
        self.assertNotIn('Comments JSON:', result.stdout)

    def test_uses_normalized_actionable_comments_with_severity_and_location(self):
        payload = {
            'pr': 42,
            'pr_url': 'https://github.com/example/repo/pull/42',
            'actionable_comments': [
                {
                    'source': 'review-thread',
                    'author': 'codex',
                    'severity': 'must_fix',
                    'path': 'src/app.py',
                    'line': 12,
                    'url': 'https://example.test/comment',
                    'body': '[P1] Reject invalid inputs.',
                },
                {
                    'source': 'review-thread',
                    'author': 'codex',
                    'severity': 'should_fix',
                    'path': 'src/app.py',
                    'line': 20,
                    'body': 'No must-fix findings.',
                },
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'comments.json'
            path.write_text(json.dumps(payload), encoding='utf-8')

            result = subprocess.run(
                [PY, str(SCRIPT), str(path), '--slice-id', 'SLICE-001'],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn('codex [review-thread] at src/app.py:12', result.stdout)
        self.assertIn('[P1] Reject invalid inputs.', result.stdout)
        self.assertIn('## Notes', result.stdout)
        self.assertIn('No must-fix findings.', result.stdout)

    def test_dry_run_does_not_write_output_file(self):
        payload = {'actionable': [{'author': 'codex', 'body': 'should fix docs'}]}
        with tempfile.TemporaryDirectory() as td:
            input_path = Path(td) / 'comments.json'
            output_path = Path(td) / 'prompt.md'
            input_path.write_text(json.dumps(payload), encoding='utf-8')

            result = subprocess.run(
                [
                    PY,
                    str(SCRIPT),
                    str(input_path),
                    '--output',
                    str(output_path),
                    '--dry-run',
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn('DRY-RUN: would write prompt to', result.stdout)
        self.assertFalse(output_path.exists())


if __name__ == '__main__':
    unittest.main()
