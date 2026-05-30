import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TestDocsStaleness(unittest.TestCase):
    def test_install_report_does_not_claim_completed_v02_work_is_future(self):
        text = (ROOT / 'INSTALL_REPORT.md').read_text()
        stale_phrases = [
            'Full feature-task generation and real parallel wave execution remain v0.2 work',
            'dry-run planning helpers',
        ]
        for phrase in stale_phrases:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, text)


if __name__ == '__main__':
    unittest.main()
