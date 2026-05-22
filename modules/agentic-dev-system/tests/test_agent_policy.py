import unittest

from support_paths import CODEX_HOME


AGENTS = CODEX_HOME / 'agents'


def read_top_level_value(path, key):
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.startswith(f'{key} = '):
            return line.split('=', 1)[1].strip().strip('"')
    return None


class AgentPolicyTests(unittest.TestCase):
    def test_integration_manager_documents_merge_opt_in(self):
        text = (AGENTS / 'integration-manager.toml').read_text(encoding='utf-8')
        self.assertIn('opt-in', text)
        self.assertIn('--merge', text)
        self.assertIn('--no-merge', text)

    def test_first_factory_agent_model_matrix(self):
        expected = {
            'planner.toml': ('gpt-5.5', 'xhigh'),
            'implementor.toml': ('gpt-5.5', 'xhigh'),
            'reviewer.toml': ('gpt-5.5', 'xhigh'),
            'refactorer.toml': ('gpt-5.5', 'medium'),
            'integration-manager.toml': ('gpt-5.3-codex-spark', 'xhigh'),
            'deslop-reviewer.toml': ('gpt-5.3-codex-spark', 'xhigh'),
            'pr-automation.toml': ('gpt-5.5', 'medium'),
        }
        for filename, (model, effort) in expected.items():
            with self.subTest(agent=filename):
                path = AGENTS / filename
                self.assertEqual(read_top_level_value(path, 'model'), model)
                self.assertEqual(read_top_level_value(path, 'model_reasoning_effort'), effort)


if __name__ == '__main__':
    unittest.main()
