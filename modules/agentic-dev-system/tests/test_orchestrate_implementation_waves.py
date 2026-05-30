import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from support_paths import script_path


SCRIPT = script_path("orchestrate_implementation_waves.py")


def run(cmd, cwd=None):
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def git(cwd, *args):
    result = run(["git", *args], cwd=cwd)
    if result.returncode:
        raise AssertionError(result.stderr or result.stdout)
    return result


def make_repo(td):
    repo = Path(td) / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test User")
    (repo / "README.md").write_text("sample\n", encoding="utf-8")
    git(repo, "add", "README.md")
    git(repo, "commit", "-m", "initial")
    return repo


def task(task_id, wave, branch=None, deps=None):
    return {
        "id": task_id,
        "epic_id": "EPIC-001",
        "wave": wave,
        "title": f"Implement {task_id}",
        "branch": branch or f"feature/{task_id.lower()}",
        "objective": f"Implement {task_id}",
        "non_goals": ["No broad cleanup"],
        "context_to_load": ["README.md"],
        "read_set": ["README.md"],
        "write_set": [f"src/{task_id.lower()}.py"],
        "dependencies": deps or [],
        "parallel_conflicts": [],
        "implementation_steps": ["Write tests first", "Implement behavior"],
        "tests_to_write_first": [f"tests/test_{task_id.lower()}.py"],
        "verification_commands": ["python3 -m unittest"],
        "acceptance_criteria": ["Verification passes"],
        "review_focus": ["correctness"],
        "rollback_notes": "Revert task branch.",
        "task_file": f"tasks/{task_id}.md",
    }


