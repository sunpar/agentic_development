#!/usr/bin/env python3
"""Prepare and optionally execute implementation task waves."""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from validate_plan import validate_plan  # noqa: E402

MODEL_ARGS = ["--model", "gpt-5.3-codex-spark", "-c", 'model_reasoning_effort="xhigh"']
WORKTREE_CREATE_LOCK = threading.Lock()


class ReviewRequestError(RuntimeError):
    def __init__(self, message, records):
        super().__init__(message)
        self.records = records


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
    return changed_files_since(worktree)


def head_sha(worktree):
    result = run_cmd(["git", "rev-parse", "HEAD"], cwd=worktree)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout or "git rev-parse failed")
    return result.stdout.strip()


def changed_files_since(worktree, base_ref=None):
    files = []
    if base_ref:
        committed = run_cmd(["git", "diff", "--name-only", str(base_ref), "HEAD"], cwd=worktree)
        if committed.returncode:
            raise RuntimeError(committed.stderr or committed.stdout or "git diff failed")
        files.extend(committed.stdout.splitlines())
    tracked = run_cmd(["git", "diff", "--name-only", "HEAD"], cwd=worktree)
    if tracked.returncode:
        raise RuntimeError(tracked.stderr or tracked.stdout or "git diff failed")
    files.extend(tracked.stdout.splitlines())
    untracked = run_cmd(["git", "ls-files", "--others", "--exclude-standard"], cwd=worktree)
    if untracked.returncode:
        raise RuntimeError(untracked.stderr or untracked.stdout or "git ls-files failed")
    files.extend(untracked.stdout.splitlines())
    return sorted(dict.fromkeys(path for path in files if path))


def has_uncommitted_changes(worktree):
    result = run_cmd(["git", "status", "--porcelain", "--untracked-files=all"], cwd=worktree)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout or "git status failed")
    return bool(result.stdout.strip())


def commit_task(worktree, task, files, message=None):
    if not files:
        return None
    add = run_cmd(["git", "add", "-A", "--", *files], cwd=worktree)
    if add.returncode:
        raise RuntimeError(add.stderr or add.stdout or "git add failed")
    staged = run_cmd(["git", "diff", "--cached", "--quiet"], cwd=worktree)
    if staged.returncode == 0:
        return head_sha(worktree)
    if staged.returncode not in {0, 1}:
        raise RuntimeError(staged.stderr or staged.stdout or "git diff --cached failed")
    title = str(task.get("title") or task["id"]).strip()
    commit = run_cmd(["git", "commit", "-m", message or f"{task['id']}: {title}"], cwd=worktree)
    if commit.returncode:
        raise RuntimeError(commit.stderr or commit.stdout or "git commit failed")
    return head_sha(worktree)


def push_branch(worktree, branch):
    result = run_cmd(["git", "push", "-u", "origin", branch], cwd=worktree)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout or "git push failed")


def resolve_pr_base_branch(base_ref_arg, current_repo_branch, repo):
    base_ref = str(base_ref_arg or "").strip()
    if not base_ref or base_ref == "HEAD":
        return current_repo_branch or "main"
    if base_ref.startswith("origin/"):
        return base_ref.split("/", 1)[1]
    if base_ref.startswith("refs/heads/"):
        return base_ref.removeprefix("refs/heads/")
    if base_ref.startswith("refs/remotes/origin/"):
        return base_ref.removeprefix("refs/remotes/origin/")
    if run_cmd(["git", "show-ref", "--verify", f"refs/heads/{base_ref}"], cwd=repo).returncode == 0:
        return base_ref
    if run_cmd(["git", "show-ref", "--verify", f"refs/remotes/origin/{base_ref}"], cwd=repo).returncode == 0:
        return base_ref
    return current_repo_branch or "main"


def refresh_base_ref_after_wave(repo, pr_base_branch, current_base_ref):
    if not pr_base_branch:
        return current_base_ref
    fetch = run_cmd(["git", "fetch", "origin", pr_base_branch], cwd=repo)
    if fetch.returncode:
        return current_base_ref
    return f"origin/{pr_base_branch}"


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


def review_request_command(args, target, agent):
    if str(agent).lower() == "copilot":
        return [args.gh_bin, "pr", "edit", target, "--add-reviewer", "@copilot"], ""
    body = review_comment_body(agent)
    return [args.gh_bin, "pr", "comment", target, "--body", body], body


