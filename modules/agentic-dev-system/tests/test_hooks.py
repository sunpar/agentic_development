import json
import os
import subprocess
import sys
import tempfile
import unittest

from support_paths import CODEX_HOME


HOOKS_JSON = CODEX_HOME / 'hooks.json'
HOOKS = [
    CODEX_HOME / 'hooks' / 'tool_policy.py',
    CODEX_HOME / 'hooks' / 'branch_hygiene.py',
    CODEX_HOME / 'hooks' / 'secret_scan.py',
    CODEX_HOME / 'hooks' / 'stop_quality_gate.py',
]


class HookHelpTests(unittest.TestCase):
    def test_hooks_support_help_without_running_checks(self):
        for hook in HOOKS:
            with self.subTest(hook=hook.name), tempfile.TemporaryDirectory() as tmp:
                result = subprocess.run([sys.executable, str(hook), '--help'], cwd=tmp, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('usage:', result.stdout)
                self.assertEqual(result.stderr, '')

    def test_hooks_json_uses_current_nested_schema(self):
        data = json.loads(HOOKS_JSON.read_text(encoding='utf-8'))
        self.assertIn('hooks', data)
        self.assertNotIn('events', data)
        self.assertNotIn('PreStop', data['hooks'])

        pre_tool = data['hooks'].get('PreToolUse', [])
        self.assertTrue(any(group.get('matcher') == 'Bash' for group in pre_tool))
        pre_tool_commands = [
            hook.get('command', '')
            for group in pre_tool
            for hook in group.get('hooks', [])
        ]
        self.assertTrue(any('tool_policy.py' in command for command in pre_tool_commands))

        stop_commands = [
            hook.get('command', '')
            for group in data['hooks'].get('Stop', [])
            for hook in group.get('hooks', [])
        ]
        for expected in ['branch_hygiene.py', 'secret_scan.py', 'stop_quality_gate.py']:
            self.assertTrue(any(expected in command for command in stop_commands), expected)

    def test_tool_policy_reads_codex_hook_json(self):
        payload = {
            'event': 'PreToolUse',
            'tool_name': 'Bash',
            'tool_input': {'command': 'git reset --hard HEAD'},
        }
        result = subprocess.run(
            [sys.executable, str(CODEX_HOME / 'hooks' / 'tool_policy.py')],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('tool_policy warning', result.stdout)

    def test_tool_policy_blocks_codex_hook_json_in_strict_mode(self):
        payload = {
            'event': 'PreToolUse',
            'tool_name': 'Bash',
            'tool_input': {'command': 'rm -rf build'},
        }
        env = os.environ.copy()
        env['AGENTIC_DEV_STRICT_HOOKS'] = '1'
        result = subprocess.run(
            [sys.executable, str(CODEX_HOME / 'hooks' / 'tool_policy.py')],
            input=json.dumps(payload),
            env=env,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('tool_policy blocked', result.stdout)

    def test_stop_hooks_accept_codex_json_stdin(self):
        payload = json.dumps({'event': 'Stop', 'transcript_path': '/tmp/missing'})
        for hook in HOOKS[1:]:
            with self.subTest(hook=hook.name), tempfile.TemporaryDirectory() as tmp:
                result = subprocess.run(
                    [sys.executable, str(hook)],
                    cwd=tmp,
                    input=payload,
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
