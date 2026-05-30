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
    def test_state_enrichment_treats_empty_task_detail_dict_as_missing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "runs"
            run_dir = root / "repo-20260529T140000Z"
            run_dir.mkdir(parents=True)
            (run_dir / "run-summary.json").write_text(json.dumps({
                "repo": "/tmp/repo",
                "run_dir": str(run_dir),
                "selected_waves": [1],
                "totals": {
                    "tasks": 1,
                    "by_status": {"merged": 1},
                },
                "tasks": [
                    {
                        "id": "TASK-001",
                        "status": "merged",
                        "review_requests": {},
                        "merge": {},
                    },
                ],
            }), encoding="utf-8")
            (run_dir / "run-state.json").write_text(json.dumps({
                "repo": "/tmp/repo",
                "run_dir": str(run_dir),
                "selected_waves": [1],
                "selected_task_ids": ["TASK-001"],
                "tasks": {
                    "TASK-001": {
                        "status": "merged",
                        "wave": 1,
                        "branch": "feature/task-001",
                        "worktree": "/tmp/worktrees/task-001",
                        "pr_number": 123,
                        "review_requests": [
                            {"agent": "codex", "returncode": 0},
                        ],
                        "merge": {
                            "returncode": 0,
                            "stdout_log": str(run_dir / "tasks/TASK-001/merge.stdout.log"),
                            "stderr_log": str(run_dir / "tasks/TASK-001/merge.stderr.log"),
                        },
                    },
                },
            }), encoding="utf-8")
            output_json = Path(td) / "aggregate.json"

            result = run([
                PY,
                str(SCRIPT),
                "--runs-root",
                str(root),
                "--output-json",
                str(output_json),
            ])

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            aggregate = json.loads(output_json.read_text())

        self.assertEqual(aggregate["runs"][0]["pr_numbers"], [123])
        self.assertEqual(aggregate["runs"][0]["review_request_count"], 1)
        self.assertEqual(aggregate["runs"][0]["merge_log_paths"], [
            str(run_dir / "tasks/TASK-001/merge.stderr.log"),
            str(run_dir / "tasks/TASK-001/merge.stdout.log"),
        ])

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
            (first / "run-state.json").write_text(json.dumps({
                "repo": "/tmp/repo",
                "run_dir": str(first),
                "implementation_plan": "/tmp/repo/docs/agentic-system/implementation/implementation-plan.json",
                "dry_run": True,
                "selected_waves": [1],
                "selected_task_ids": ["TASK-001", "TASK-002"],
                "tasks": {
                    "TASK-001": {
                        "status": "planned",
                        "wave": 1,
                        "branch": "feature/task-001",
                        "worktree": "/tmp/worktrees/task-001",
                    },
                    "TASK-002": {
                        "status": "failed",
                        "wave": 1,
                        "branch": "feature/task-002",
                        "worktree": "/tmp/worktrees/task-002",
                    },
                },
            }), encoding="utf-8")
            (second / "run-state.json").write_text(json.dumps({
                "repo": "/tmp/repo",
                "run_dir": str(second),
                "implementation_plan": "/tmp/repo/docs/agentic-system/implementation/implementation-plan.json",
                "dry_run": False,
                "selected_waves": [2],
                "selected_task_ids": ["TASK-003", "TASK-004"],
                "execution_options": {
                    "allow_codex": True,
                    "allow_pr": True,
                    "allow_review_request": True,
                    "review_agents": "codex,copilot",
                    "allow_merge": True,
                    "merge_method": "squash",
                    "max_parallel": 3,
                    "delete_branch": True,
                },
                "tasks": {
                    "TASK-003": {
                        "status": "merged",
                        "wave": 2,
                        "branch": "feature/task-003",
                        "worktree": "/tmp/worktrees/task-003",
                        "prompt_path": str(second / "tasks/TASK-003/prompt.md"),
                        "pr_number": 123,
                        "pr_url": "https://github.com/example/repo/pull/123",
                        "review_requests": [
                            {"agent": "codex", "returncode": 0},
                            {"agent": "copilot", "returncode": 0},
                        ],
                        "merge": {
                            "returncode": 0,
                            "stdout_log": str(second / "tasks/TASK-003/merge.stdout.log"),
                            "stderr_log": str(second / "tasks/TASK-003/merge.stderr.log"),
                        },
                        "merged_at": "2026-05-29T13:10:00Z",
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
        self.assertEqual(aggregate["totals"]["prs"], 1)
        self.assertEqual(aggregate["totals"]["review_requests"], 2)
        self.assertEqual(aggregate["totals"]["merged_tasks"], 1)
        self.assertEqual(aggregate["totals"]["by_status"]["planned"], 1)
        self.assertEqual(aggregate["totals"]["by_status"]["merged"], 1)
        self.assertEqual(aggregate["totals"]["by_status"]["failed"], 1)
        self.assertEqual(aggregate["totals"]["by_status"]["error"], 1)
        self.assertEqual(aggregate["runs"][0]["failed_tasks"], ["TASK-002"])
        self.assertEqual(aggregate["runs"][1]["failed_tasks"], ["TASK-004"])
        self.assertEqual(aggregate["runs"][1]["branches"], ["feature/task-003", "feature/task-004"])
        self.assertEqual(aggregate["runs"][1]["pr_numbers"], [123])
        self.assertEqual(aggregate["runs"][1]["review_request_count"], 2)
        self.assertEqual(aggregate["runs"][1]["merged_tasks"], 1)
        self.assertEqual(aggregate["runs"][1]["merge_log_paths"], [
            str(second / "tasks/TASK-003/merge.stderr.log"),
            str(second / "tasks/TASK-003/merge.stdout.log"),
        ])
        self.assertEqual(len(aggregate["runs"][0]["resume_commands"]), 1)
        first_resume = aggregate["runs"][0]["resume_commands"][0]
        self.assertIn("--dry-run", first_resume)
        self.assertIn("--wave 1", first_resume)
        self.assertIn("--task TASK-002", first_resume)
        self.assertIn("--worktree-dir /tmp/worktrees", first_resume)
        self.assertEqual(len(aggregate["runs"][1]["resume_commands"]), 1)
        resume = aggregate["runs"][1]["resume_commands"][0]
        self.assertIn(str(Path.home() / ".codex/agentic-dev-system/scripts/orchestrate_implementation_waves.py"), resume)
        self.assertIn("/tmp/repo/docs/agentic-system/implementation/implementation-plan.json", resume)
        self.assertIn(f"--run-dir {second}", resume)
        self.assertIn("--wave 2", resume)
        self.assertIn("--task TASK-004", resume)
        self.assertIn("--worktree-dir /tmp/worktrees", resume)
        self.assertIn("--allow-codex --allow-pr", resume)
        self.assertIn("--allow-review-request --review-agents codex,copilot", resume)
        self.assertIn("--allow-merge --merge-method squash --delete-branch", resume)
        self.assertIn("--max-parallel 3", resume)
        self.assertIn("--resume --reuse-worktrees", resume)
        self.assertIn("# Implementation Wave Run Report", markdown)
        self.assertIn("repo-20260529T120000Z", markdown)
        self.assertIn("failed=TASK-002", markdown)
        self.assertIn("PRs=#123", markdown)
        self.assertIn("review_requests=2", markdown)
        self.assertIn("merged=1", markdown)
        self.assertIn("Resume:", markdown)
        self.assertIn("--task TASK-004", markdown)


if __name__ == "__main__":
    unittest.main()
