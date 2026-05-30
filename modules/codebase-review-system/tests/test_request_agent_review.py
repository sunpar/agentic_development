import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'request_agent_review.py'
PY = sys.executable


def load_module():
    spec = importlib.util.spec_from_file_location('request_agent_review', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RequestAgentReviewTests(unittest.TestCase):
    def test_both_providers_use_review_trigger_text(self):
        module = load_module()

        body = module.build_review_body({'codex', 'copilot'}, 'tests, scope')

        self.assertIn('@codex review for tests, scope', body)
        self.assertIn('@copilot please review this PR for tests, scope', body)
        self.assertIn('Focus:\n- tests\n- scope', body)

    def test_post_request_includes_pr_number_and_repo(self):
        module = load_module()
        calls = []

        def fake_run(cmd):
            calls.append(cmd)

            class Result:
                returncode = 0

            return Result()

        module.run = fake_run
        result = module.post_request(7, {'codex'}, 'correctness', repo='owner/repo')

        self.assertEqual(result.returncode, 0)
        self.assertEqual(calls[0][0:4], ['gh', 'pr', 'comment', '7'])
        self.assertIn('--repo', calls[0])
        self.assertEqual(calls[0][calls[0].index('--repo') + 1], 'owner/repo')
        body = calls[0][calls[0].index('--body') + 1]
        self.assertIn('@codex review for correctness', body)

    def test_dry_run_with_pr_number_does_not_require_gh(self):
        with tempfile.TemporaryDirectory() as td:
            result = subprocess.run(
                [
                    PY,
                    str(SCRIPT),
                    '--dry-run',
                    '--provider',
                    'codex',
                    '--focus',
                    'correctness',
                    '--pr-number',
                    '7',
                    '--repo',
                    'owner/repo',
                ],
                env={'PATH': td},
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('DRY-RUN', result.stdout)
        self.assertIn('gh pr comment 7', result.stdout)
        self.assertIn('@codex review for correctness', result.stdout)


if __name__ == '__main__':
    unittest.main()