def request_review_comments(args, worktree, pr, agents):
    if not agents:
        raise RuntimeError("--review-agents must include at least one agent")
    target = str(pr["number"] or pr["url"])
    records = []
    for agent in agents:
        cmd, body = review_request_command(args, target, agent)
        result = run_cmd(cmd, cwd=worktree)
        record = {
            "agent": agent,
            "target": target,
            "body": body,
            "command": cmd,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "status": "completed" if result.returncode == 0 else "failed",
            "requested_at": now_utc() if result.returncode == 0 else None,
        }
        records.append(record)
    failed = [record for record in records if record["returncode"]]
    if failed:
        detail = failed[0]["stderr"] or failed[0]["stdout"] or f"review request failed for {failed[0]['agent']}"
        raise ReviewRequestError(detail, records)
    return records


def successful_review_request_times(records):
    return [
        record.get("requested_at")
        for record in records or []
        if isinstance(record, dict) and record.get("status") == "completed" and record.get("requested_at")
    ]


def review_requested_at_from_records(records):
    times = successful_review_request_times(records)
    return max(times) if times else None


def has_successful_review_requests(task_state):
    return bool(review_requested_at_from_records(task_state.get("review_requests")))


def task_context_updates(updates, *task_states):
    preserved_keys = ("commit_sha", "changed_files", "verification", "pr_url", "pr_number")
    merged = dict(updates)
    for key in preserved_keys:
        if key in merged:
            continue
        for task_state in task_states:
            if not isinstance(task_state, dict) or key not in task_state:
                continue
            value = task_state.get(key)
            if value is not None:
                merged[key] = value
                break
    return merged


def run_merge_gate(args, worktree, task_dir, pr, expected_head_sha, require_review_after=None, attempt=0):
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
    suffix = "" if attempt == 0 else f".attempt-{attempt + 1}"
    stdout_log = task_dir / f"merge{suffix}.stdout.log"
    stderr_log = task_dir / f"merge{suffix}.stderr.log"
    stdout_log.write_text(result.stdout, encoding="utf-8")
    stderr_log.write_text(result.stderr, encoding="utf-8")
    return {
        "command": cmd,
        "returncode": result.returncode,
        "stdout_log": str(stdout_log),
        "stderr_log": str(stderr_log),
    }


def is_review_thread_gate_failure(output):
    text = (output or "").lower()
    return "unresolved review threads" in text or "unresolved must-fix comments" in text


def parse_pr_owner_name(pr):
    url = str(pr.get("url") or "")
    match = re.search(r"github\.com[:/]+([^/]+)/([^/]+)/pull/\d+", url)
    if match:
        return match.group(1), match.group(2).removesuffix(".git")
    return None, None


def origin_owner_name(worktree):
    result = run_cmd(["git", "remote", "get-url", "origin"], cwd=worktree)
    if result.returncode:
        return None, None
    remote = result.stdout.strip()
    match = re.search(r"github\.com[:/]+([^/]+)/([^/.]+)(?:\.git)?$", remote)
    if not match:
        return None, None
    return match.group(1), match.group(2)


def gh_json_required(args, cmd, cwd):
    result = run_cmd(cmd, cwd=cwd)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout or "gh command failed")
    try:
        return json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"gh returned invalid JSON: {exc}") from exc


def active_review_threads(args, worktree, pr):
    owner, name = parse_pr_owner_name(pr)
    if not owner or not name:
        owner, name = origin_owner_name(worktree)
    if not owner or not name:
        raise RuntimeError("cannot determine GitHub owner/repo for review thread repair")
    number = pr.get("number") or parse_pr_number(pr.get("url"))
    if not number:
        raise RuntimeError("created PR has no number for review thread repair")
    query = """
query($owner:String!, $name:String!, $number:Int!, $after:String) {
  repository(owner:$owner, name:$name) {
    pullRequest(number:$number) {
      reviewThreads(first:100, after:$after) {
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          startLine
          comments(first:20) {
            nodes {
              body
              createdAt
              url
              author { login }
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
  }
}
"""
    threads = []
    after = ""
    while True:
        cmd = [
            args.gh_bin,
            "api",
            "graphql",
            "-f",
            f"owner={owner}",
            "-f",
            f"name={name}",
            "-F",
            f"number={int(number)}",
            "-f",
            "query=" + query,
        ]
        if after:
            cmd += ["-f", f"after={after}"]
        data = gh_json_required(args, cmd, cwd=worktree)
        page = (((data.get("data") or {}).get("repository") or {}).get("pullRequest") or {}).get("reviewThreads", {})
        threads.extend(page.get("nodes") or [])
        page_info = page.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            break
        after = page_info.get("endCursor") or ""
        if not after:
            raise RuntimeError("review thread pagination missing endCursor")
    return [
        thread
        for thread in threads
        if thread.get("isResolved") is False and not thread.get("isOutdated")
    ]


