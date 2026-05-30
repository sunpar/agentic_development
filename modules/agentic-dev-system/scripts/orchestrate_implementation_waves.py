#!/usr/bin/env python3
"""Prepare and optionally execute implementation task waves."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from validate_plan import validate_plan  # noqa: E402

MODEL_ARGS = ["--model", "gpt-5.3-codex-spark", "-c", 'model_reasoning_effort="xhigh"']


def default_merge_gate_script():
    source_copy = SCRIPT_DIR.parent.parent / "codebase-review-system" / "scripts" / "merge_gate.py"
    if source_copy.exists():
        return source_copy
    return Path.home() / ".codex" / "codebase-review-factory" / "scripts" / "merge_gate.py"


def now_utc():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_cmd(cmd, cwd=None):
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def run_shell(command, cwd=None):
    return subprocess.run(
        command,
        cwd=cwd,
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def repo_root(cwd="."):
    result = run_cmd(["git", "rev-parse", "--show-toplevel"], cwd=cwd)
    if result.returncode:
        raise RuntimeError("not inside a git repository")
    return Path(result.stdout.strip()).resolve()


def current_branch(cwd):
    result = run_cmd(["git", "branch", "--show-current"], cwd=cwd)
    return result.stdout.strip() if result.returncode == 0 else ""


def branch_exists(repo, branch):
    return run_cmd(["git", "show-ref", "--verify", f"refs/heads/{branch}"], cwd=repo).returncode == 0


def valid_branch_name(repo, branch):
    return run_cmd(["git", "check-ref-format", "--branch", branch], cwd=repo).returncode == 0


def sanitize_worktree_name(branch):
    return re.sub(r"[^a-zA-Z0-9_.-]", "-", branch).strip("-") or "task-worktree"


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def safe_extra_args(value):
    args = shlex.split(value) if value else []
    banned = {"--model", "-m", "--sandbox", "-s", "--dangerously-bypass-approvals-and-sandbox", "--dangerously-bypass-hook-trust"}
    for index, arg in enumerate(args):
        if arg in banned or arg.startswith("--model=") or arg.startswith("--sandbox="):
            raise RuntimeError(f"unsafe --codex-extra-args token blocked: {arg}")
        if arg in {"-c", "--config"}:
            nxt = args[index + 1] if index + 1 < len(args) else ""
            if any(key in nxt for key in ["model", "model_reasoning_effort", "sandbox", "danger"]):
                raise RuntimeError(f"unsafe --codex-extra-args config blocked: {nxt}")
    return args


def cleanup_cutoff(older_than_days):
    return time.time() - (older_than_days * 24 * 60 * 60)


def cleanup_candidates(root: Path, older_than_days: int, require_run_state=False):
    root = root.expanduser()
    if not root.exists():
        return []
    cutoff = cleanup_cutoff(older_than_days)
    candidates = []
    for child in sorted(root.iterdir(), key=lambda path: str(path)):
        if not child.exists() or not child.is_dir():
            continue
        if require_run_state and not (child / "run-state.json").exists():
            continue
        try:
            mtime = child.stat().st_mtime
        except OSError:
            continue
        if mtime <= cutoff:
            candidates.append(child)
    return candidates


def remove_artifact(path: Path):
    if path.is_symlink():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def remove_worktree_artifact(path: Path):
    top_result = run_cmd(["git", "-C", str(path), "rev-parse", "--show-toplevel"])
    if top_result.returncode or Path(top_result.stdout.strip()).resolve() != path.resolve():
        remove_artifact(path)
        return {"removed_by": "filesystem"}
    result = run_cmd(["git", "-C", str(path), "worktree", "remove", "--force", str(path)])
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout or f"git worktree remove failed for {path}")
    return {
        "removed_by": "git worktree remove",
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def remove_cleanup_artifact(kind, path: Path):
    if kind == "worktree":
        return remove_worktree_artifact(path)
    remove_artifact(path)
    return {"removed_by": "filesystem"}


def cleanup_artifacts(args):
    if args.cleanup_older_than_days < 0:
        print("--cleanup-older-than-days must be zero or greater", file=sys.stderr)
        return 2
    runs_root = Path(args.runs_root).expanduser()
    worktree_dir = Path(args.worktree_dir).expanduser()
    candidates = [
        ("run_dir", path)
        for path in cleanup_candidates(runs_root, args.cleanup_older_than_days, require_run_state=True)
    ] + [
        ("worktree", path)
        for path in cleanup_candidates(worktree_dir, args.cleanup_older_than_days, require_run_state=False)
    ]
    if not candidates:
        print("no cleanup artifacts matched")
        return 0
    if not args.dry_run and not args.confirm_cleanup:
        print("refusing to remove artifacts without --confirm-cleanup or --dry-run", file=sys.stderr)
        return 2
    for kind, path in candidates:
        if args.dry_run:
            print(f"[dry-run] remove {kind} {path}")
        else:
            remove_cleanup_artifact(kind, path)
            print(f"removed {kind} {path}")
    return 0


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def file_sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def task_map(plan):
    return {
        task["id"]: task
        for task in plan.get("tasks", [])
        if isinstance(task, dict) and task.get("id")
    }


def selected_waves(plan, wave_number):
    waves = [wave for wave in plan.get("waves", []) if isinstance(wave, dict)]
    if wave_number is None:
        return waves
    selected = [wave for wave in waves if int(wave.get("wave", -1)) == wave_number]
    if not selected:
        raise RuntimeError(f"wave {wave_number} not found in plan")
    return selected


def selected_tasks(plan, wave_number, requested_task_ids=None):
    tasks = task_map(plan)
    selected_ids = []
    for wave in selected_waves(plan, wave_number):
        for task_id in wave.get("task_ids", []):
            if task_id in tasks:
                selected_ids.append(task_id)
    if requested_task_ids:
        requested = list(dict.fromkeys(requested_task_ids))
        for task_id in requested:
            if task_id not in tasks:
                raise RuntimeError(f"task {task_id} not found in plan")
        allowed = set(selected_ids)
        for task_id in requested:
            if task_id not in allowed:
                raise RuntimeError(f"task {task_id} is not in selected wave(s)")
        requested_set = set(requested)
        selected_ids = [task_id for task_id in selected_ids if task_id in requested_set]
    return [tasks[task_id] for task_id in selected_ids]


def status_counts(tasks):
    counts = {}
    for item in tasks.values():
        status = item.get("status") or "unknown"
        counts[status] = counts.get(status, 0) + 1
    return counts


def build_prompt(task, plan_path, task_markdown_path):
    lines = [
        f"Use task-implementor for {task['id']}.",
        f"Task ID: {task['id']}",
        f"Implementation plan: {plan_path}",
        f"Task spec: {task_markdown_path or task.get('task_file', '')}",
        f"Branch: {task.get('branch', '')}",
        f"Context to load: {task.get('context_to_load', [])}",
        f"Write set: {task.get('write_set', [])}",
        f"Tests to write first: {task.get('tests_to_write_first', [])}",
        f"Verification commands: {task.get('verification_commands', [])}",
        "Follow TDD: write failing tests first, implement minimally, then run verification.",
        "Do not create PRs, request review, or merge from this prompt.",
    ]
    return "\n".join(lines) + "\n"


def codex_command(args, prompt):
    cmd = [args.codex_bin, "exec"] + MODEL_ARGS
    if args.codex_profile:
        cmd += ["--profile", args.codex_profile]
    cmd += safe_extra_args(args.codex_extra_args)
    cmd.append(prompt)
    return cmd


def run_codex_task(args, worktree, prompt_path, task_dir):
    prompt = Path(prompt_path).read_text(encoding="utf-8")
    cmd = codex_command(args, prompt)
    result = run_cmd(cmd, cwd=worktree)
    stdout_log = task_dir / "codex.stdout.log"
    stderr_log = task_dir / "codex.stderr.log"
    stdout_log.write_text(result.stdout, encoding="utf-8")
    stderr_log.write_text(result.stderr, encoding="utf-8")
    return {
        "returncode": result.returncode,
        "stdout_log": str(stdout_log),
        "stderr_log": str(stderr_log),
    }


def verification_results(commands, cwd):
    results = []
    for command in commands:
        result = run_shell(command, cwd)
        results.append({
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        })
    return results


def failed_verification(results):
    return next((item for item in results if item["returncode"] != 0), None)


def changed_files(worktree):
    result = run_cmd(["git", "status", "--short", "--untracked-files=all"], cwd=worktree)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout or "git status failed")
    files = []
    for line in result.stdout.splitlines():
        if not line:
            continue
        files.append(line[3:].strip())
    return files


def commit_task(worktree, task, files):
    if not files:
        return None
    add = run_cmd(["git", "add", "--", *files], cwd=worktree)
    if add.returncode:
        raise RuntimeError(add.stderr or add.stdout or "git add failed")
    title = str(task.get("title") or task["id"]).strip()
    commit = run_cmd(["git", "commit", "-m", f"{task['id']}: {title}"], cwd=worktree)
    if commit.returncode:
        raise RuntimeError(commit.stderr or commit.stdout or "git commit failed")
    head = run_cmd(["git", "rev-parse", "HEAD"], cwd=worktree)
    if head.returncode:
        raise RuntimeError(head.stderr or head.stdout or "git rev-parse failed")
    return head.stdout.strip()


def push_branch(worktree, branch):
    result = run_cmd(["git", "push", "-u", "origin", branch], cwd=worktree)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout or "git push failed")


def pr_body(task, verification):
    lines = [
        "## Summary",
        f"- {task.get('objective') or task.get('title') or task['id']}",
        "",
        "## Verification",
    ]
    if verification:
        for item in verification:
            status = "PASS" if item.get("returncode") == 0 else "FAIL"
            lines.append(f"- {status}: `{item.get('command')}`")
    else:
        lines.append("- No verification commands were declared.")
    return "\n".join(lines)


def parse_pr_number(url):
    tail = str(url).rstrip("/").split("/")[-1]
    return int(tail) if tail.isdigit() else None


def create_task_pr(args, worktree, task, branch, base_branch, verification):
    title = str(task.get("title") or task["id"]).strip()
    cmd = [
        args.gh_bin,
        "pr",
        "create",
        "--title",
        title,
        "--body",
        pr_body(task, verification),
        "--base",
        base_branch,
        "--head",
        branch,
    ]
    result = run_cmd(cmd, cwd=worktree)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout or "gh pr create failed")
    url = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
    return {
        "url": url,
        "number": parse_pr_number(url),
    }


def review_agents(value):
    agents = [item.strip() for item in str(value or "").split(",") if item.strip()]
    for agent in agents:
        if not re.match(r"^[A-Za-z0-9_.-]+$", agent):
            raise RuntimeError(f"invalid review agent: {agent}")
    return agents


def review_comment_body(agent):
    return f"@{agent} please review"


def request_review_comments(args, worktree, pr, agents):
    target = str(pr["number"] or pr["url"])
    records = []
    for agent in agents:
        body = review_comment_body(agent)
        result = run_cmd([args.gh_bin, "pr", "comment", target, "--body", body], cwd=worktree)
        record = {
            "agent": agent,
            "target": target,
            "body": body,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        records.append(record)
        if result.returncode:
            raise RuntimeError(result.stderr or result.stdout or f"review request failed for {agent}")
    return records


def run_merge_gate(args, worktree, task_dir, pr, expected_head_sha, require_review_after=None):
    pr_target = pr.get("number") or pr.get("url")
    if not pr_target:
        raise RuntimeError("created PR has no number or URL for merge gate")
    cmd = [
        sys.executable,
        str(Path(args.merge_gate_script).expanduser()),
        "--pr",
        str(pr_target),
        "--repo-path",
        str(worktree),
        "--allow-merge",
        "--merge-method",
        args.merge_method,
        "--expected-head-sha",
        expected_head_sha or "",
        "--ci-timeout-seconds",
        str(args.ci_timeout_seconds),
        "--ci-poll-seconds",
        str(args.ci_poll_seconds),
        "--review-timeout-seconds",
        str(args.review_timeout_seconds),
        "--review-thread-timeout-seconds",
        str(args.review_thread_timeout_seconds),
    ]
    if require_review_after:
        cmd += ["--require-review-after", require_review_after]
    if args.delete_branch:
        cmd.append("--delete-branch")
    result = run_cmd(cmd)
    stdout_log = task_dir / "merge.stdout.log"
    stderr_log = task_dir / "merge.stderr.log"
    stdout_log.write_text(result.stdout, encoding="utf-8")
    stderr_log.write_text(result.stderr, encoding="utf-8")
    return {
        "command": cmd,
        "returncode": result.returncode,
        "stdout_log": str(stdout_log),
        "stderr_log": str(stderr_log),
    }


def write_task_artifacts(run_dir, plan_path, task):
    task_dir = run_dir / "tasks" / task["id"]
    task_dir.mkdir(parents=True, exist_ok=True)
    source_task = None
    if task.get("task_file"):
        candidate = plan_path.parent / task["task_file"]
        if candidate.exists():
            source_task = candidate
            (task_dir / "task.md").write_text(candidate.read_text(encoding="utf-8"), encoding="utf-8")
    prompt_path = task_dir / "prompt.md"
    prompt_path.write_text(build_prompt(task, plan_path, source_task), encoding="utf-8")
    return str(prompt_path)


def prepare_worktree(repo, worktree_dir, branch, base_ref, reuse, dry_run):
    if not valid_branch_name(repo, branch):
        raise RuntimeError(f"invalid branch name: {branch}")
    worktree_path = worktree_dir / sanitize_worktree_name(branch)
    exists = worktree_path.exists()
    existing_branch = branch_exists(repo, branch)
    if exists:
        if not reuse:
            raise RuntimeError(f"worktree already exists: {worktree_path}")
        actual = current_branch(worktree_path)
        if actual != branch:
            raise RuntimeError(f"stale worktree {worktree_path}: expected branch {branch}, found {actual}")
        return worktree_path, True
    if existing_branch and not reuse:
        raise RuntimeError(f"branch already exists: {branch}")
    if dry_run:
        cmd = ["git", "worktree", "add"]
        if existing_branch:
            cmd += [str(worktree_path), branch]
        else:
            cmd += ["-b", branch, str(worktree_path), base_ref]
        print("DRY-RUN:", " ".join(cmd))
        return worktree_path, False
    worktree_dir.mkdir(parents=True, exist_ok=True)
    if existing_branch:
        cmd = ["git", "worktree", "add", str(worktree_path), branch]
    else:
        cmd = ["git", "worktree", "add", "-b", branch, str(worktree_path), base_ref]
    result = run_cmd(cmd, cwd=repo)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout or "git worktree add failed")
    return worktree_path, False


def write_summary(run_dir, state):
    tasks = state.get("tasks", {})
    summary = {
        "generated_at": now_utc(),
        "repo": state.get("repo"),
        "run_dir": state.get("run_dir"),
        "implementation_plan": state.get("implementation_plan"),
        "implementation_plan_sha256": state.get("implementation_plan_sha256"),
        "dry_run": state.get("dry_run"),
        "selected_waves": state.get("selected_waves", []),
        "selected_task_ids": state.get("selected_task_ids", []),
        "totals": {
            "tasks": len(tasks),
            "by_status": status_counts(tasks),
        },
        "tasks": [
            {
                "id": task_id,
                "status": item.get("status"),
                "wave": item.get("wave"),
                "branch": item.get("branch"),
                "worktree": item.get("worktree"),
                "prompt_path": item.get("prompt_path"),
                "codex": item.get("codex"),
                "verification": item.get("verification"),
                "changed_files": item.get("changed_files"),
                "commit_sha": item.get("commit_sha"),
                "pr_url": item.get("pr_url"),
                "pr_number": item.get("pr_number"),
                "review_requested_at": item.get("review_requested_at"),
                "review_requests": item.get("review_requests"),
                "merge": item.get("merge"),
                "merged_at": item.get("merged_at"),
                "error": item.get("error"),
            }
            for task_id, item in sorted(tasks.items())
        ],
    }
    write_json(run_dir / "run-summary.json", summary)
    lines = [
        "# Implementation Wave Run Summary",
        "",
        f"Repo: {summary['repo']}",
        f"Run dir: {summary['run_dir']}",
        f"Implementation plan: {summary['implementation_plan']}",
        f"Dry run: {summary['dry_run']}",
        f"Selected waves: {summary['selected_waves']}",
        f"Selected tasks: {summary['selected_task_ids']}",
        "",
        "## Tasks",
        "",
    ]
    for item in summary["tasks"]:
        line = f"- {item['id']} (wave {item['wave']}): {item['status']} `{item['branch']}` -> {item['worktree']}"
        if item.get("error"):
            line += f"; error={item['error']}"
        lines.append(line)
    (run_dir / "run-summary.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def checkpoint_state(run_dir, state):
    state["updated_at"] = now_utc()
    write_json(run_dir / "run-state.json", state)
    write_summary(run_dir, state)


def validate_resume_state(state, repo, plan_path, plan_hash, selected_wave_numbers, selected_task_ids, dry_run):
    if state.get("repo") and Path(state["repo"]).resolve() != repo:
        raise RuntimeError(f"run-state repo mismatch: expected {repo}, got {state.get('repo')}")
    if state.get("implementation_plan") and Path(state["implementation_plan"]).resolve() != plan_path:
        raise RuntimeError(f"run-state implementation plan path mismatch: expected {plan_path}, got {state.get('implementation_plan')}")
    if state.get("implementation_plan_sha256") and state.get("implementation_plan_sha256") != plan_hash:
        raise RuntimeError("run-state implementation plan hash mismatch")
    if list(state.get("selected_waves") or []) != list(selected_wave_numbers):
        raise RuntimeError("run-state selected waves mismatch")
    if state.get("selected_task_ids") is not None and list(state.get("selected_task_ids") or []) != list(selected_task_ids):
        raise RuntimeError("run-state selected tasks mismatch")
    if bool(state.get("dry_run")) != bool(dry_run):
        raise RuntimeError("run-state dry-run mode mismatch")
    state.setdefault("selected_task_ids", selected_task_ids)
    state.setdefault("tasks", {})
    return state


def load_or_initialize_state(run_dir, repo, plan_path, plan_hash, selected_wave_numbers, selected_task_ids, dry_run, resume):
    state_path = run_dir / "run-state.json"
    if resume:
        if not state_path.exists():
            raise RuntimeError(f"run-state not found for resume: {state_path}")
        return validate_resume_state(
            load_json(state_path),
            repo,
            plan_path,
            plan_hash,
            selected_wave_numbers,
            selected_task_ids,
            dry_run,
        )
    return initial_state(repo, run_dir, plan_path, plan_hash, selected_wave_numbers, selected_task_ids, dry_run)


def initial_state(repo, run_dir, plan_path, plan_hash, selected_wave_numbers, selected_task_ids, dry_run):
    return {
        "created_at": now_utc(),
        "repo": str(repo),
        "run_dir": str(run_dir),
        "implementation_plan": str(plan_path),
        "implementation_plan_sha256": plan_hash,
        "selected_waves": selected_wave_numbers,
        "selected_task_ids": selected_task_ids,
        "dry_run": dry_run,
        "tasks": {},
    }


def validate_or_raise(plan):
    errors, warnings = validate_plan(plan)
    if warnings:
        for warning in warnings:
            print(f"warning: {warning}", file=sys.stderr)
    if errors:
        raise RuntimeError("plan invalid: " + "; ".join(errors))


def parse_args():
    parser = argparse.ArgumentParser(description="Prepare and optionally execute implementation task waves.")
    parser.add_argument("implementation_plan", nargs="?")
    parser.add_argument("--wave", type=int)
    parser.add_argument("--task", action="append", dest="task_ids", help="Prepare only the named task ID. May be repeated.")
    parser.add_argument("--run-dir")
    parser.add_argument("--runs-root", default=str(Path.home() / ".codex" / "runs" / "implementation-waves"))
    parser.add_argument("--worktree-dir", default=str(Path.home() / ".codex" / "worktrees" / "implementation"))
    parser.add_argument("--base-ref", default="HEAD")
    parser.add_argument("--max-parallel", type=int, default=1)
    parser.add_argument("--reuse-worktrees", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-codex", action="store_true", help="Run Codex for each prepared task worktree. Dry-run still only prints planned work.")
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--codex-profile")
    parser.add_argument("--codex-extra-args", default="")
    parser.add_argument("--allow-pr", action="store_true", help="After successful Codex execution, commit changed files, push the task branch, and create a PR.")
    parser.add_argument("--gh-bin", default="gh")
    parser.add_argument("--pr-base")
    parser.add_argument("--allow-review-request", action="store_true", help="After creating a PR, comment to request configured review agents.")
    parser.add_argument("--review-agents", default="codex")
    parser.add_argument("--allow-merge", action="store_true", help="After PR creation and optional review request, run the shared merge gate with merging enabled.")
    parser.add_argument("--no-merge", "--pr-only", dest="no_merge", action="store_true", help="Disable merge even when --allow-merge is also provided.")
    parser.add_argument("--merge-gate-script", default=str(default_merge_gate_script()))
    parser.add_argument("--merge-method", choices=["squash", "merge", "rebase"], default="squash")
    parser.add_argument("--delete-branch", action="store_true")
    parser.add_argument("--ci-timeout-seconds", type=int, default=600)
    parser.add_argument("--ci-poll-seconds", type=int, default=15)
    parser.add_argument("--review-timeout-seconds", type=int, default=600)
    parser.add_argument("--review-thread-timeout-seconds", type=int, default=0)
    parser.add_argument("--cleanup-artifacts", action="store_true", help="List or remove old run directories and task worktrees.")
    parser.add_argument("--cleanup-older-than-days", type=int, default=30)
    parser.add_argument("--confirm-cleanup", action="store_true", help="Required to remove artifacts when --cleanup-artifacts is used without --dry-run.")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.cleanup_artifacts:
        return cleanup_artifacts(args)
    if not args.implementation_plan:
        print("implementation_plan is required unless --cleanup-artifacts is used", file=sys.stderr)
        return 2
    if args.max_parallel <= 0:
        print("--max-parallel must be greater than zero", file=sys.stderr)
        return 2
    if args.allow_pr and not args.allow_codex:
        print("--allow-pr requires --allow-codex", file=sys.stderr)
        return 2
    if args.allow_review_request and not args.allow_pr:
        print("--allow-review-request requires --allow-pr", file=sys.stderr)
        return 2
    merge_enabled = args.allow_merge and not args.no_merge
    if merge_enabled and not args.allow_pr:
        print("--allow-merge requires --allow-pr", file=sys.stderr)
        return 2
    if args.ci_timeout_seconds < 0:
        print("--ci-timeout-seconds must be zero or greater", file=sys.stderr)
        return 2
    if args.ci_poll_seconds < 0:
        print("--ci-poll-seconds must be zero or greater", file=sys.stderr)
        return 2
    if args.review_timeout_seconds < 0:
        print("--review-timeout-seconds must be zero or greater", file=sys.stderr)
        return 2
    if args.review_thread_timeout_seconds < 0:
        print("--review-thread-timeout-seconds must be zero or greater", file=sys.stderr)
        return 2
    plan_path = Path(args.implementation_plan).resolve()
    try:
        plan = load_json(plan_path)
        validate_or_raise(plan)
        repo = repo_root(".")
        pr_base_branch = args.pr_base or current_branch(repo) or "main"
        selected = selected_waves(plan, args.wave)
        selected_wave_numbers = [int(wave["wave"]) for wave in selected]
        tasks = selected_tasks(plan, args.wave, args.task_ids)
        selected_task_ids = [task["id"] for task in tasks]
        repo_name = repo.name
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_dir = Path(args.run_dir).expanduser() if args.run_dir else Path.home() / ".codex" / "runs" / "implementation-waves" / f"{repo_name}-{stamp}"
        run_dir = run_dir.resolve()
        worktree_dir = Path(args.worktree_dir).expanduser().resolve()
        plan_hash = file_sha256(plan_path)
        state = load_or_initialize_state(
            run_dir,
            repo,
            plan_path,
            plan_hash,
            selected_wave_numbers,
            selected_task_ids,
            args.dry_run,
            args.resume,
        )
        run_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_state(run_dir, state)

        print(f"implementation_waves={selected_wave_numbers} tasks={len(tasks)} dry_run={args.dry_run}")
        for task in tasks:
            branch = task.get("branch") or f"agentic-task-{task['id'].lower()}"
            task_id = task["id"]
            previous = state.get("tasks", {}).get(task_id) or {}
            if args.allow_codex and not args.dry_run:
                if merge_enabled:
                    complete_statuses = {"merged", "no_changes"}
                elif args.allow_pr:
                    complete_statuses = {"pr_ready", "no_changes"}
                else:
                    complete_statuses = {"implemented"}
            else:
                complete_statuses = {"planned"} if args.dry_run else {"worktree_ready"}
            if args.resume and previous.get("status") in complete_statuses:
                print(f"RESUME: skipping {task_id} status {previous.get('status')}")
                continue
            prompt_path = None
            planned_worktree = worktree_dir / sanitize_worktree_name(branch)
            state["tasks"][task_id] = {
                "status": "running",
                "wave": int(task.get("wave")),
                "branch": branch,
                "worktree": str(planned_worktree),
                "prompt_path": None,
                "task_file": task.get("task_file"),
                "reused_worktree": False,
                "started_at": state["created_at"],
            }
            checkpoint_state(run_dir, state)
            try:
                prompt_path = write_task_artifacts(run_dir, plan_path, task)
                worktree_path, reused = prepare_worktree(
                    repo,
                    worktree_dir,
                    branch,
                    args.base_ref,
                    args.reuse_worktrees,
                    args.dry_run,
                )
                status = "planned" if args.dry_run else "worktree_ready"
                state["tasks"][task_id].update({
                    "status": status,
                    "worktree": str(worktree_path),
                    "prompt_path": prompt_path,
                    "reused_worktree": reused,
                    "completed_at": now_utc(),
                })
                checkpoint_state(run_dir, state)
                if args.allow_codex and not args.dry_run:
                    task_dir = run_dir / "tasks" / task_id
                    codex = run_codex_task(args, worktree_path, prompt_path, task_dir)
                    state["tasks"][task_id]["codex"] = codex
                    checkpoint_state(run_dir, state)
                    if codex["returncode"]:
                        raise RuntimeError(f"codex exited {codex['returncode']}")
                    verify = verification_results(task.get("verification_commands", []), worktree_path)
                    state["tasks"][task_id]["verification"] = verify
                    checkpoint_state(run_dir, state)
                    failed = failed_verification(verify)
                    if failed:
                        raise RuntimeError(f"verification failed: {failed['command']}")
                    files = changed_files(worktree_path)
                    state["tasks"][task_id].update({
                        "status": "implemented",
                        "changed_files": files,
                        "completed_at": now_utc(),
                    })
                    checkpoint_state(run_dir, state)
                    if args.allow_pr:
                        if not files:
                            state["tasks"][task_id].update({
                                "status": "no_changes",
                                "completed_at": now_utc(),
                            })
                            checkpoint_state(run_dir, state)
                        else:
                            commit_sha = commit_task(worktree_path, task, files)
                            push_branch(worktree_path, branch)
                            pr = create_task_pr(args, worktree_path, task, branch, pr_base_branch, verify)
                            state["tasks"][task_id].update({
                                "status": "pr_ready",
                                "commit_sha": commit_sha,
                                "pr_url": pr["url"],
                                "pr_number": pr["number"],
                                "completed_at": now_utc(),
                            })
                            checkpoint_state(run_dir, state)
                            if args.allow_review_request:
                                requests = request_review_comments(args, worktree_path, pr, review_agents(args.review_agents))
                                state["tasks"][task_id].update({
                                    "review_requested_at": now_utc(),
                                    "review_requests": requests,
                                    "completed_at": now_utc(),
                                })
                                checkpoint_state(run_dir, state)
                            if merge_enabled:
                                merge = run_merge_gate(
                                    args,
                                    worktree_path,
                                    task_dir,
                                    pr,
                                    commit_sha,
                                    state["tasks"][task_id].get("review_requested_at") if args.allow_review_request else None,
                                )
                                state["tasks"][task_id]["merge"] = merge
                                checkpoint_state(run_dir, state)
                                if merge["returncode"]:
                                    raise RuntimeError(f"merge gate exited {merge['returncode']}")
                                state["tasks"][task_id].update({
                                    "status": "merged",
                                    "merged_at": now_utc(),
                                    "completed_at": now_utc(),
                                })
                                checkpoint_state(run_dir, state)
            except Exception as exc:
                state["tasks"][task_id].update({
                    "status": "failed",
                    "prompt_path": prompt_path,
                    "error": str(exc),
                    "completed_at": now_utc(),
                })
                checkpoint_state(run_dir, state)
                raise
            prefix = "DRY-RUN: would prepare" if args.dry_run else "prepared"
            print(f"{prefix} {task_id} branch {branch} worktree {worktree_path}")
            print(f"NEXT: task prompt {prompt_path}")
            if args.allow_codex and args.dry_run:
                print(f"DRY-RUN: would run codex for {task_id}")

        print(f"run_dir={run_dir}")
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI reports exact failure.
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
