import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TestSkillReferenceDepth(unittest.TestCase):
    def test_operational_references_include_commands_outputs_and_examples(self):
        references = [
            ROOT / 'skills/codebase-maintenance-orchestrator/references/orchestration-contract.md',
            ROOT / 'skills/codebase-maintenance-orchestrator/references/wave-execution-contract.md',
            ROOT / 'skills/codebase-maintenance-orchestrator/references/failure-handling.md',
            ROOT / 'skills/slice-agent-review-loop/references/review-comment-resolution.md',
            ROOT / 'skills/reviewable-slice-validator/references/validation-rubric.md',
        ]
        for path in references:
            text = path.read_text()
            with self.subTest(path=path.name):
                self.assertIn('## Commands', text)
                self.assertIn('## Output Contract', text)
                self.assertIn('## Good Example', text)
                self.assertIn('## Bad Example', text)


if __name__ == '__main__':
    unittest.main()