def write_plan(path, tasks):
    waves = []
    for wave_num in sorted({item["wave"] for item in tasks}):
        ids = [item["id"] for item in tasks if item["wave"] == wave_num]
        commands = []
        for item in tasks:
            if item["wave"] == wave_num:
                commands.extend(item["verification_commands"])
        waves.append({
            "wave": wave_num,
            "task_ids": ids,
            "integration_order": ids,
            "post_wave_verification": commands or ["python3 -m unittest"],
        })
    data = {
        "feature": "sample-feature",
        "source_documents": ["feature-model.json"],
        "assumptions": [],
        "open_questions": [],
        "epics": [{"id": "EPIC-001", "title": "Implement sample"}],
        "milestones": [{"id": "MILESTONE-001", "epic_ids": ["EPIC-001"]}],
        "releases": [{"id": "RELEASE-001", "milestone_ids": ["MILESTONE-001"]}],
        "tasks": tasks,
        "waves": waves,
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    task_dir = path.parent / "tasks"
    task_dir.mkdir()
    for item in tasks:
        (task_dir / f"{item['id']}.md").write_text(f"# {item['id']}\n\n{item['objective']}\n", encoding="utf-8")


class ImplementationWaveExecutorTests(unittest.TestCase):
    def test_dry_run_prints_worktrees_and_writes_state_without_creating_worktrees(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            plan = repo / "implementation-plan.json"
            run_dir = Path(td) / "run"
            worktrees = Path(td) / "worktrees"
            write_plan(plan, [task("TASK-001", 1, "feature/task-001-core-flow")])

            result = run([
                sys.executable,
                str(SCRIPT),
                str(plan),
                "--wave",
                "1",
                "--run-dir",
                str(run_dir),
                "--worktree-dir",
                str(worktrees),
                "--dry-run",
            ], cwd=repo)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("DRY-RUN", result.stdout)
            self.assertIn(str(worktrees / "feature-task-001-core-flow"), result.stdout)
            self.assertFalse(worktrees.exists())
            state = json.loads((run_dir / "run-state.json").read_text())
            self.assertTrue(state["dry_run"])
            self.assertEqual(state["selected_waves"], [1])
            self.assertEqual(state["tasks"]["TASK-001"]["status"], "planned")
            self.assertTrue((run_dir / "tasks" / "TASK-001" / "prompt.md").exists())
            self.assertFalse((repo / "run-state.json").exists())

    def test_real_mode_creates_task_worktree_and_summary_outside_repo(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            plan = repo / "implementation-plan.json"
            run_dir = Path(td) / "run"
            worktrees = Path(td) / "worktrees"
            write_plan(plan, [task("TASK-001", 1, "feature/task-001-core-flow")])

            result = run([
                sys.executable,
                str(SCRIPT),
                str(plan),
                "--run-dir",
                str(run_dir),
                "--worktree-dir",
                str(worktrees),
                "--base-ref",
                "HEAD",
            ], cwd=repo)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            worktree = worktrees / "feature-task-001-core-flow"
            self.assertTrue(worktree.exists())
            self.assertEqual(git(worktree, "branch", "--show-current").stdout.strip(), "feature/task-001-core-flow")
            summary = json.loads((run_dir / "run-summary.json").read_text())
            self.assertEqual(summary["totals"]["tasks"], 1)
            self.assertEqual(summary["totals"]["by_status"]["worktree_ready"], 1)
            self.assertFalse((repo / "run-summary.json").exists())

    def test_wave_option_limits_prepared_tasks(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            plan = repo / "implementation-plan.json"
            run_dir = Path(td) / "run"
            write_plan(plan, [
                task("TASK-001", 1),
                task("TASK-002", 2, deps=["TASK-001"]),
            ])

            result = run([
                sys.executable,
                str(SCRIPT),
                str(plan),
                "--wave",
                "2",
                "--run-dir",
                str(run_dir),
                "--worktree-dir",
                str(Path(td) / "worktrees"),
                "--dry-run",
            ], cwd=repo)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertNotIn("TASK-001", result.stdout)
            self.assertIn("TASK-002", result.stdout)
            state = json.loads((run_dir / "run-state.json").read_text())
            self.assertEqual(list(state["tasks"]), ["TASK-002"])

    def test_invalid_plan_dependency_fails_before_worktree_creation(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            plan = repo / "implementation-plan.json"
            worktrees = Path(td) / "worktrees"
            write_plan(plan, [task("TASK-001", 1, deps=["TASK-MISSING"])])

            result = run([
                sys.executable,
                str(SCRIPT),
                str(plan),
                "--worktree-dir",
                str(worktrees),
                "--dry-run",
            ], cwd=repo)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing dependency", result.stderr + result.stdout)
            self.assertFalse(worktrees.exists())

    def test_reuse_worktrees_allows_existing_worktree(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            plan = repo / "implementation-plan.json"
            worktrees = Path(td) / "worktrees"
            branch = "feature/task-001-core-flow"
            worktree = worktrees / "feature-task-001-core-flow"
            write_plan(plan, [task("TASK-001", 1, branch)])
            git(repo, "worktree", "add", "-b", branch, str(worktree), "HEAD")

            blocked = run([
                sys.executable,
                str(SCRIPT),
                str(plan),
                "--worktree-dir",
                str(worktrees),
                "--run-dir",
                str(Path(td) / "blocked-run"),
            ], cwd=repo)
            reused = run([
                sys.executable,
                str(SCRIPT),
                str(plan),
                "--worktree-dir",
                str(worktrees),
                "--run-dir",
                str(Path(td) / "reused-run"),
                "--reuse-worktrees",
            ], cwd=repo)

            self.assertNotEqual(blocked.returncode, 0)
            self.assertIn("worktree already exists", blocked.stderr + blocked.stdout)
            self.assertEqual(reused.returncode, 0, reused.stderr + reused.stdout)
            state = json.loads((Path(td) / "reused-run" / "run-state.json").read_text())
            self.assertTrue(state["tasks"]["TASK-001"]["reused_worktree"])

    def test_cleanup_artifacts_dry_run_lists_old_runs_and_worktrees_without_removing(self):
        with tempfile.TemporaryDirectory() as td:
            runs_root = Path(td) / "runs"
            worktrees = Path(td) / "worktrees"
            old_run = runs_root / "repo-20200101T000000Z"
            new_run = runs_root / "repo-new"
            old_worktree = worktrees / "feature-old"
            new_worktree = worktrees / "feature-new"
            for path in [old_run, new_run, old_worktree, new_worktree]:
                path.mkdir(parents=True)
            (old_run / "run-state.json").write_text("{}\n", encoding="utf-8")
            (new_run / "run-state.json").write_text("{}\n", encoding="utf-8")
            old_time = time.time() - (60 * 60 * 24 * 40)
            os.utime(old_run, (old_time, old_time))
            os.utime(old_worktree, (old_time, old_time))

            result = run([
                sys.executable,
                str(SCRIPT),
                "--cleanup-artifacts",
                "--dry-run",
                "--runs-root",
                str(runs_root),
                "--worktree-dir",
                str(worktrees),
                "--cleanup-older-than-days",
                "30",
            ])

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn(f"[dry-run] remove run_dir {old_run}", result.stdout)
            self.assertIn(f"[dry-run] remove worktree {old_worktree}", result.stdout)
            self.assertNotIn(str(new_run), result.stdout)
            self.assertNotIn(str(new_worktree), result.stdout)
            self.assertTrue(old_run.exists())
            self.assertTrue(old_worktree.exists())

    def test_cleanup_artifacts_removes_worktrees_through_git(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            worktrees = Path(td) / "worktrees"
            old_worktree = worktrees / "feature-old"
            git(repo, "worktree", "add", "-b", "feature/old", str(old_worktree), "HEAD")
            old_time = time.time() - (60 * 60 * 24 * 40)
            os.utime(old_worktree, (old_time, old_time))

            result = run([
                sys.executable,
                str(SCRIPT),
                "--cleanup-artifacts",
                "--confirm-cleanup",
                "--runs-root",
                str(Path(td) / "runs"),
                "--worktree-dir",
                str(worktrees),
                "--cleanup-older-than-days",
                "30",
            ], cwd=repo)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertFalse(old_worktree.exists())
            self.assertNotIn(str(old_worktree), git(repo, "worktree", "list", "--porcelain").stdout)


if __name__ == "__main__":
    unittest.main()
