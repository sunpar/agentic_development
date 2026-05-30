import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from support_paths import script_path


SCRIPT = script_path("report_implementation_wave_runs.py")
PY = sys.executable


def run(cmd):
    return subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


class ImplementationWaveRunReportTests(unittest.TestCase):
    def test_aggregates_summary_and_state_backed_runs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "runs"
            first = root / "repo-20260529T120000Z"
            second = root / "repo-20260529T130000Z"
            ignored = root / "not-a-run"
            first.mkdir(parents=True)
            second.mkdir()
            ignored.mkdir()
            (first / "run-summary.json").write_text(json.dumps({
                "repo": "/tmp/repo",
                "run_dir": str(first),
                "dry_run": True,
                "selected_waves": [1],
                "totals": {
                    "tasks": 2,
                    "by_status": {"planned": 1, "failed": 1},
                },
                "tasks": [
                    {
                        "id": "TASK-001",
                        "status": "planned",
                        "branch": "feature/task-001",
                        "worktree": "/tmp/worktrees/task-001",
                        "prompt_path": str(first / "tasks/TASK-001/prompt.md"),
                    },
                    {
                        "id": "TASK-002",
                        "status": "failed",
                        "branch": "feature/task-002",
                        "worktree": "/tmp/worktrees/task-002",
                    },
                ],
            }), encoding="utf-8")
            (second / "run-state.json").write_text(json.dumps({
                "repo": "/tmp/repo",
                "run_dir": str(second),
                "dry_run": False,
                "selected_waves": [2],
                "tasks": {
                    "TASK-003": {
                        "status": "worktree_ready",
                        "wave": 2,
                        "branch": "feature/task-003",
                        "worktree": "/tmp/worktrees/task-003",
                        "prompt_path": str(second / "tasks/TASK-003/prompt.md"),
                    },
                    "TASK-004": {
                        "status": "error",
                        "wave": 2,
                        "branch": "feature/task-004",
                        "worktree": "/tmp/worktrees/task-004",
                    },
                },
            }), encoding="utf-8")
            output_json = Path(td) / "aggregate.json"
            output_md = Path(td) / "aggregate.md"

            result = run([
                PY,
                str(SCRIPT),
                "--runs-root",
                str(root),
                "--output-json",
                str(output_json),
                "--output-md",
                str(output_md),
            ])

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn(str(output_json), result.stdout)
            aggregate = json.loads(output_json.read_text())
            markdown = output_md.read_text()

        self.assertEqual(aggregate["totals"]["runs"], 2)
        self.assertEqual(aggregate["totals"]["dry_runs"], 1)
        self.assertEqual(aggregate["totals"]["waves"], 2)
        self.assertEqual(aggregate["totals"]["tasks"], 4)
        self.assertEqual(aggregate["totals"]["by_status"]["planned"], 1)
        self.assertEqual(aggregate["totals"]["by_status"]["worktree_ready"], 1)
        self.assertEqual(aggregate["totals"]["by_status"]["failed"], 1)
        self.assertEqual(aggregate["totals"]["by_status"]["error"], 1)
        self.assertEqual(aggregate["runs"][0]["failed_tasks"], ["TASK-002"])
        self.assertEqual(aggregate["runs"][1]["failed_tasks"], ["TASK-004"])
        self.assertEqual(aggregate["runs"][1]["branches"], ["feature/task-003", "feature/task-004"])
        self.assertIn("# Implementation Wave Run Report", markdown)
        self.assertIn("repo-20260529T120000Z", markdown)
        self.assertIn("failed=TASK-002", markdown)


if __name__ == "__main__":
    unittest.main()
