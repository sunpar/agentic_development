import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from support_paths import script_path


SCRIPT = script_path('address_review_comments_prompt.py')


class AddressReviewCommentsPromptTests(unittest.TestCase):
    def write_findings(self, tmp_path: Path) -> Path:
        payload = {
            'pr': 7,
            'pr_url': 'https://github.com/owner/repo/pull/7',
            'actionable': [
                {
                    'source': 'comment',
                    'author': 'codex',
                    'url': 'https://github.com/owner/repo/pull/7#discussion_r1',
                    'body': 'Must fix missing regression test before merge.',
                },
                {
                    'source': 'issue-comment',
                    'author': 'human',
                    'url': 'https://github.com/owner/repo/pull/7#issuecomment-1',
                    'body': 'Please clarify the API compatibility note.',
                },
            ],
        }
        path = tmp_path / 'findings.json'
        path.write_text(json.dumps(payload), encoding='utf-8')
        return path

    def test_generates_precise_fix_prompt_and_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            findings = self.write_findings(tmp_path)
            prompt = tmp_path / 'prompt.md'
            summary = tmp_path / 'summary.json'

            result = subprocess.run([
                sys.executable,
                str(SCRIPT),
                '--input', str(findings),
                '--output', str(prompt),
                '--json-output', str(summary),
            ], text=True, capture_output=True)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            text = prompt.read_text(encoding='utf-8')
            self.assertIn('Fix only in-scope must-fix and should-fix review comments.', text)
            self.assertIn('Do not broaden scope.', text)
            self.assertIn('Run verification.', text)
            self.assertIn('Commit and push follow-up changes.', text)
            self.assertIn('Reply with evidence.', text)
            summary_payload = json.loads(summary.read_text(encoding='utf-8'))
            self.assertEqual(summary_payload['counts']['must_fix'], 1)
            self.assertEqual(summary_payload['counts']['clarify'], 1)

    def test_dry_run_does_not_write_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            findings = self.write_findings(tmp_path)
            prompt = tmp_path / 'prompt.md'
            summary = tmp_path / 'summary.json'

            result = subprocess.run([
                sys.executable,
                str(SCRIPT),
                '--input', str(findings),
                '--output', str(prompt),
                '--json-output', str(summary),
                '--dry-run',
            ], text=True, capture_output=True)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(prompt.exists())
            self.assertFalse(summary.exists())
            self.assertIn('DRY-RUN', result.stdout)
            self.assertIn('Fix only in-scope must-fix', result.stdout)


if __name__ == '__main__':
    unittest.main()
