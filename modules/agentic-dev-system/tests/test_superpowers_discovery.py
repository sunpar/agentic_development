import unittest
import os

from support_paths import AGENTS_HOME

class SuperpowersDiscoveryTests(unittest.TestCase):
    def test_superpowers_discovery_link_has_skills(self):
        link = AGENTS_HOME / 'skills' / 'superpowers'
        if os.environ.get('AGENTS_HOME') and not link.exists() and not link.is_symlink():
            self.skipTest('Superpowers symlink is install-time state; see docs/SYMLINK_MANIFEST.md')
        if not os.environ.get('AGENTS_HOME'):
            self.assertTrue(link.is_symlink(), f'{link} must be a symlink in installed mode')
        else:
            self.assertTrue(link.exists(), f'{link} must exist in extracted-review mode')
        skills = sorted(link.glob('*/SKILL.md'))
        self.assertGreater(len(skills), 0, f'{link} should expose Superpowers SKILL.md files')


if __name__ == '__main__':
    unittest.main()
