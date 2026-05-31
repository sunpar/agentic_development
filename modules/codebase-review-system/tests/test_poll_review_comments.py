import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'poll_review_comments.py'
PY = sys.executable


def run(cmd, env=None):
    return subprocess.run(
        cmd,
        env=env,
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

    def test_live_fetch_includes_inline_review_comments(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            output_json = td_path / 'review-report.json'
            output_md = td_path / 'review-report.md'
            gh_log = td_path / 'gh.log'
            fake_gh = td_path / 'gh'
            fake_gh.write_text(
                """#!/bin/sh
printf '%s\\n' "$*" >> "$GH_LOG"
if [ "$1" = "pr" ] && [ "$2" = "view" ]; then
  printf '%s' '{"url":"https://github.com/sunpar/agentic_development/pull/2","number":2,"title":"Example","comments":[],"latestReviews":[]}'
elif [ "$1" = "api" ] && [ "$2" = "repos/sunpar/agentic_development/pulls/2/comments" ]; then
  printf '%s' '[{"id":99,"user":{"login":"chatgpt-codex-reviewer"},"body":"[P1] Inline blocker.","path":"src/a.py","line":12,"created_at":"2026-05-29T14:00:00Z","html_url":"https://example.test/comment/99"}]'
else
  echo "unexpected gh args: $*" >&2
  exit 2
fi
""",
                encoding='utf-8',
            )
            fake_gh.chmod(0o755)
            env = dict(os.environ)
            env['PATH'] = f'{td}{os.pathsep}{env["PATH"]}'
            env['GH_LOG'] = str(gh_log)

            result = run(
                [
                    PY,
                    str(SCRIPT),
                    '--repo',
                    'sunpar/agentic_development',
                    '--pr',
                    '2',
                    '--output-json',
                    str(output_json),
                    '--output-md',
                    str(output_md),
                ],
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            report = json.loads(output_json.read_text())
            log = gh_log.read_text()

        self.assertIn('--json comments,latestReviews,url,number,title', log)
        self.assertIn('api repos/sunpar/agentic_development/pulls/2/comments --paginate', log)
        self.assertEqual([item['id'] for item in report['actionable_comments']], ['comment-99'])
        self.assertEqual(report['actionable_comments'][0]['path'], 'src/a.py')

    def test_classifies_non_blocking_feedback_as_info(self):
        payload = {
            'url': 'https://example.test/pr/7',
            'comments': [
                {
                    'id': 1,
                    'author': {'login': 'reviewer'},
                    'body': 'Non-blocking: consider renaming this helper later.',
                }
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            input_json = td_path / 'pr.json'
            output_json = td_path / 'review-report.json'
            input_json.write_text(json.dumps(payload), encoding='utf-8')

            result = run([
                PY,
                str(SCRIPT),
                '--input-json',
                str(input_json),
                '--output-json',
                str(output_json),
                '--output-md',
                str(td_path / 'review-report.md'),
            ])

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            report = json.loads(output_json.read_text())

        self.assertEqual(report['comments'][0]['severity'], 'info')
        self.assertEqual(report['actionable_comments'], [])

    def test_classifies_negated_changes_requested_as_info(self):
        payload = {
            'url': 'https://example.test/pr/7',
            'comments': [
                {
                    'id': 1,
                    'author': {'login': 'reviewer'},
                    'body': 'No changes requested.',
                }
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            input_json = td_path / 'pr.json'
            output_json = td_path / 'review-report.json'
            input_json.write_text(json.dumps(payload), encoding='utf-8')

            result = run([
                PY,
                str(SCRIPT),
                '--input-json',
                str(input_json),
                '--output-json',
                str(output_json),
                '--output-md',
                str(td_path / 'review-report.md'),
            ])

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            report = json.loads(output_json.read_text())

        self.assertEqual(report['comments'][0]['severity'], 'info')
        self.assertEqual(report['actionable_comments'], [])

    def test_classifies_p2_findings_as_should_fix(self):
        payload = {
            'url': 'https://example.test/pr/7',
            'comments': [
                {
                    'id': 1,
                    'author': {'login': 'chatgpt-codex-connector'},
                    'body': '[P2] Fix the stale cache invalidation path.',
                }
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            input_json = td_path / 'pr.json'
            output_json = td_path / 'review-report.json'
            input_json.write_text(json.dumps(payload), encoding='utf-8')

            result = run([
                PY,
                str(SCRIPT),
                '--input-json',
                str(input_json),
                '--output-json',
                str(output_json),
                '--output-md',
                str(td_path / 'review-report.md'),
            ])

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            report = json.loads(output_json.read_text())

        self.assertEqual(report['actionable_comments'][0]['id'], 'comment-1')
        self.assertEqual(report['actionable_comments'][0]['severity'], 'should_fix')

    def test_uses_latest_reviews_for_review_level_decisions(self):
        payload = {
            'url': 'https://example.test/pr/7',
            'reviews': [
                {
                    'id': 1,
                    'author': {'login': 'reviewer'},
                    'body': 'Changes requested: old review that was superseded.',
                    'state': 'CHANGES_REQUESTED',
                }
            ],
            'latestReviews': [
                {
                    'id': 2,
                    'author': {'login': 'reviewer'},
                    'body': 'Looks good now.',
                    'state': 'APPROVED',
                }
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            input_json = td_path / 'pr.json'
            output_json = td_path / 'review-report.json'
            input_json.write_text(json.dumps(payload), encoding='utf-8')

            result = run([
                PY,
                str(SCRIPT),
                '--input-json',
                str(input_json),
                '--output-json',
                str(output_json),
                '--output-md',
                str(td_path / 'review-report.md'),
            ])

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            report = json.loads(output_json.read_text())

        self.assertEqual([item['id'] for item in report['comments']], ['review-2'])
        self.assertEqual(report['actionable_comments'], [])


if __name__ == '__main__':
    unittest.main()
