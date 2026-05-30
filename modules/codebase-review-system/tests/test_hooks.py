import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOK_FIXTURES = ROOT / 'fixtures' / 'hooks'
PY = sys.executable


def run(cmd, cwd=None, env=None, input_text=None):
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def git(cwd, *args):
    result = run(['git', *args], cwd=cwd)
    if result.returncode:
        raise AssertionError(result.stderr or result.stdout)
    return result


def make_repo(td):
    repo = Path(td) / 'repo'
    repo.mkdir()
    git(repo, 'init', '-b', 'main')
    git(repo, 'config', 'user.email', 'test@example.com')
    git(repo, 'config', 'user.name', 'Test User')
    (repo / 'src').mkdir()
    (repo / 'docs').mkdir()
    (repo / 'src' / 'a.py').write_text('print("a")\n')
    (repo / 'src' / 'b.py').write_text('print("b")\n')
    git(repo, 'add', '.')
    git(repo, 'commit', '-m', 'initial')
    return repo


def slop_fixture_text():
    return 'As ' + 'requested, this is ' + 'ro' + 'bust.\n'


class HookTests(unittest.TestCase):
    def test_slice_scope_guard_reads_slice_state_when_allowed_scope_env_missing(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            state = Path(td) / 'slice-state.json'
            state.write_text(json.dumps({
                'slices': [{
                    'id': 'SLICE-001',
                    'files_allowed_to_edit': ['src/a.py'],
                }]
            }))
            (repo / 'src' / 'b.py').write_text('print("outside")\n')
            env = {
                **os.environ,
                'CODEBASE_REVIEW_FACTORY_STRICT': '1',
                'CODEBASE_REVIEW_FACTORY_SLICE_ID': 'SLICE-001',
                'CODEBASE_REVIEW_FACTORY_SLICE_STATE': str(state),
            }

            result = run([PY, str(ROOT / 'hooks/slice_scope_guard.py')], cwd=repo, env=env)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn('src/b.py', result.stdout)

    def test_slop_guard_ignores_preexisting_slop_when_added_diff_is_clean(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            doc = repo / 'docs' / 'note.md'
            doc.write_text(slop_fixture_text())
            git(repo, 'add', 'docs/note.md')
            git(repo, 'commit', '-m', 'add old note')
            doc.write_text(slop_fixture_text() + 'Clean added line.\n')
            env = {**os.environ, 'CODEBASE_REVIEW_FACTORY_STRICT': '1'}

            result = run([PY, str(ROOT / 'hooks/slop_guard.py')], cwd=repo, env=env)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_slop_guard_blocks_new_slop_in_added_diff(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            doc = repo / 'docs' / 'note.md'
            doc.write_text('Clean base.\n')
            git(repo, 'add', 'docs/note.md')
            git(repo, 'commit', '-m', 'add clean note')
            doc.write_text('Clean base.\n' + slop_fixture_text())
            env = {**os.environ, 'CODEBASE_REVIEW_FACTORY_STRICT': '1'}

            result = run([PY, str(ROOT / 'hooks/slop_guard.py')], cwd=repo, env=env)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn('apology/as-requested', result.stdout)

    def test_stop_summary_guard_reads_codex_transcript_payload(self):
        with tempfile.TemporaryDirectory() as td:
            transcript = Path(td) / 'transcript.jsonl'
            transcript.write_text(json.dumps({
                'type': 'response_item',
                'item': {
                    'type': 'message',
                    'role': 'assistant',
                    'content': [{
                        'type': 'output_text',
                        'text': 'Updated hook behavior. Tests passed.',
                    }],
                },
            }) + '\n')
            payload = json.dumps({'transcript_path': str(transcript)})
            env = {**os.environ, 'CODEBASE_REVIEW_FACTORY_STRICT': '1'}

            result = run([PY, str(ROOT / 'hooks/stop_summary_guard.py')], env=env, input_text=payload)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_hook_fixture_payloads_match_supported_inputs(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            state = HOOK_FIXTURES / 'slice-state.json'
            slop_text = ''.join(json.loads((HOOK_FIXTURES / 'slop-added-line.json').read_text())['parts'])
            transcript = HOOK_FIXTURES / 'stop-transcript.jsonl'
            payload = json.loads((HOOK_FIXTURES / 'stop-summary-payload.json').read_text())
            payload['transcript_path'] = str(transcript)

            (repo / 'src' / 'a.py').write_text('print("fixture allowed")\n')
            env = {
                **os.environ,
                'CODEBASE_REVIEW_FACTORY_STRICT': '1',
                'CODEBASE_REVIEW_FACTORY_SLICE_ID': 'SLICE-001',
                'CODEBASE_REVIEW_FACTORY_SLICE_STATE_PATH': str(state),
            }
            scope = run([PY, str(ROOT / 'hooks/slice_scope_guard.py')], cwd=repo, env=env)
            self.assertEqual(scope.returncode, 0, scope.stderr + scope.stdout)

            doc = repo / 'docs' / 'fixture.md'
            doc.write_text('Clean base.\n')
            git(repo, 'add', 'docs/fixture.md')
            git(repo, 'commit', '-m', 'add fixture doc')
            doc.write_text('Clean base.\n' + slop_text)
            slop = run(
                [PY, str(ROOT / 'hooks/slop_guard.py')],
                cwd=repo,
                env={**os.environ, 'CODEBASE_REVIEW_FACTORY_STRICT': '1'},
            )
            self.assertNotEqual(slop.returncode, 0)
            self.assertIn('apology/as-requested', slop.stdout)

            stop = run(
                [PY, str(ROOT / 'hooks/stop_summary_guard.py')],
                env={**os.environ, 'CODEBASE_REVIEW_FACTORY_STRICT': '1'},
                input_text=json.dumps(payload),
            )
            self.assertEqual(stop.returncode, 0, stop.stderr + stop.stdout)


if __name__ == '__main__':
    unittest.main()