def resolve_review_thread(args, worktree, thread_id):
    mutation = """
mutation($threadId: ID!) {
  resolveReviewThread(input: {threadId: $threadId}) {
    thread { id isResolved }
  }
}
"""
    result = run_cmd([
        args.gh_bin,
        "api",
        "graphql",
        "-f",
        "query=" + mutation,
        "-f",
        f"threadId={thread_id}",
    ], cwd=worktree)
    return {
        "thread_id": thread_id,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def review_repair_prompt(task, plan_path, task_dir, threads_path):
    return "\n".join([
        f"Use task-implementor to address active PR review threads for {task['id']}.",
        f"Task ID: {task['id']}",
        f"Implementation plan: {plan_path}",
        f"Active review threads JSON: {threads_path}",
        f"Write repair notes/artifacts under this external artifact directory, not inside the target repo: {task_dir}",
        f"Write set: {task.get('write_set', [])}",
        f"Non-goals: {task.get('non_goals', [])}",
        f"Verification commands: {task.get('verification_commands', [])}",
        "Verify every thread against the current code.",
        "Apply only valid in-scope fixes for the task.",
        "If a thread is invalid or out of scope, write evidence in the external artifact directory and do not broaden scope.",
        "Do not create, update, or merge PRs; the orchestrator owns PR, review request, thread resolution, and merge steps.",
    ]) + "\n"


def move_legacy_task_artifacts(worktree, task_id, task_dir):
    artifact_root = Path(worktree) / "docs" / "agentic-system"
    if not artifact_root.exists():
        return []
    moved = []
    task_dir.mkdir(parents=True, exist_ok=True)
    for pattern in (f"{task_id}.*.json", f"{task_id}.*.md"):
        for artifact in sorted(artifact_root.glob(pattern)):
            target = task_dir / artifact.name
            artifact.replace(target)
            moved.append(str(target))
    for directory in [artifact_root, artifact_root.parent]:
        try:
            directory.rmdir()
        except OSError:
            pass
    return moved


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
    waves = state.get("waves", {})
    summary = {
        "generated_at": now_utc(),
        "repo": state.get("repo"),
        "run_dir": state.get("run_dir"),
        "implementation_plan": state.get("implementation_plan"),
        "implementation_plan_sha256": state.get("implementation_plan_sha256"),
        "dry_run": state.get("dry_run"),
        "execution_options": state.get("execution_options", {}),
        "selected_waves": state.get("selected_waves", []),
        "selected_task_ids": state.get("selected_task_ids", []),
        "totals": {
            "tasks": len(tasks),
            "by_status": status_counts(tasks),
        },
        "waves": [
            {
                "wave": item.get("wave", wave_id),
                "status": item.get("status"),
                "task_ids": item.get("task_ids", []),
                "started_at": item.get("started_at"),
                "completed_at": item.get("completed_at"),
                "error": item.get("error"),
            }
            for wave_id, item in sorted(
                waves.items(),
                key=lambda pair: (0, int(pair[0])) if str(pair[0]).isdigit() else (1, str(pair[0])),
            )
        ],
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
                "review_repair_attempts": item.get("review_repair_attempts"),
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
        "## Waves",
        "",
    ]
    for item in summary["waves"]:
        line = f"- Wave {item['wave']}: {item['status']} tasks={item['task_ids']}"
        if item.get("error"):
            line += f"; error={item['error']}"
        lines.append(line)
    lines += [
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


def validate_resume_state(state, repo, plan_path, plan_hash, selected_wave_numbers, selected_task_ids, dry_run, execution_opts):
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
    state["execution_options"] = merge_execution_options(state.get("execution_options"), execution_opts)
    state.setdefault("selected_task_ids", selected_task_ids)
    state.setdefault("tasks", {})
    state.setdefault("waves", {})
    return state


def merge_execution_options(saved, current):
    merged = dict(saved or {})
    for key, value in (current or {}).items():
        if isinstance(value, bool):
            merged[key] = bool(merged.get(key)) or value
        elif key not in merged or merged.get(key) in (None, "", [], {}):
            merged[key] = value
    return merged


def load_or_initialize_state(run_dir, repo, plan_path, plan_hash, selected_wave_numbers, selected_task_ids, dry_run, execution_opts, resume):
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
            execution_opts,
        )
    return initial_state(repo, run_dir, plan_path, plan_hash, selected_wave_numbers, selected_task_ids, dry_run, execution_opts)


def initial_state(repo, run_dir, plan_path, plan_hash, selected_wave_numbers, selected_task_ids, dry_run, execution_opts):
    return {
        "created_at": now_utc(),
        "repo": str(repo),
        "run_dir": str(run_dir),
        "implementation_plan": str(plan_path),
        "implementation_plan_sha256": plan_hash,
        "selected_waves": selected_wave_numbers,
        "selected_task_ids": selected_task_ids,
        "dry_run": dry_run,
        "execution_options": execution_opts,
        "waves": {},
        "tasks": {},
    }


def execution_options(args, merge_enabled):
    return {
        "allow_codex": bool(args.allow_codex),
        "codex_bin": args.codex_bin,
        "codex_profile": args.codex_profile,
        "codex_extra_args": args.codex_extra_args,
        "allow_pr": bool(args.allow_pr),
        "gh_bin": args.gh_bin,
        "pr_base": args.pr_base,
        "allow_review_request": bool(args.allow_review_request),
        "review_agents": args.review_agents,
        "allow_merge": bool(merge_enabled),
        "no_merge": bool(args.no_merge),
        "merge_gate_script": str(Path(args.merge_gate_script).expanduser()),
        "merge_method": args.merge_method,
        "ci_timeout_seconds": args.ci_timeout_seconds,
        "ci_poll_seconds": args.ci_poll_seconds,
        "review_timeout_seconds": args.review_timeout_seconds,
        "review_thread_timeout_seconds": args.review_thread_timeout_seconds,
        "max_parallel": args.max_parallel,
        "review_repair_attempts": args.review_repair_attempts,
        "resolve_review_threads": bool(args.resolve_review_threads),
        "delete_branch": bool(args.delete_branch),
        "worktree_dir": str(Path(args.worktree_dir).expanduser().resolve()),
    }


def completed_task_statuses(args, merge_enabled):
    if args.allow_codex and not args.dry_run:
        if merge_enabled:
            return {"merged", "no_changes"}
        if args.allow_pr:
            return {"pr_ready", "no_changes"}
        return {"implemented"}
    if args.dry_run:
        return {"planned"}
    return {"worktree_ready", "implemented", "pr_ready", "merged", "no_changes"}


def checkpoint_task_state(run_dir, state, state_lock, task_id, updates, replace=False):
    with state_lock:
        if replace:
            state.setdefault("tasks", {})[task_id] = updates
        else:
            state.setdefault("tasks", {}).setdefault(task_id, {}).update(updates)
        checkpoint_state(run_dir, state)
        return dict(state["tasks"][task_id])


def current_task_state(state, state_lock, task_id):
    with state_lock:
        return dict(state.get("tasks", {}).get(task_id, {}))


def checkpoint_wave_state(run_dir, state, state_lock, wave_number, updates, replace=False):
    wave_id = str(wave_number)
    with state_lock:
        if replace:
            state.setdefault("waves", {})[wave_id] = updates
        else:
            state.setdefault("waves", {}).setdefault(wave_id, {}).update(updates)
        checkpoint_state(run_dir, state)
        return dict(state["waves"][wave_id])


def run_task(task, args, repo, worktree_dir, base_ref, run_dir, plan_path, state, state_lock, pr_base_branch):
    task_id = task["id"]
    branch = task.get("branch") or f"agentic-task-{task_id.lower()}"
    prompt_path = None
    worktree_path = worktree_dir / sanitize_worktree_name(branch)
    previous = current_task_state(state, state_lock, task_id)
    resume_dirty_failed = args.resume and args.reuse_worktrees and previous.get("status") == "failed"
    checkpoint_task_state(
        run_dir,
        state,
        state_lock,
        task_id,
        {
            "status": "running",
            "id": task_id,
            "wave": int(task.get("wave")),
            "branch": branch,
            "worktree": str(worktree_path),
            "prompt_path": None,
            "task_file": task.get("task_file"),
            "reused_worktree": False,
            "started_at": now_utc(),
        },
        replace=True,
    )
    try:
        prompt_path = write_task_artifacts(run_dir, plan_path, task)
        with WORKTREE_CREATE_LOCK:
            worktree_path, reused = prepare_worktree(
                repo,
                worktree_dir,
                branch,
                base_ref,
                args.reuse_worktrees,
                args.dry_run,
            )
        base_sha = head_sha(worktree_path) if not args.dry_run else None
        status = "planned" if args.dry_run else "worktree_ready"
        checkpoint_task_state(
            run_dir,
            state,
            state_lock,
            task_id,
            {
                "status": status,
                "worktree": str(worktree_path),
                "prompt_path": prompt_path,
                "reused_worktree": reused,
                "base_sha": base_sha,
                "completed_at": now_utc(),
            },
        )
        if args.resume and args.allow_pr and previous.get("commit_sha") and not previous.get("pr_number"):
            checkpoint_task_state(
                run_dir,
                state,
                state_lock,
                task_id,
                {
                    "status": "committed",
                    "commit_sha": previous.get("commit_sha"),
                    "changed_files": previous.get("changed_files", []),
                    "verification": previous.get("verification", []),
                    "completed_at": now_utc(),
                },
            )
            push_branch(worktree_path, branch)
            pr = create_task_pr(args, worktree_path, task, branch, pr_base_branch, previous.get("verification") or [])
            updates = {
                "status": "pr_ready",
                "commit_sha": previous.get("commit_sha"),
                "changed_files": previous.get("changed_files", []),
                "verification": previous.get("verification", []),
                "pr_url": pr["url"],
                "pr_number": pr["number"],
                "completed_at": now_utc(),
            }
            if args.allow_review_request:
                try:
                    requests = request_review_comments(args, worktree_path, pr, review_agents(args.review_agents))
                except ReviewRequestError as exc:
                    checkpoint_task_state(
                        run_dir,
                        state,
                        state_lock,
                        task_id,
                        {
                            **updates,
                            "review_requests": exc.records,
                        },
                    )
                    raise
                requested_at = review_requested_at_from_records(requests)
                updates.update({
                    "review_requests": requests,
                })
                if requested_at:
                    updates["review_requested_at"] = requested_at
            checkpoint_task_state(run_dir, state, state_lock, task_id, updates)
            return current_task_state(state, state_lock, task_id)
        if args.allow_codex and not args.dry_run:
            task_dir = run_dir / "tasks" / task_id
            if resume_dirty_failed and has_uncommitted_changes(worktree_path):
                codex = {"returncode": 0, "skipped": "resumed_dirty_failed_worktree"}
            else:
                codex = run_codex_task(args, worktree_path, prompt_path, task_dir)
            checkpoint_task_state(run_dir, state, state_lock, task_id, {"codex": codex})
            if codex["returncode"]:
                raise RuntimeError(f"codex exited {codex['returncode']}")
            moved_artifacts = move_legacy_task_artifacts(worktree_path, task_id, task_dir)
            verify = verification_results(task.get("verification_commands", []), worktree_path)
            checkpoint_task_state(run_dir, state, state_lock, task_id, {"verification": verify})
            failed = failed_verification(verify)
            if failed:
                raise RuntimeError(f"verification failed: {failed['command']}")
            moved_artifacts += move_legacy_task_artifacts(worktree_path, task_id, task_dir)
            files = changed_files_since(worktree_path, base_sha)
            checkpoint_task_state(
                run_dir,
                state,
                state_lock,
                task_id,
                {
                    "status": "implemented",
                    "changed_files": files,
                    "artifacts": moved_artifacts,
                    "completed_at": now_utc(),
                },
            )
            if args.allow_pr:
                if not files:
                    checkpoint_task_state(
                        run_dir,
                        state,
                        state_lock,
                        task_id,
                        {
                            "status": "no_changes",
                            "completed_at": now_utc(),
                        },
                    )
                else:
                    commit_sha = commit_task(worktree_path, task, files) if has_uncommitted_changes(worktree_path) else head_sha(worktree_path)
                    checkpoint_task_state(
                        run_dir,
                        state,
                        state_lock,
                        task_id,
                        {
                            "status": "committed",
                            "commit_sha": commit_sha,
                            "changed_files": files,
                            "verification": verify,
                            "completed_at": now_utc(),
                        },
                    )
                    push_branch(worktree_path, branch)
                    pr = create_task_pr(args, worktree_path, task, branch, pr_base_branch, verify)
                    checkpoint_task_state(
                        run_dir,
                        state,
                        state_lock,
                        task_id,
                        {
                            "status": "pr_ready",
                            "commit_sha": commit_sha,
                            "pr_url": pr["url"],
                            "pr_number": pr["number"],
                            "completed_at": now_utc(),
                        },
                    )
                    if args.allow_review_request:
                        try:
                            requests = request_review_comments(args, worktree_path, pr, review_agents(args.review_agents))
                        except ReviewRequestError as exc:
                            checkpoint_task_state(
                                run_dir,
                                state,
                                state_lock,
                                task_id,
                                {
                                    "review_requests": exc.records,
                                    "completed_at": now_utc(),
                                },
                            )
                            raise
                        requested_at = review_requested_at_from_records(requests)
                        updates = {
                            "review_requests": requests,
                            "completed_at": now_utc(),
                        }
                        if requested_at:
                            updates["review_requested_at"] = requested_at
                        checkpoint_task_state(
                            run_dir,
                            state,
                            state_lock,
                            task_id,
                            updates,
                        )
        prefix = "DRY-RUN: would prepare" if args.dry_run else "prepared"
        print(f"{prefix} {task_id} branch {branch} worktree {worktree_path}")
        print(f"NEXT: task prompt {prompt_path}")
        if args.allow_codex and args.dry_run:
            print(f"DRY-RUN: would run codex for {task_id}")
        return current_task_state(state, state_lock, task_id)
    except Exception as exc:  # noqa: BLE001 - task state records exact failure.
        latest = current_task_state(state, state_lock, task_id)
        checkpoint_task_state(
            run_dir,
            state,
            state_lock,
            task_id,
            task_context_updates(
                {
                    "status": "failed",
                    "prompt_path": prompt_path,
                    "error": str(exc),
                    "completed_at": now_utc(),
                },
                latest,
                previous,
            ),
        )
        return current_task_state(state, state_lock, task_id)


def repair_review_threads(task, args, run_dir, state, state_lock, attempt):
    task_id = task["id"]
    task_state = current_task_state(state, state_lock, task_id)
    worktree = Path(task_state["worktree"])
    pr = {
        "url": task_state.get("pr_url"),
        "number": task_state.get("pr_number"),
    }
    task_dir = run_dir / "tasks" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    threads = active_review_threads(args, worktree, pr)
    repair_record = {
        "attempt": attempt,
        "started_at": now_utc(),
        "pr_number": pr.get("number"),
        "base_commit_sha": task_state.get("commit_sha"),
        "active_thread_count": len(threads),
    }
    if not threads:
        repair_record["status"] = "no_active_threads"
        attempts = list(task_state.get("review_repair_attempts") or [])
        attempts.append(repair_record)
        checkpoint_task_state(run_dir, state, state_lock, task_id, {"review_repair_attempts": attempts})
        return False

    threads_path = task_dir / f"review-threads-attempt-{attempt}.json"
    write_json(threads_path, {"threads": threads})
    plan_path = Path(state.get("implementation_plan") or "")
    prompt = review_repair_prompt(task, plan_path, task_dir, threads_path)
    codex = run_cmd(codex_command(args, prompt), cwd=worktree)
    (task_dir / f"review-repair-{attempt}.stdout.log").write_text(codex.stdout, encoding="utf-8")
    (task_dir / f"review-repair-{attempt}.stderr.log").write_text(codex.stderr, encoding="utf-8")
    if codex.returncode:
        raise RuntimeError(f"{task_id} review repair attempt {attempt} codex exited {codex.returncode}")

    moved_artifacts = move_legacy_task_artifacts(worktree, task_id, task_dir)
    verify = verification_results(task.get("verification_commands", []), worktree)
    write_json(task_dir / f"review-repair-{attempt}.verification.json", verify)
    failed = failed_verification(verify)
    if failed:
        raise RuntimeError(f"{task_id} review repair attempt {attempt} verification failed: {failed['command']}")
    moved_artifacts += move_legacy_task_artifacts(worktree, task_id, task_dir)
    files = changed_files_since(worktree, task_state.get("commit_sha"))

    if not files:
        remaining = active_review_threads(args, worktree, pr)
        repair_record.update({
            "status": "no_changes",
            "completed_at": now_utc(),
            "remaining_thread_count": len(remaining),
            "verification": verify,
            "artifacts": moved_artifacts,
        })
        attempts = list(current_task_state(state, state_lock, task_id).get("review_repair_attempts") or [])
        attempts.append(repair_record)
        checkpoint_task_state(run_dir, state, state_lock, task_id, {"review_repair_attempts": attempts})
        if remaining:
            raise RuntimeError(f"{task_id} review repair attempt {attempt} produced no changes with {len(remaining)} active threads remaining")
        return True

    commit_sha = commit_task(
        worktree,
        task,
        files,
        message=f"{task_id}: address review feedback",
    ) if has_uncommitted_changes(worktree) else head_sha(worktree)
    push_branch(worktree, task_state["branch"])
    active_after_repair = active_review_threads(args, worktree, pr)
    active_after_repair_ids = {thread.get("id") for thread in active_after_repair if thread.get("id")}
    resolved_threads = []
    skipped_active_threads = []
    if getattr(args, "resolve_review_threads", True):
        for thread in threads:
            thread_id = thread.get("id")
            if not thread_id:
                continue
            if thread_id in active_after_repair_ids:
                skipped_active_threads.append(thread_id)
            else:
                resolved_threads.append(resolve_review_thread(args, worktree, thread_id))
        write_json(task_dir / f"review-repair-{attempt}.resolved-threads.json", resolved_threads)
    review_requests = request_review_comments(args, worktree, pr, review_agents(args.review_agents)) if args.allow_review_request else None

    repair_record.update({
        "status": "pushed",
        "completed_at": now_utc(),
        "commit_sha": commit_sha,
        "changed_files": files,
        "verification": verify,
        "artifacts": moved_artifacts,
        "threads_path": str(threads_path),
        "active_thread_count_after_repair": len(active_after_repair),
        "skipped_active_threads": skipped_active_threads,
        "resolved_threads": resolved_threads,
        "review_requests": review_requests,
    })
    latest = current_task_state(state, state_lock, task_id)
    attempts = list(latest.get("review_repair_attempts") or [])
    attempts.append(repair_record)
    updates = {
        "status": "pr_ready",
        "commit_sha": commit_sha,
        "changed_files": files,
        "review_repair_attempts": attempts,
        "completed_at": now_utc(),
    }
    if review_requests:
        requested_at = review_requested_at_from_records(review_requests)
        updates["review_requests"] = review_requests
        if requested_at:
            updates["review_requested_at"] = requested_at
    checkpoint_task_state(run_dir, state, state_lock, task_id, updates)
    return True


def merge_ready_task(task, args, run_dir, state, state_lock):
    task_id = task["id"]
    task_state = current_task_state(state, state_lock, task_id)
    status = task_state.get("status")
    if status in {"merged", "no_changes"}:
        return task_state
    if status != "pr_ready" and not (status == "failed" and (task_state.get("pr_number") or task_state.get("pr_url"))):
        raise RuntimeError(f"{task_id} is not ready to merge; status={status}")
    task_dir = run_dir / "tasks" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    pr = {
        "url": task_state.get("pr_url"),
        "number": task_state.get("pr_number"),
    }
    try:
        max_repairs = getattr(args, "review_repair_attempts", 0)
        for attempt in range(max_repairs + 1):
            task_state = current_task_state(state, state_lock, task_id)
            if args.allow_review_request and not has_successful_review_requests(task_state):
                try:
                    requests = request_review_comments(args, Path(task_state["worktree"]), pr, review_agents(args.review_agents))
                except ReviewRequestError as exc:
                    checkpoint_task_state(
                        run_dir,
                        state,
                        state_lock,
                        task_id,
                        {
                            "review_requests": exc.records,
                            "completed_at": now_utc(),
                        },
                    )
                    raise
                requested_at = review_requested_at_from_records(requests)
                updates = {
                    "review_requests": requests,
                    "completed_at": now_utc(),
                }
                if requested_at:
                    updates["review_requested_at"] = requested_at
                task_state = checkpoint_task_state(
                    run_dir,
                    state,
                    state_lock,
                    task_id,
                    updates,
                )
            review_required_at = review_requested_at_from_records(task_state.get("review_requests"))
            if not review_required_at and not task_state.get("review_requests"):
                review_required_at = task_state.get("review_requested_at")
            merge = run_merge_gate(
                args,
                Path(task_state["worktree"]),
                task_dir,
                pr,
                task_state.get("commit_sha"),
                review_required_at,
                attempt=attempt,
            )
            checkpoint_task_state(run_dir, state, state_lock, task_id, {"merge": merge})
            if merge["returncode"] == 0:
                merged = checkpoint_task_state(
                    run_dir,
                    state,
                    state_lock,
                    task_id,
                    {
                        "status": "merged",
                        "merged_at": now_utc(),
                        "completed_at": now_utc(),
                    },
                )
                print(f"merged {task_id} existing PR {pr.get('number') or pr.get('url')}")
                return merged

            stdout = Path(merge["stdout_log"]).read_text(encoding="utf-8")
            stderr = Path(merge["stderr_log"]).read_text(encoding="utf-8")
            output = stderr or stdout
            if not is_review_thread_gate_failure(output) or attempt >= max_repairs:
                raise RuntimeError(f"merge gate failed for {task_id}: {output}")
            if not args.allow_review_request:
                raise RuntimeError(f"merge gate failed for {task_id}: review repair requires --allow-review-request: {output}")
            print(f"{task_id}: merge gate found unresolved review threads; running review repair attempt {attempt + 1}/{max_repairs}")
            repair_review_threads(task, args, run_dir, state, state_lock, attempt + 1)
        raise RuntimeError(f"merge gate failed for {task_id}: review repair attempts exhausted")
    except Exception as exc:  # noqa: BLE001 - task state records exact failure.
        checkpoint_task_state(
            run_dir,
            state,
            state_lock,
            task_id,
            {
                "status": "failed",
                "error": str(exc),
                "completed_at": now_utc(),
            },
        )
        raise


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
    parser.add_argument("--review-repair-attempts", type=int, default=2)
    parser.add_argument("--no-resolve-review-threads", dest="resolve_review_threads", action="store_false")
    parser.add_argument("--cleanup-artifacts", action="store_true", help="List or remove old run directories and task worktrees.")
    parser.add_argument("--cleanup-older-than-days", type=int, default=30)
    parser.add_argument("--confirm-cleanup", action="store_true", help="Required to remove artifacts when --cleanup-artifacts is used without --dry-run.")
    parser.set_defaults(resolve_review_threads=True)
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
    if args.review_repair_attempts < 0:
        print("--review-repair-attempts must be zero or greater", file=sys.stderr)
        return 2
    if args.allow_review_request and not review_agents(args.review_agents):
        print("--review-agents must include at least one agent", file=sys.stderr)
        return 2
    plan_path = Path(args.implementation_plan).resolve()
    try:
        plan = load_json(plan_path)
        validate_or_raise(plan)
        repo = repo_root(".")
        repo_branch = current_branch(repo)
        pr_base_branch = args.pr_base or resolve_pr_base_branch(args.base_ref, repo_branch, repo)
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
        execution_opts = execution_options(args, merge_enabled)
        state = load_or_initialize_state(
            run_dir,
            repo,
            plan_path,
            plan_hash,
            selected_wave_numbers,
            selected_task_ids,
            args.dry_run,
            execution_opts,
            args.resume,
        )
        run_dir.mkdir(parents=True, exist_ok=True)
        state_lock = threading.Lock()
        checkpoint_state(run_dir, state)

        print(f"implementation_waves={selected_wave_numbers} tasks={len(tasks)} dry_run={args.dry_run}")
        tasks_by_id = {task["id"]: task for task in tasks}
        selected_task_set = set(selected_task_ids)
        complete_statuses = completed_task_statuses(args, merge_enabled)
        base_ref = args.base_ref
        for wave in selected:
            wave_number = int(wave.get("wave"))
            wave_task_ids = [
                task_id
                for task_id in wave.get("task_ids", [])
                if task_id in selected_task_set
            ]
            if not wave_task_ids:
                continue
            print(f"wave {wave_number}: {wave_task_ids}")
            checkpoint_wave_state(
                run_dir,
                state,
                state_lock,
                wave_number,
                {
                    "status": "running",
                    "wave": wave_number,
                    "task_ids": wave_task_ids,
                    "started_at": now_utc(),
                },
                replace=True,
            )
            pending = []
            for task_id in wave_task_ids:
                previous = state.get("tasks", {}).get(task_id) or {}
                if args.resume and previous.get("status") in complete_statuses:
                    print(f"RESUME: skipping {task_id} status {previous.get('status')}")
                    continue
                if args.resume and merge_enabled and previous.get("status") in {"pr_ready", "failed"} and (previous.get("pr_number") or previous.get("pr_url")):
                    continue
                pending.append(tasks_by_id[task_id])

            results = []
            if len(pending) == 1 or args.max_parallel == 1:
                for item in pending:
                    results.append(run_task(
                        item,
                        args,
                        repo,
                        worktree_dir,
                        base_ref,
                        run_dir,
                        plan_path,
                        state,
                        state_lock,
                        pr_base_branch,
                    ))
            elif pending:
                with concurrent.futures.ThreadPoolExecutor(max_workers=min(args.max_parallel, len(pending))) as executor:
                    futures = [
                        executor.submit(
                            run_task,
                            item,
                            args,
                            repo,
                            worktree_dir,
                            base_ref,
                            run_dir,
                            plan_path,
                            state,
                            state_lock,
                            pr_base_branch,
                        )
                        for item in pending
                    ]
                    results = [future.result() for future in concurrent.futures.as_completed(futures)]

            failed = [item for item in results if item.get("status") == "failed"]
            if failed:
                error = "; ".join(f"{item.get('id', item.get('branch', 'task'))}: {item.get('error', 'unknown error')}" for item in failed)
                checkpoint_wave_state(
                    run_dir,
                    state,
                    state_lock,
                    wave_number,
                    {
                        "status": "failed",
                        "completed_at": now_utc(),
                        "error": error,
                    },
                )
                for item in failed:
                    print(f"{item.get('id', item.get('branch', 'task'))} failed: {item.get('error', 'unknown error')}", file=sys.stderr)
                raise RuntimeError(f"wave {wave_number} failed; later waves blocked")

            try:
                if merge_enabled and not args.dry_run:
                    integration_order = list(wave.get("integration_order") or [])
                    ordered_task_ids = [task_id for task_id in integration_order if task_id in wave_task_ids]
                    ordered_task_ids.extend(task_id for task_id in wave_task_ids if task_id not in ordered_task_ids)
                    for task_id in ordered_task_ids:
                        if task_id in selected_task_set:
                            merge_ready_task(tasks_by_id[task_id], args, run_dir, state, state_lock)
            except Exception as exc:
                checkpoint_wave_state(
                    run_dir,
                    state,
                    state_lock,
                    wave_number,
                    {
                        "status": "failed",
                        "completed_at": now_utc(),
                        "error": str(exc),
                    },
                )
                raise

            checkpoint_wave_state(
                run_dir,
                state,
                state_lock,
                wave_number,
                {
                    "status": "succeeded",
                    "completed_at": now_utc(),
                },
            )
            if merge_enabled and not args.dry_run:
                base_ref = refresh_base_ref_after_wave(repo, pr_base_branch, base_ref)

        print(f"run_dir={run_dir}")
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI reports exact failure.
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
