#!/usr/bin/env python3
"""Prepare implementation task waves without running Codex or PR automation."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from validate_plan import validate_plan  # noqa: E402


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
    parser = argparse.ArgumentParser(description="Prepare implementation task waves.")
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
    plan_path = Path(args.implementation_plan).resolve()
    try:
        plan = load_json(plan_path)
        validate_or_raise(plan)
        repo = repo_root(".")
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
            if args.resume and previous.get("status") in {"planned", "worktree_ready"}:
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

        print(f"run_dir={run_dir}")
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI reports exact failure.
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
