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

    def test_state_enrichment_recomputes_totals_and_prefers_state_waves(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "runs"
            run_dir = root / "repo-20260529T150000Z"
            run_dir.mkdir(parents=True)
            (run_dir / "run-summary.json").write_text(json.dumps({
                "repo": "/tmp/repo",
                "run_dir": str(run_dir),
                "selected_waves": [1],
                "totals": {
                    "tasks": 1,
                    "by_status": {"planned": 1},
                },
                "waves": [
                    {"wave": 1, "status": "running", "task_ids": ["TASK-001"]},
                ],
                "tasks": [
                    {"id": "TASK-001", "status": "planned"},
                ],
            }), encoding="utf-8")
            (run_dir / "run-state.json").write_text(json.dumps({
                "repo": "/tmp/repo",
                "run_dir": str(run_dir),
                "selected_waves": [1],
                "selected_task_ids": ["TASK-001", "TASK-002"],
                "waves": {
                    "1": {"wave": 1, "status": "failed", "task_ids": ["TASK-001", "TASK-002"], "error": "boom"},
                },
                "tasks": {
                    "TASK-001": {"status": "planned"},
                    "TASK-002": {"status": "failed", "wave": 1, "worktree": "/tmp/worktrees/task-002"},
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

        run_summary = aggregate["runs"][0]
        self.assertEqual(run_summary["totals"]["tasks"], 2)
        self.assertEqual(run_summary["totals"]["by_status"], {"failed": 1, "planned": 1})
        self.assertEqual(run_summary["waves"][0]["status"], "failed")
        self.assertEqual(run_summary["failed_waves"], [1])

    def test_resume_command_runs_from_repo_and_preserves_selected_tasks(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "runs"
            run_dir = root / "repo-20260529T160000Z"
            run_dir.mkdir(parents=True)
            (run_dir / "run-state.json").write_text(json.dumps({
                "repo": "/tmp/repo",
                "run_dir": str(run_dir),
                "implementation_plan": "/tmp/repo/docs/implementation-plan.json",
                "dry_run": False,
                "selected_waves": [1],
                "selected_task_ids": ["TASK-001", "TASK-002"],
                "execution_options": {"allow_codex": True, "allow_pr": True},
                "tasks": {
                    "TASK-001": {"status": "implemented", "wave": 1, "worktree": "/tmp/worktrees/task-001"},
                    "TASK-002": {"status": "failed", "wave": 1, "worktree": "/tmp/worktrees/task-002"},
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

        resume = aggregate["runs"][0]["resume_commands"][0]
        self.assertTrue(resume.startswith("cd /tmp/repo && "))
        self.assertIn("--task TASK-001 --task TASK-002", resume)

    def test_resume_command_limits_selected_tasks_to_failed_task_wave(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "runs"
            run_dir = root / "repo-20260529T170000Z"
            run_dir.mkdir(parents=True)
            (run_dir / "run-state.json").write_text(json.dumps({
                "repo": "/tmp/repo",
                "run_dir": str(run_dir),
                "implementation_plan": "/tmp/repo/docs/implementation-plan.json",
                "dry_run": False,
                "selected_waves": [1, 2],
                "selected_task_ids": ["TASK-001", "TASK-002"],
                "tasks": {
                    "TASK-001": {"status": "failed", "wave": 1, "worktree": "/tmp/worktrees/task-001"},
                    "TASK-002": {"status": "planned", "wave": 2, "worktree": "/tmp/worktrees/task-002"},
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

        resume = aggregate["runs"][0]["resume_commands"][0]
        self.assertIn("--wave 1", resume)
        self.assertIn("--task TASK-001", resume)
        self.assertNotIn("--task TASK-002", resume)

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
                "waves": [
                    {
                        "wave": 1,
                        "status": "failed",
                        "task_ids": ["TASK-001", "TASK-002"],
                        "error": "TASK-002: branch already exists",
                    },
                ],
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
                "waves": {
                    "1": {
                        "wave": 1,
                        "status": "failed",
                        "task_ids": ["TASK-001", "TASK-002"],
                        "error": "TASK-002: branch already exists",
                    },
                },
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
                "waves": {
                    "2": {
                        "wave": 2,
                        "status": "succeeded",
                        "task_ids": ["TASK-003", "TASK-004"],
                    },
                },
                "execution_options": {
                    "allow_codex": True,
                    "codex_bin": "/opt/bin/codex-wrapper",
                    "codex_profile": "prod",
                    "codex_extra_args": "--config foo=bar",
                    "allow_pr": True,
                    "gh_bin": "/opt/bin/gh-wrapper",
                    "pr_base": "release",
                    "allow_review_request": True,
                    "review_agents": "codex,copilot",
                    "allow_merge": True,
                    "merge_gate_script": "/tmp/custom-merge-gate.py",
                    "merge_method": "squash",
                    "ci_timeout_seconds": 42,
                    "ci_poll_seconds": 3,
                    "review_timeout_seconds": 43,
                    "review_thread_timeout_seconds": 4,
                    "max_parallel": 3,
                    "review_repair_attempts": 2,
                    "resolve_review_threads": False,
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
                        "review_repair_attempts": [
                            {"attempt": 1, "status": "pushed"},
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
        self.assertEqual(aggregate["totals"]["review_repairs"], 1)
        self.assertEqual(aggregate["totals"]["merged_tasks"], 1)
        self.assertEqual(aggregate["totals"]["failed_waves"], 1)
        self.assertEqual(aggregate["totals"]["by_status"]["planned"], 1)
        self.assertEqual(aggregate["totals"]["by_status"]["merged"], 1)
        self.assertEqual(aggregate["totals"]["by_status"]["failed"], 1)
        self.assertEqual(aggregate["totals"]["by_status"]["error"], 1)
        self.assertEqual(aggregate["runs"][0]["failed_waves"], [1])
        self.assertEqual(aggregate["runs"][1]["waves"][0]["status"], "succeeded")
        self.assertEqual(aggregate["runs"][0]["failed_tasks"], ["TASK-002"])
        self.assertEqual(aggregate["runs"][1]["failed_tasks"], ["TASK-004"])
        self.assertEqual(aggregate["runs"][1]["branches"], ["feature/task-003", "feature/task-004"])
        self.assertEqual(aggregate["runs"][1]["pr_numbers"], [123])
        self.assertEqual(aggregate["runs"][1]["review_request_count"], 2)
        self.assertEqual(aggregate["runs"][1]["review_repair_count"], 1)
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
        self.assertIn("--allow-codex --codex-bin /opt/bin/codex-wrapper --codex-profile prod", resume)
        self.assertIn("--codex-extra-args '--config foo=bar'", resume)
        self.assertIn("--allow-pr --gh-bin /opt/bin/gh-wrapper --pr-base release", resume)
        self.assertIn("--allow-review-request --review-agents codex,copilot", resume)
        self.assertIn("--merge-gate-script /tmp/custom-merge-gate.py", resume)
        self.assertIn("--ci-timeout-seconds 42 --ci-poll-seconds 3", resume)
        self.assertIn("--review-timeout-seconds 43 --review-thread-timeout-seconds 4", resume)
        self.assertIn("--allow-merge", resume)
        self.assertIn("--merge-method squash", resume)
        self.assertIn("--delete-branch", resume)
        self.assertIn("--max-parallel 3", resume)
        self.assertIn("--review-repair-attempts 2 --no-resolve-review-threads", resume)
        self.assertIn("--resume --reuse-worktrees", resume)
        self.assertIn("# Implementation Wave Run Report", markdown)
        self.assertIn("repo-20260529T120000Z", markdown)
        self.assertIn("failed=TASK-002", markdown)
        self.assertIn("failed_waves=1", markdown)
        self.assertIn("PRs=#123", markdown)
        self.assertIn("review_requests=2", markdown)
        self.assertIn("review_repairs=1", markdown)
        self.assertIn("merged=1", markdown)
        self.assertIn("Resume:", markdown)
        self.assertIn("--task TASK-004", markdown)


if __name__ == "__main__":
    unittest.main()
