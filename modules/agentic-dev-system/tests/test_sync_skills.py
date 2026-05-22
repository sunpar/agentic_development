import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from support_paths import script_path

SCRIPT = script_path('sync_skills.py')


class SyncSkillsTests(unittest.TestCase):
    def test_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            codex = tmp_path / '.codex'
            agents = tmp_path / '.agents'
            src = codex / 'agentic-dev-system' / 'skills' / 'sample-skill'
            (src).mkdir(parents=True)
            (src / 'SKILL.md').write_text('---\nname: sample\n---\n', encoding='utf-8')
            result = subprocess.run([
                sys.executable,
                str(SCRIPT),
                '--dry-run',
                '--codex-dir', str(codex),
                '--agents-skills-dir', str(agents / 'skills')
            ], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0)
            self.assertFalse((agents / 'skills' / 'agentic-dev-system').exists())

    def test_dry_run_does_not_create_agents_skills_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            codex = tmp_path / '.codex'
            agents_skills = tmp_path / '.agents' / 'skills'
            src = codex / 'agentic-dev-system' / 'skills' / 'sample-skill'
            src.mkdir(parents=True)
            (src / 'SKILL.md').write_text('---\nname: sample\n---\n', encoding='utf-8')
            result = subprocess.run([
                sys.executable,
                str(SCRIPT),
                '--dry-run',
                '--codex-dir', str(codex),
                '--agents-skills-dir', str(agents_skills)
            ], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0)
            self.assertFalse(agents_skills.exists())

    def test_existing_non_symlink_is_backed_up_and_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            codex = tmp_path / '.codex'
            agents_skills = tmp_path / '.agents' / 'skills'
            src = codex / 'agentic-dev-system' / 'skills' / 'sample-skill'
            src.mkdir(parents=True)
            (src / 'SKILL.md').write_text('---\nname: sample\n---\n', encoding='utf-8')
            conflict = agents_skills / 'agentic-dev-system'
            conflict.mkdir(parents=True)
            (conflict / 'KEEP.txt').write_text('preserve me', encoding='utf-8')

            result = subprocess.run([
                sys.executable,
                str(SCRIPT),
                '--codex-dir', str(codex),
                '--agents-skills-dir', str(agents_skills)
            ], text=True, capture_output=True)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(conflict.is_symlink())
            backups = list(agents_skills.glob('agentic-dev-system.backup.*'))
            self.assertEqual(len(backups), 1)
            self.assertTrue((backups[0] / 'KEEP.txt').exists())

    def test_existing_wrong_symlink_is_backed_up_and_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            codex = tmp_path / '.codex'
            agents_skills = tmp_path / '.agents' / 'skills'
            src = codex / 'agentic-dev-system' / 'skills'
            sample = src / 'sample-skill'
            sample.mkdir(parents=True)
            (sample / 'SKILL.md').write_text('---\nname: sample\n---\n', encoding='utf-8')
            old_target = tmp_path / 'old-skills'
            old_target.mkdir()
            agents_skills.mkdir(parents=True)
            conflict = agents_skills / 'agentic-dev-system'
            conflict.symlink_to(old_target)

            result = subprocess.run([
                sys.executable,
                str(SCRIPT),
                '--codex-dir', str(codex),
                '--agents-skills-dir', str(agents_skills)
            ], text=True, capture_output=True)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(conflict.is_symlink())
            self.assertEqual(os.path.realpath(conflict), os.path.realpath(src))
            backups = list(agents_skills.glob('agentic-dev-system.backup.*'))
            self.assertEqual(len(backups), 1)
            self.assertTrue(backups[0].is_symlink())
            self.assertEqual(os.path.realpath(backups[0]), os.path.realpath(old_target))

    def test_check_validates_existing_link_without_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            codex = tmp_path / '.codex'
            agents_skills = tmp_path / '.agents' / 'skills'
            src = codex / 'agentic-dev-system' / 'skills'
            sample = src / 'sample-skill'
            sample.mkdir(parents=True)
            (sample / 'SKILL.md').write_text('---\nname: sample\n---\n', encoding='utf-8')
            agents_skills.mkdir(parents=True)
            (agents_skills / 'agentic-dev-system').symlink_to(src)

            result = subprocess.run([
                sys.executable,
                str(SCRIPT),
                '--check',
                '--codex-dir', str(codex),
                '--agents-skills-dir', str(agents_skills)
            ], text=True, capture_output=True)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('DISCOVERED: 1 skills', result.stdout)

    def test_check_superpowers_validates_superpowers_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            agents_skills = tmp_path / '.agents' / 'skills'
            superpowers = tmp_path / 'superpowers' / 'skills' / 'using-superpowers'
            superpowers.mkdir(parents=True)
            (superpowers / 'SKILL.md').write_text('---\nname: using-superpowers\n---\n', encoding='utf-8')
            agents_skills.mkdir(parents=True)
            (agents_skills / 'superpowers').symlink_to(tmp_path / 'superpowers' / 'skills')

            result = subprocess.run([
                sys.executable,
                str(SCRIPT),
                '--check-superpowers',
                '--codex-dir', str(tmp_path / '.codex-missing'),
                '--agents-skills-dir', str(agents_skills)
            ], text=True, capture_output=True)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('DISCOVERED: 1 skills', result.stdout)


if __name__ == '__main__':
    unittest.main()
