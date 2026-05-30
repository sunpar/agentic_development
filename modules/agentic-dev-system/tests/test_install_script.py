import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "install.py"
PY = sys.executable


class InstallScriptTests(unittest.TestCase):
    def test_dry_run_prefixes_mutating_actions(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            codex_home = base / ".codex"
            agents_home = base / ".agents"
            (codex_home / "agentic-dev-system").mkdir(parents=True)

            result = subprocess.run(
                [
                    PY,
                    str(SCRIPT),
                    "--codex-home",
                    str(codex_home),
                    "--agents-home",
                    str(agents_home),
                    "--dry-run",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            lines = result.stdout.splitlines()

        self.assertTrue(any(line.startswith("[dry-run] backup ") for line in lines))
        self.assertTrue(any(line.startswith("[dry-run] copy ") for line in lines))
        self.assertTrue(any(line.startswith("[dry-run] symlink ") for line in lines))
        for line in lines:
            self.assertFalse(line.startswith(("backup ", "copy ", "copy skills ", "symlink ")), line)


if __name__ == "__main__":
    unittest.main()
