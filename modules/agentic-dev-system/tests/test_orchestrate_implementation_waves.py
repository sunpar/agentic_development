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


def fake_codex_bin(bin_dir, body):
    path = Path(bin_dir) / "codex"
    path.write_text("#!/usr/bin/env python3\n" + body.strip() + "\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def fake_gh_bin(bin_dir, body):
    path = Path(bin_dir) / "gh"
    path.write_text("#!/usr/bin/env python3\n" + body.strip() + "\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def fake_merge_gate(path, log_path, body="print('merged')"):
    path = Path(path)
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib\n"
        "import sys\n"
        f"with pathlib.Path({str(log_path)!r}).open('a', encoding='utf-8') as handle:\n"
        "    handle.write(' '.join(sys.argv[1:]) + '\\n')\n"
        + body.strip()
        + "\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


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


def add_bare_origin(td, repo):
    remote = Path(td) / "origin.git"
    git(remote.parent, "init", "--bare", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-u", "origin", "main")
    return remote


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
            self.assertEqual(summary["implementation_plan"], str(plan.resolve()))
            self.assertEqual(summary["selected_task_ids"], ["TASK-001"])
            self.assertEqual(summary["totals"]["tasks"], 1)
            self.assertEqual(summary["totals"]["by_status"]["worktree_ready"], 1)
            self.assertEqual(summary["waves"][0]["status"], "succeeded")
            self.assertEqual(summary["waves"][0]["task_ids"], ["TASK-001"])
            self.assertEqual(summary["tasks"][0]["wave"], 1)
            self.assertFalse((repo / "run-summary.json").exists())

    def test_allow_codex_runs_task_prompt_and_verification(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            plan = repo / "implementation-plan.json"
            run_dir = Path(td) / "run"
            worktrees = Path(td) / "worktrees"
            bin_dir = Path(td) / "bin"
            bin_dir.mkdir()
            codex = fake_codex_bin(bin_dir, """
import pathlib
import sys
pathlib.Path('codex-args.log').write_text(' '.join(sys.argv[1:]), encoding='utf-8')
pathlib.Path('src').mkdir(exist_ok=True)
pathlib.Path('src/task-001.py').write_text('implemented\\n', encoding='utf-8')
print('codex completed task')
""")
            item = task("TASK-001", 1, "feature/task-001-core-flow")
            item["verification_commands"] = ["python3 -c \"from pathlib import Path; assert Path('src/task-001.py').exists()\""]
            write_plan(plan, [item])

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
                "--allow-codex",
                "--codex-bin",
                str(codex),
            ], cwd=repo)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            worktree = worktrees / "feature-task-001-core-flow"
            self.assertTrue((worktree / "src" / "task-001.py").exists())
            self.assertIn("exec", (worktree / "codex-args.log").read_text())
            state = json.loads((run_dir / "run-state.json").read_text())
            task_state = state["tasks"]["TASK-001"]
            self.assertEqual(task_state["status"], "implemented")
            self.assertEqual(task_state["codex"]["returncode"], 0)
            self.assertEqual(task_state["verification"][0]["returncode"], 0)
            self.assertIn("src/task-001.py", task_state["changed_files"])
            task_dir = run_dir / "tasks" / "TASK-001"
            self.assertIn("codex completed task", (task_dir / "codex.stdout.log").read_text())
            summary = json.loads((run_dir / "run-summary.json").read_text())
            self.assertEqual(summary["totals"]["by_status"]["implemented"], 1)
            self.assertEqual(summary["tasks"][0]["codex"]["returncode"], 0)

    def test_max_parallel_runs_same_wave_tasks_concurrently(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            plan = repo / "implementation-plan.json"
            run_dir = Path(td) / "run"
            worktrees = Path(td) / "worktrees"
            bin_dir = Path(td) / "bin"
            starts = Path(td) / "starts"
            bin_dir.mkdir()
            starts.mkdir()
            codex = fake_codex_bin(bin_dir, f"""
import pathlib
import sys
import time

starts = pathlib.Path({str(starts)!r})
(starts / (pathlib.Path.cwd().name + '.started')).write_text('started', encoding='utf-8')
deadline = time.time() + 1.5
while len(list(starts.glob('*.started'))) < 2 and time.time() < deadline:
    time.sleep(0.02)
if len(list(starts.glob('*.started'))) < 2:
    print('parallel peer did not start', file=sys.stderr)
    raise SystemExit(9)
pathlib.Path('src').mkdir(exist_ok=True)
pathlib.Path('src/done.txt').write_text('done\\n', encoding='utf-8')
""")
            items = [
                task("TASK-001", 1, "feature/task-001"),
                task("TASK-002", 1, "feature/task-002"),
            ]
            for item in items:
                item["verification_commands"] = ["python3 -c \"from pathlib import Path; assert Path('src/done.txt').exists()\""]
            write_plan(plan, items)

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
                "--allow-codex",
                "--codex-bin",
                str(codex),
                "--max-parallel",
                "2",
            ], cwd=repo)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            state = json.loads((run_dir / "run-state.json").read_text())
            statuses = [state["tasks"][task_id]["status"] for task_id in ["TASK-001", "TASK-002"]]
            self.assertEqual(statuses, ["implemented", "implemented"])

    def test_allow_codex_failure_records_failed_task(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            plan = repo / "implementation-plan.json"
            run_dir = Path(td) / "run"
            worktrees = Path(td) / "worktrees"
            bin_dir = Path(td) / "bin"
            bin_dir.mkdir()
            codex = fake_codex_bin(bin_dir, """
import sys
print('codex failed task', file=sys.stderr)
raise SystemExit(7)
""")
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
                "--allow-codex",
                "--codex-bin",
                str(codex),
            ], cwd=repo)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("codex exited 7", result.stderr + result.stdout)
            state = json.loads((run_dir / "run-state.json").read_text())
            task_state = state["tasks"]["TASK-001"]
            self.assertEqual(task_state["status"], "failed")
            self.assertEqual(task_state["codex"]["returncode"], 7)
            self.assertIn("codex exited 7", task_state["error"])
            self.assertIn("codex failed task", (run_dir / "tasks" / "TASK-001" / "codex.stderr.log").read_text())

    def test_dry_run_with_allow_codex_does_not_execute_codex(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            plan = repo / "implementation-plan.json"
            run_dir = Path(td) / "run"
            worktrees = Path(td) / "worktrees"
            marker = Path(td) / "codex-ran"
            bin_dir = Path(td) / "bin"
            bin_dir.mkdir()
            codex = fake_codex_bin(bin_dir, f"""
import pathlib
pathlib.Path({str(marker)!r}).write_text('ran', encoding='utf-8')
""")
            write_plan(plan, [task("TASK-001", 1, "feature/task-001-core-flow")])

            result = run([
                sys.executable,
                str(SCRIPT),
                str(plan),
                "--run-dir",
                str(run_dir),
                "--worktree-dir",
                str(worktrees),
                "--dry-run",
                "--allow-codex",
                "--codex-bin",
                str(codex),
            ], cwd=repo)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("DRY-RUN: would run codex for TASK-001", result.stdout)
            self.assertFalse(marker.exists())
            self.assertFalse(worktrees.exists())
            state = json.loads((run_dir / "run-state.json").read_text())
            self.assertEqual(state["tasks"]["TASK-001"]["status"], "planned")

    def test_run_state_records_execution_options(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            plan = repo / "implementation-plan.json"
            run_dir = Path(td) / "run"
            write_plan(plan, [task("TASK-001", 1, "feature/task-001-core-flow")])

            result = run([
                sys.executable,
                str(SCRIPT),
                str(plan),
                "--run-dir",
                str(run_dir),
                "--dry-run",
                "--allow-codex",
                "--allow-pr",
                "--allow-review-request",
                "--review-agents",
                "codex,copilot",
                "--allow-merge",
                "--merge-method",
                "rebase",
                "--max-parallel",
                "2",
                "--delete-branch",
            ], cwd=repo)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            state = json.loads((run_dir / "run-state.json").read_text())
            self.assertEqual(state["execution_options"], {
                "allow_codex": True,
                "codex_bin": "codex",
                "codex_profile": None,
                "codex_extra_args": "",
                "allow_pr": True,
                "gh_bin": "gh",
                "pr_base": None,
                "allow_review_request": True,
                "review_agents": "codex,copilot",
                "allow_merge": True,
                "no_merge": False,
                "merge_gate_script": str(SCRIPT.parents[2] / "codebase-review-system" / "scripts" / "merge_gate.py"),
                "merge_method": "rebase",
                "ci_timeout_seconds": 600,
                "ci_poll_seconds": 15,
                "review_timeout_seconds": 600,
                "review_thread_timeout_seconds": 0,
                "max_parallel": 2,
                "review_repair_attempts": 2,
                "resolve_review_threads": True,
                "delete_branch": True,
                "worktree_dir": str((Path.home() / ".codex" / "worktrees" / "implementation").resolve()),
            })

    def test_allow_pr_commits_pushes_and_creates_pr_after_codex(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            add_bare_origin(td, repo)
            plan = repo / "implementation-plan.json"
            run_dir = Path(td) / "run"
            worktrees = Path(td) / "worktrees"
            bin_dir = Path(td) / "bin"
            bin_dir.mkdir()
            codex = fake_codex_bin(bin_dir, """
import pathlib
pathlib.Path('src').mkdir(exist_ok=True)
pathlib.Path('src/task-001.py').write_text('implemented\\n', encoding='utf-8')
""")
            gh_log = Path(td) / "gh-calls.log"
            gh = fake_gh_bin(bin_dir, f"""
import pathlib
import sys
pathlib.Path({str(gh_log)!r}).write_text(' '.join(sys.argv[1:]), encoding='utf-8')
print('https://github.com/example/repo/pull/123')
""")
            item = task("TASK-001", 1, "feature/task-001-core-flow")
            item["verification_commands"] = ["python3 -c \"from pathlib import Path; assert Path('src/task-001.py').exists()\""]
            write_plan(plan, [item])

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
                "--allow-codex",
                "--allow-pr",
                "--codex-bin",
                str(codex),
                "--gh-bin",
                str(gh),
            ], cwd=repo)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            worktree = worktrees / "feature-task-001-core-flow"
            self.assertEqual(git(worktree, "log", "-1", "--pretty=%s").stdout.strip(), "TASK-001: Implement TASK-001")
            self.assertIn("feature/task-001-core-flow", git(repo, "ls-remote", "--heads", "origin").stdout)
            self.assertIn("pr create", gh_log.read_text())
            state = json.loads((run_dir / "run-state.json").read_text())
            task_state = state["tasks"]["TASK-001"]
            self.assertEqual(task_state["status"], "pr_ready")
            self.assertEqual(task_state["pr_number"], 123)
            self.assertEqual(task_state["pr_url"], "https://github.com/example/repo/pull/123")
            self.assertTrue(task_state["commit_sha"])

    def test_allow_pr_tracks_codex_commits_against_task_base(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            add_bare_origin(td, repo)
            plan = repo / "implementation-plan.json"
            run_dir = Path(td) / "run"
            worktrees = Path(td) / "worktrees"
            bin_dir = Path(td) / "bin"
            bin_dir.mkdir()
            codex = fake_codex_bin(bin_dir, """
import pathlib
import subprocess
pathlib.Path('src').mkdir(exist_ok=True)
pathlib.Path('src/task-001.py').write_text('implemented\\n', encoding='utf-8')
subprocess.run(['git', 'add', 'src/task-001.py'], check=True)
subprocess.run(['git', 'commit', '-m', 'codex internal commit'], check=True)
""")
            gh = fake_gh_bin(bin_dir, """
import sys
if sys.argv[1:3] == ['pr', 'create']:
    print('https://github.com/example/repo/pull/123')
""")
            item = task("TASK-001", 1, "feature/task-001-core-flow")
            item["verification_commands"] = ["python3 -c \"from pathlib import Path; assert Path('src/task-001.py').exists()\""]
            write_plan(plan, [item])

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
                "--allow-codex",
                "--allow-pr",
                "--codex-bin",
                str(codex),
                "--gh-bin",
                str(gh),
            ], cwd=repo)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            state = json.loads((run_dir / "run-state.json").read_text())
            task_state = state["tasks"]["TASK-001"]
            self.assertEqual(task_state["status"], "pr_ready")
            self.assertEqual(task_state["changed_files"], ["src/task-001.py"])
            self.assertEqual(git(worktrees / "feature-task-001-core-flow", "log", "-1", "--pretty=%s").stdout.strip(), "codex internal commit")

    def test_resume_retries_pr_creation_after_post_commit_failure(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            add_bare_origin(td, repo)
            plan = repo / "implementation-plan.json"
            run_dir = Path(td) / "run"
            worktrees = Path(td) / "worktrees"
            bin_dir = Path(td) / "bin"
            fail_bin_dir = Path(td) / "fail-bin"
            gh_marker = Path(td) / "gh-first-failed"
            bin_dir.mkdir()
            fail_bin_dir.mkdir()
            codex = fake_codex_bin(bin_dir, """
import pathlib
pathlib.Path('src').mkdir(exist_ok=True)
pathlib.Path('src/task-001.py').write_text('implemented\\n', encoding='utf-8')
""")
            failing_codex = fake_codex_bin(fail_bin_dir, "import sys\nsys.exit(99)")
            gh = fake_gh_bin(bin_dir, f"""
import pathlib
import sys
if sys.argv[1:3] == ['pr', 'create']:
    marker = pathlib.Path({str(gh_marker)!r})
    if not marker.exists():
        marker.write_text('failed', encoding='utf-8')
        print('transient create failure', file=sys.stderr)
        raise SystemExit(2)
    print('https://github.com/example/repo/pull/123')
""")
            item = task("TASK-001", 1, "feature/task-001-core-flow")
            item["verification_commands"] = ["python3 -c \"from pathlib import Path; assert Path('src/task-001.py').exists()\""]
            write_plan(plan, [item])

            first = run([
                sys.executable,
                str(SCRIPT),
                str(plan),
                "--run-dir",
                str(run_dir),
                "--worktree-dir",
                str(worktrees),
                "--base-ref",
                "HEAD",
                "--allow-codex",
                "--allow-pr",
                "--codex-bin",
                str(codex),
                "--gh-bin",
                str(gh),
            ], cwd=repo)
            resumed = run([
                sys.executable,
                str(SCRIPT),
                str(plan),
                "--run-dir",
                str(run_dir),
                "--worktree-dir",
                str(worktrees),
                "--base-ref",
                "HEAD",
                "--allow-codex",
                "--allow-pr",
                "--codex-bin",
                str(failing_codex),
                "--gh-bin",
                str(gh),
                "--resume",
                "--reuse-worktrees",
            ], cwd=repo)

            self.assertNotEqual(first.returncode, 0)
            self.assertEqual(resumed.returncode, 0, resumed.stderr + resumed.stdout)
            state = json.loads((run_dir / "run-state.json").read_text())
            task_state = state["tasks"]["TASK-001"]
            self.assertEqual(task_state["status"], "pr_ready")
            self.assertEqual(task_state["pr_number"], 123)

    def test_allow_pr_requires_allow_codex(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            plan = repo / "implementation-plan.json"
            write_plan(plan, [task("TASK-001", 1, "feature/task-001-core-flow")])

            result = run([
                sys.executable,
                str(SCRIPT),
                str(plan),
                "--allow-pr",
            ], cwd=repo)

            self.assertEqual(result.returncode, 2)
            self.assertIn("--allow-pr requires --allow-codex", result.stderr + result.stdout)

    def test_resume_allow_merge_uses_existing_pr_ready_task(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            add_bare_origin(td, repo)
            plan = repo / "implementation-plan.json"
            run_dir = Path(td) / "run"
            worktrees = Path(td) / "worktrees"
            bin_dir = Path(td) / "bin"
            bin_dir.mkdir()
            fail_bin_dir = Path(td) / "fail-bin"
            fail_bin_dir.mkdir()
            codex = fake_codex_bin(bin_dir, """
import pathlib
pathlib.Path('src').mkdir(exist_ok=True)
pathlib.Path('src/task-001.py').write_text('implemented\\n', encoding='utf-8')
""")
            gh = fake_gh_bin(bin_dir, """
import sys
if sys.argv[1:3] == ['pr', 'create']:
    print('https://github.com/example/repo/pull/123')
""")
            failing_codex = fake_codex_bin(fail_bin_dir, "import sys\nsys.exit(99)")
            merge_log = Path(td) / "merge-gate.log"
            merge_gate = fake_merge_gate(Path(td) / "merge_gate.py", merge_log)
            item = task("TASK-001", 1, "feature/task-001-core-flow")
            item["verification_commands"] = ["python3 -c \"from pathlib import Path; assert Path('src/task-001.py').exists()\""]
            write_plan(plan, [item])

            first = run([
                sys.executable,
                str(SCRIPT),
                str(plan),
                "--run-dir",
                str(run_dir),
                "--worktree-dir",
                str(worktrees),
                "--base-ref",
                "HEAD",
                "--allow-codex",
                "--allow-pr",
                "--codex-bin",
                str(codex),
                "--gh-bin",
                str(gh),
            ], cwd=repo)
            resumed = run([
                sys.executable,
                str(SCRIPT),
                str(plan),
                "--run-dir",
                str(run_dir),
                "--worktree-dir",
                str(worktrees),
                "--base-ref",
                "HEAD",
                "--allow-codex",
                "--allow-pr",
                "--allow-merge",
                "--merge-gate-script",
                str(merge_gate),
                "--codex-bin",
                str(failing_codex),
                "--gh-bin",
                str(gh),
                "--resume",
                "--reuse-worktrees",
            ], cwd=repo)

            self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
            self.assertEqual(resumed.returncode, 0, resumed.stderr + resumed.stdout)
            self.assertIn("--pr 123", merge_log.read_text())
            state = json.loads((run_dir / "run-state.json").read_text())
            self.assertEqual(state["tasks"]["TASK-001"]["status"], "merged")

    def test_allow_review_request_comments_on_created_pr(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            add_bare_origin(td, repo)
            plan = repo / "implementation-plan.json"
            run_dir = Path(td) / "run"
            worktrees = Path(td) / "worktrees"
            bin_dir = Path(td) / "bin"
            bin_dir.mkdir()
            codex = fake_codex_bin(bin_dir, """
import pathlib
pathlib.Path('src').mkdir(exist_ok=True)
pathlib.Path('src/task-001.py').write_text('implemented\\n', encoding='utf-8')
""")
            gh_log = Path(td) / "gh-calls.log"
            gh = fake_gh_bin(bin_dir, f"""
import pathlib
import sys
args = ' '.join(sys.argv[1:])
with pathlib.Path({str(gh_log)!r}).open('a', encoding='utf-8') as handle:
    handle.write(args + '\\n')
if sys.argv[1:3] == ['pr', 'create']:
    print('https://github.com/example/repo/pull/123')
elif sys.argv[1:3] == ['pr', 'comment']:
    print('https://github.com/example/repo/pull/123#issuecomment-1')
""")
            item = task("TASK-001", 1, "feature/task-001-core-flow")
            item["verification_commands"] = ["python3 -c \"from pathlib import Path; assert Path('src/task-001.py').exists()\""]
            write_plan(plan, [item])

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
                "--allow-codex",
                "--allow-pr",
                "--allow-review-request",
                "--review-agents",
                "codex,copilot",
                "--codex-bin",
                str(codex),
                "--gh-bin",
                str(gh),
            ], cwd=repo)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            calls = gh_log.read_text()
            self.assertIn("pr comment 123", calls)
            self.assertIn("@codex please review", calls)
            self.assertIn("pr edit 123 --add-reviewer @copilot", calls)
            state = json.loads((run_dir / "run-state.json").read_text())
            requests = state["tasks"]["TASK-001"]["review_requests"]
            self.assertEqual([item["agent"] for item in requests], ["codex", "copilot"])
            self.assertTrue(all(item["returncode"] == 0 for item in requests))

    def test_allow_review_request_rejects_empty_reviewer_list(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            plan = repo / "implementation-plan.json"
            write_plan(plan, [task("TASK-001", 1, "feature/task-001-core-flow")])

            result = run([
                sys.executable,
                str(SCRIPT),
                str(plan),
                "--dry-run",
                "--allow-codex",
                "--allow-pr",
                "--allow-review-request",
                "--review-agents",
                "",
            ], cwd=repo)

            self.assertEqual(result.returncode, 2)
            self.assertIn("--review-agents must include at least one agent", result.stderr + result.stdout)

    def test_allow_review_request_requires_allow_pr(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            plan = repo / "implementation-plan.json"
            write_plan(plan, [task("TASK-001", 1, "feature/task-001-core-flow")])

            result = run([
                sys.executable,
                str(SCRIPT),
                str(plan),
                "--allow-codex",
                "--allow-review-request",
            ], cwd=repo)

            self.assertEqual(result.returncode, 2)
            self.assertIn("--allow-review-request requires --allow-pr", result.stderr + result.stdout)

    def test_allow_merge_runs_merge_gate_after_created_pr(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            add_bare_origin(td, repo)
            plan = repo / "implementation-plan.json"
            run_dir = Path(td) / "run"
            worktrees = Path(td) / "worktrees"
            bin_dir = Path(td) / "bin"
            bin_dir.mkdir()
            codex = fake_codex_bin(bin_dir, """
import pathlib
pathlib.Path('src').mkdir(exist_ok=True)
pathlib.Path('src/task-001.py').write_text('implemented\\n', encoding='utf-8')
""")
            gh = fake_gh_bin(bin_dir, """
import sys
if sys.argv[1:3] == ['pr', 'create']:
    print('https://github.com/example/repo/pull/123')
""")
            merge_log = Path(td) / "merge-gate.log"
            merge_gate = fake_merge_gate(Path(td) / "merge_gate.py", merge_log)
            item = task("TASK-001", 1, "feature/task-001-core-flow")
            item["verification_commands"] = ["python3 -c \"from pathlib import Path; assert Path('src/task-001.py').exists()\""]
            write_plan(plan, [item])

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
                "--allow-codex",
                "--allow-pr",
                "--allow-merge",
                "--merge-gate-script",
                str(merge_gate),
                "--merge-method",
                "squash",
                "--delete-branch",
                "--codex-bin",
                str(codex),
                "--gh-bin",
                str(gh),
            ], cwd=repo)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            worktree = worktrees / "feature-task-001-core-flow"
            calls = merge_log.read_text()
            self.assertIn("--pr 123", calls)
            self.assertIn(f"--repo-path {worktree.resolve()}", calls)
            self.assertIn("--allow-merge", calls)
            self.assertIn("--merge-method squash", calls)
            self.assertIn("--expected-head-sha", calls)
            self.assertIn("--delete-branch", calls)
            state = json.loads((run_dir / "run-state.json").read_text())
            task_state = state["tasks"]["TASK-001"]
            self.assertEqual(task_state["status"], "merged")
            self.assertTrue(task_state["merged_at"])
            self.assertEqual(task_state["merge"]["returncode"], 0)
            self.assertTrue((run_dir / "tasks" / "TASK-001" / "merge.stdout.log").exists())
            self.assertTrue((run_dir / "tasks" / "TASK-001" / "merge.stderr.log").exists())
            summary = json.loads((run_dir / "run-summary.json").read_text())
            self.assertEqual(summary["totals"]["by_status"]["merged"], 1)
            self.assertEqual(summary["tasks"][0]["merge"]["returncode"], 0)

    def test_allow_merge_repairs_unresolved_review_threads_and_retries_gate(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            add_bare_origin(td, repo)
            plan = repo / "implementation-plan.json"
            run_dir = Path(td) / "run"
            worktrees = Path(td) / "worktrees"
            bin_dir = Path(td) / "bin"
            marker = Path(td) / "repair-done"
            gh_log = Path(td) / "gh-calls.log"
            merge_log = Path(td) / "merge-gate.log"
            bin_dir.mkdir()
            codex = fake_codex_bin(bin_dir, f"""
import pathlib
import sys

prompt = sys.argv[-1]
pathlib.Path('src').mkdir(exist_ok=True)
if 'Active review threads JSON' in prompt:
    pathlib.Path('src/task-001.py').write_text('repaired\\n', encoding='utf-8')
    pathlib.Path({str(marker)!r}).write_text('done', encoding='utf-8')
else:
    pathlib.Path('src/task-001.py').write_text('implemented\\n', encoding='utf-8')
""")
            gh = fake_gh_bin(bin_dir, f"""
import json
import pathlib
import sys

args = sys.argv[1:]
with pathlib.Path({str(gh_log)!r}).open('a', encoding='utf-8') as handle:
    handle.write(' '.join(args) + '\\n')
if args[:2] == ['pr', 'create']:
    print('https://github.com/example/repo/pull/123')
elif args[:2] == ['pr', 'comment']:
    print('https://github.com/example/repo/pull/123#issuecomment-1')
elif args[:2] == ['api', 'graphql']:
    joined = ' '.join(args)
    if 'resolveReviewThread' in joined:
        print(json.dumps({{'data': {{'resolveReviewThread': {{'thread': {{'id': 'THREAD1', 'isResolved': True}}}}}}}}))
    else:
        nodes = [] if pathlib.Path({str(marker)!r}).exists() else [{{
            'id': 'THREAD1',
            'isResolved': False,
            'isOutdated': False,
            'path': 'src/task-001.py',
            'line': 1,
            'comments': {{'nodes': [{{'body': 'Please fix this', 'author': {{'login': 'reviewer'}}}}]}},
        }}]
        print(json.dumps({{'data': {{'repository': {{'pullRequest': {{'reviewThreads': {{'nodes': nodes, 'pageInfo': {{'hasNextPage': False}}}}}}}}}}}}))
""")
            merge_gate = fake_merge_gate(Path(td) / "merge_gate.py", merge_log, f"""
import pathlib
import sys
if not pathlib.Path({str(marker)!r}).exists():
    print('unresolved review threads remain', file=sys.stderr)
    raise SystemExit(2)
print('merged')
""")
            item = task("TASK-001", 1, "feature/task-001-core-flow")
            item["verification_commands"] = ["python3 -c \"from pathlib import Path; assert Path('src/task-001.py').exists()\""]
            write_plan(plan, [item])

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
                "--allow-codex",
                "--allow-pr",
                "--allow-review-request",
                "--allow-merge",
                "--review-repair-attempts",
                "1",
                "--merge-gate-script",
                str(merge_gate),
                "--codex-bin",
                str(codex),
                "--gh-bin",
                str(gh),
            ], cwd=repo)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("review repair attempt 1/1", result.stdout)
            state = json.loads((run_dir / "run-state.json").read_text())
            task_state = state["tasks"]["TASK-001"]
            self.assertEqual(task_state["status"], "merged")
            self.assertEqual(task_state["review_repair_attempts"][0]["status"], "pushed")
            self.assertEqual(task_state["review_repair_attempts"][0]["resolved_threads"][0]["thread_id"], "THREAD1")
            self.assertTrue((run_dir / "tasks" / "TASK-001" / "review-repair-1.stdout.log").exists())
            self.assertIn("pr comment 123", gh_log.read_text())
            self.assertGreaterEqual(merge_log.read_text().count("--pr 123"), 2)

    def test_allow_merge_requires_allow_pr(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            plan = repo / "implementation-plan.json"
            write_plan(plan, [task("TASK-001", 1, "feature/task-001-core-flow")])

            result = run([
                sys.executable,
                str(SCRIPT),
                str(plan),
                "--allow-codex",
                "--allow-merge",
            ], cwd=repo)

            self.assertEqual(result.returncode, 2)
            self.assertIn("--allow-merge requires --allow-pr", result.stderr + result.stdout)

    def test_pr_only_alias_overrides_allow_merge(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            plan = repo / "implementation-plan.json"
            write_plan(plan, [task("TASK-001", 1, "feature/task-001-core-flow")])

            result = run([
                sys.executable,
                str(SCRIPT),
                str(plan),
                "--run-dir",
                str(Path(td) / "run"),
                "--dry-run",
                "--allow-merge",
                "--pr-only",
            ], cwd=repo)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("DRY-RUN", result.stdout)

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

    def test_task_option_limits_prepared_tasks(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            plan = repo / "implementation-plan.json"
            run_dir = Path(td) / "run"
            write_plan(plan, [
                task("TASK-001", 1),
                task("TASK-002", 1),
            ])

            result = run([
                sys.executable,
                str(SCRIPT),
                str(plan),
                "--task",
                "TASK-002",
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
            self.assertEqual(state["selected_task_ids"], ["TASK-002"])
            self.assertEqual(list(state["tasks"]), ["TASK-002"])

    def test_task_option_rejects_unknown_or_unselected_wave_task(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            plan = repo / "implementation-plan.json"
            write_plan(plan, [
                task("TASK-001", 1),
                task("TASK-002", 2, deps=["TASK-001"]),
            ])

            missing = run([
                sys.executable,
                str(SCRIPT),
                str(plan),
                "--task",
                "TASK-404",
                "--dry-run",
            ], cwd=repo)
            wrong_wave = run([
                sys.executable,
                str(SCRIPT),
                str(plan),
                "--wave",
                "2",
                "--task",
                "TASK-001",
                "--dry-run",
            ], cwd=repo)

            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("task TASK-404 not found in plan", missing.stderr + missing.stdout)
            self.assertNotEqual(wrong_wave.returncode, 0)
            self.assertIn("task TASK-001 is not in selected wave(s)", wrong_wave.stderr + wrong_wave.stdout)

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

    def test_failure_after_partial_prepare_writes_checkpoint_and_summary(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            plan = repo / "implementation-plan.json"
            run_dir = Path(td) / "run"
            worktrees = Path(td) / "worktrees"
            write_plan(plan, [
                task("TASK-001", 1, "feature/task-001"),
                task("TASK-002", 1, "feature/task-002"),
                task("TASK-003", 2, "feature/task-003", deps=["TASK-001"]),
            ])
            git(repo, "branch", "feature/task-002", "HEAD")

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

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("branch already exists: feature/task-002", result.stderr + result.stdout)
            self.assertTrue((worktrees / "feature-task-001").exists())
            state = json.loads((run_dir / "run-state.json").read_text())
            summary = json.loads((run_dir / "run-summary.json").read_text())
            self.assertEqual(state["tasks"]["TASK-001"]["status"], "worktree_ready")
            self.assertEqual(state["tasks"]["TASK-002"]["status"], "failed")
            self.assertIn("branch already exists", state["tasks"]["TASK-002"]["error"])
            self.assertEqual(state["waves"]["1"]["status"], "failed")
            self.assertEqual(state["waves"]["1"]["task_ids"], ["TASK-001", "TASK-002"])
            self.assertNotIn("2", state["waves"])
            self.assertNotIn("TASK-003", state["tasks"])
            self.assertEqual(summary["waves"][0]["status"], "failed")
            self.assertEqual(summary["totals"]["by_status"]["worktree_ready"], 1)
            self.assertEqual(summary["totals"]["by_status"]["failed"], 1)
            self.assertIn("branch already exists", summary["tasks"][1]["error"])
            self.assertIn("TASK-002", (run_dir / "run-summary.md").read_text())

    def test_resume_skips_ready_tasks_and_retries_failed_tasks(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            plan = repo / "implementation-plan.json"
            run_dir = Path(td) / "run"
            worktrees = Path(td) / "worktrees"
            write_plan(plan, [
                task("TASK-001", 1, "feature/task-001"),
                task("TASK-002", 1, "feature/task-002"),
            ])
            git(repo, "branch", "feature/task-002", "HEAD")

            first = run([
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
            resumed = run([
                sys.executable,
                str(SCRIPT),
                str(plan),
                "--run-dir",
                str(run_dir),
                "--worktree-dir",
                str(worktrees),
                "--base-ref",
                "HEAD",
                "--resume",
                "--reuse-worktrees",
            ], cwd=repo)

            self.assertNotEqual(first.returncode, 0)
            self.assertEqual(resumed.returncode, 0, resumed.stderr + resumed.stdout)
            self.assertIn("RESUME: skipping TASK-001 status worktree_ready", resumed.stdout)
            state = json.loads((run_dir / "run-state.json").read_text())
            self.assertEqual(state["tasks"]["TASK-001"]["status"], "worktree_ready")
            self.assertEqual(state["tasks"]["TASK-002"]["status"], "worktree_ready")
            self.assertTrue((worktrees / "feature-task-001").exists())
            self.assertTrue((worktrees / "feature-task-002").exists())

    def test_resume_rejects_run_state_for_different_plan_hash(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(td)
            plan = repo / "implementation-plan.json"
            run_dir = Path(td) / "run"
            write_plan(plan, [task("TASK-001", 1, "feature/task-001")])
            first = run([
                sys.executable,
                str(SCRIPT),
                str(plan),
                "--run-dir",
                str(run_dir),
                "--worktree-dir",
                str(Path(td) / "worktrees"),
                "--dry-run",
            ], cwd=repo)
            data = json.loads(plan.read_text())
            data["tasks"][0]["objective"] = "Changed after run state was written."
            plan.write_text(json.dumps(data, indent=2), encoding="utf-8")

            resumed = run([
                sys.executable,
                str(SCRIPT),
                str(plan),
                "--run-dir",
                str(run_dir),
                "--worktree-dir",
                str(Path(td) / "worktrees"),
                "--dry-run",
                "--resume",
            ], cwd=repo)

            self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
            self.assertNotEqual(resumed.returncode, 0)
            self.assertIn("run-state implementation plan hash mismatch", resumed.stderr + resumed.stdout)


if __name__ == "__main__":
    unittest.main()
