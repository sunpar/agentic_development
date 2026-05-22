import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest

from support_paths import script_path


SCRIPT = script_path('request_review_and_poll.py')


def load_module():
    spec = importlib.util.spec_from_file_location('request_review_and_poll', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RequestReviewPollTests(unittest.TestCase):
    def test_codex_review_body_uses_exact_review_trigger(self):
        module = load_module()
        calls = []

        def fake_run(cmd, capture=True):
            calls.append(cmd)

            class Result:
                returncode = 0
                stdout = ''
                stderr = ''

            return Result()

        module.run = fake_run
        result = module.post_request(7, {'codex'}, 'security regressions')

        self.assertEqual(result.returncode, 0)
        body = calls[0][calls[0].index('--body') + 1]
        self.assertIn('@codex review for security regressions', body)
        self.assertNotIn('Tags:', body)

    def test_both_providers_use_provider_specific_review_lines(self):
        module = load_module()
        calls = []

        def fake_run(cmd, capture=True):
            calls.append(cmd)

            class Result:
                returncode = 0
                stdout = ''
                stderr = ''

            return Result()

        module.run = fake_run
        module.post_request(7, {'codex', 'copilot'}, 'tests, api compatibility')

        body = calls[0][calls[0].index('--body') + 1]
        self.assertIn('@codex review for tests, api compatibility', body)
        self.assertIn('@copilot please review this PR for tests, api compatibility', body)
        self.assertNotIn('Tags:', body)

    def test_poll_pr_includes_issue_comments(self):
        module = load_module()

        def fake_run_json(cmd):
            target = cmd[-1]
            if target == 'repos/owner/repo/issues/7/comments':
                return [{'body': 'please fix docs', 'author': {'login': 'human'}, 'url': 'issue-url'}]
            if target == 'repos/owner/repo/pulls/7/comments':
                return []
            if target == 'repos/owner/repo/pulls/7/reviews':
                return []
            return None

        module.run_json = fake_run_json

        findings = module.poll_pr(7, 'owner/repo')
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['source'], 'issue-comment')
        self.assertEqual(findings[0]['url'], 'issue-url')

    def test_dry_run_with_pr_number_and_repo_does_not_require_gh_auth(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env['PATH'] = tmp
            result = subprocess.run(
                [
                    sys.executable,
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
                env=env,
                text=True,
                capture_output=True,
            )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('@codex review for correctness', result.stdout)
        self.assertNotIn('gh unavailable', result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
