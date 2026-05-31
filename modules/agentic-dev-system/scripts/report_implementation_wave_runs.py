#!/usr/bin/env python3
"""Aggregate implementation-wave run summaries."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shlex
from pathlib import Path

ORCHESTRATOR = Path.home() / ".codex/agentic-dev-system/scripts/orchestrate_implementation_waves.py"


def now_utc():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def status_counts(items):
    counts = {}
    for item in items:
        status = str(item.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


def sorted_task_items(mapping):
    return [
        (key, value)
        for key, value in sorted((mapping or {}).items(), key=lambda item: str(item[0]))
        if isinstance(value, dict)
    ]


def sorted_wave_items(mapping):
    return [
        (key, value)
        for key, value in sorted(
            (mapping or {}).items(),
            key=lambda item: (0, int(item[0])) if str(item[0]).isdigit() else (1, str(item[0])),
        )
        if isinstance(value, dict)
    ]


def summary_from_state(run_dir):
    state = load_json(run_dir / "run-state.json")
    waves = [
        {
            "wave": item.get("wave", wave_id),
            "status": item.get("status"),
            "task_ids": item.get("task_ids", []),
            "started_at": item.get("started_at"),
            "completed_at": item.get("completed_at"),
            "error": item.get("error"),
        }
        for wave_id, item in sorted_wave_items(state.get("waves"))
    ]
    tasks = [
        {
            "id": task_id,
            "status": item.get("status"),
            "wave": item.get("wave"),
            "branch": item.get("branch"),
            "worktree": item.get("worktree"),
            "prompt_path": item.get("prompt_path"),
            "pr_number": item.get("pr_number"),
            "pr_url": item.get("pr_url"),
            "review_requests": item.get("review_requests"),
            "review_repair_attempts": item.get("review_repair_attempts"),
            "merge": item.get("merge"),
            "merged_at": item.get("merged_at"),
            "error": item.get("error"),
        }
        for task_id, item in sorted_task_items(state.get("tasks"))
    ]
    return {
        "generated_at": state.get("updated_at") or state.get("created_at"),
        "repo": state.get("repo"),
        "run_dir": state.get("run_dir") or str(run_dir),
        "implementation_plan": state.get("implementation_plan"),
        "dry_run": bool(state.get("dry_run")),
        "execution_options": dict(state.get("execution_options") or {}),
        "selected_waves": list(state.get("selected_waves") or []),
        "selected_task_ids": list(state.get("selected_task_ids") or []),
        "totals": {
            "tasks": len(tasks),
            "by_status": status_counts(tasks),
        },
        "waves": waves,
        "tasks": tasks,
    }


def unique_sorted(values):
    return sorted({str(value) for value in values if value})


def task_by_id(tasks):
    return {
        str(item.get("id")): item
        for item in tasks
        if isinstance(item, dict) and item.get("id")
    }


def fill_missing(base, fallback, keys):
    merged = dict(base)
    for key in keys:
        if merged.get(key) in (None, "", []) or merged.get(key) == {}:
            value = fallback.get(key)
            if value not in (None, "", []) and value != {}:
                merged[key] = value
    return merged


def merge_task_details(summary_tasks, state_tasks):
    state_by_id = task_by_id(state_tasks)
    merged = []
    seen = set()
    detail_keys = (
        "wave",
        "branch",
        "worktree",
        "prompt_path",
        "pr_number",
        "pr_url",
        "review_requests",
        "review_repair_attempts",
        "merge",
        "merged_at",
        "error",
    )
    for item in summary_tasks:
        task_id = str(item.get("id") or "")
        seen.add(task_id)
        merged.append(fill_missing(item, state_by_id.get(task_id, {}), detail_keys))
    for task_id, item in state_by_id.items():
        if task_id not in seen:
            merged.append(item)
    return merged


def merge_wave_details(summary_waves, state_waves):
    if summary_waves:
        return summary_waves
    return state_waves


def enrich_summary_from_state(summary, state_summary):
    enriched = dict(summary)
    for key in ("implementation_plan", "selected_task_ids", "selected_waves", "repo", "run_dir", "execution_options"):
        if enriched.get(key) in (None, "", []):
            value = state_summary.get(key)
            if value not in (None, "", []):
                enriched[key] = value
    if enriched.get("dry_run") is None:
        enriched["dry_run"] = state_summary.get("dry_run")
    enriched["tasks"] = merge_task_details(
        [item for item in enriched.get("tasks") or [] if isinstance(item, dict)],
        [item for item in state_summary.get("tasks") or [] if isinstance(item, dict)],
    )
    enriched["waves"] = merge_wave_details(
        [item for item in enriched.get("waves") or [] if isinstance(item, dict)],
        [item for item in state_summary.get("waves") or [] if isinstance(item, dict)],
    )
    return enriched


def common_worktree_dir(tasks):
    parents = unique_sorted(str(Path(item["worktree"]).parent) for item in tasks if item.get("worktree"))
    return parents[0] if len(parents) == 1 else None


def shell_join(parts):
    return " ".join(shlex.quote(str(part)) for part in parts if part is not None and str(part) != "")


def execution_resume_args(summary):
    options = summary.get("execution_options") or {}
    args = []
    if options.get("allow_codex"):
        args.append("--allow-codex")
    if options.get("allow_pr"):
        args.append("--allow-pr")
    if options.get("allow_review_request"):
        args.append("--allow-review-request")
        if options.get("review_agents"):
            args += ["--review-agents", options.get("review_agents")]
    if options.get("allow_merge"):
        args.append("--allow-merge")
        if options.get("merge_method"):
            args += ["--merge-method", options.get("merge_method")]
        if options.get("delete_branch"):
            args.append("--delete-branch")
    if options.get("max_parallel") is not None:
        args += ["--max-parallel", options.get("max_parallel")]
    if options.get("review_repair_attempts") is not None:
        args += ["--review-repair-attempts", options.get("review_repair_attempts")]
    if options.get("resolve_review_threads") is False:
        args.append("--no-resolve-review-threads")
    if options.get("no_merge"):
        args.append("--no-merge")
    return args


def resume_commands(summary, failed_tasks, tasks):
    plan_path = summary.get("implementation_plan")
    run_dir = summary.get("run_dir")
    if not plan_path or not run_dir or not failed_tasks:
        return []
    by_id = task_by_id(tasks)
    worktree_dir = common_worktree_dir(tasks)
    commands = []
    for task_id in failed_tasks:
        task = by_id.get(task_id, {})
        cmd = [
            "python3",
            ORCHESTRATOR,
            plan_path,
            "--run-dir",
            run_dir,
        ]
        if task.get("wave") is not None:
            cmd += ["--wave", task.get("wave")]
        cmd += ["--task", task_id]
        if worktree_dir:
            cmd += ["--worktree-dir", worktree_dir]
        if summary.get("dry_run"):
            cmd.append("--dry-run")
        cmd += execution_resume_args(summary)
        cmd += ["--resume", "--reuse-worktrees"]
        commands.append(shell_join(cmd))
    return commands


def pr_numbers(tasks):
    return sorted({
        int(item["pr_number"])
        for item in tasks
        if isinstance(item, dict) and item.get("pr_number") is not None
    })


def review_request_count(tasks):
    total = 0
    for item in tasks:
        requests = item.get("review_requests")
        if isinstance(requests, list):
            total += len(requests)
    return total


def review_repair_count(tasks):
    total = 0
    for item in tasks:
        repairs = item.get("review_repair_attempts")
        if isinstance(repairs, list):
            total += len(repairs)
    return total


def merged_task_count(tasks):
    return sum(1 for item in tasks if str(item.get("status") or "") == "merged")


def merge_log_paths(tasks):
    paths = []
    for item in tasks:
        merge = item.get("merge")
        if not isinstance(merge, dict):
            continue
        paths.extend([merge.get("stderr_log"), merge.get("stdout_log")])
    return unique_sorted(paths)


def failed_wave_numbers(waves):
    failed = []
    for item in waves:
        if str(item.get("status") or "") not in {"failed", "error"}:
            continue
        wave = item.get("wave")
        if isinstance(wave, str) and wave.isdigit():
            wave = int(wave)
        failed.append(wave)
    return failed


def load_run_summary(run_dir):
    summary_path = run_dir / "run-summary.json"
    state_path = run_dir / "run-state.json"
    if summary_path.exists():
        summary = load_json(summary_path)
        source = summary_path
        if state_path.exists():
            summary = enrich_summary_from_state(summary, summary_from_state(run_dir))
    elif state_path.exists():
        summary = summary_from_state(run_dir)
        source = state_path
    else:
        return None

    tasks = [item for item in summary.get("tasks") or [] if isinstance(item, dict)]
    waves = [item for item in summary.get("waves") or [] if isinstance(item, dict)]
    failed_tasks = [
        str(item.get("id"))
        for item in tasks
        if str(item.get("status") or "") in {"failed", "error"}
    ]
    failed_waves = failed_wave_numbers(waves)
    totals = summary.get("totals") or {}
    selected_waves = list(summary.get("selected_waves") or [])
    prs = pr_numbers(tasks)
    reviews = review_request_count(tasks)
    repairs = review_repair_count(tasks)
    merges = merged_task_count(tasks)
    return {
        "name": run_dir.name,
        "run_dir": str(run_dir),
        "repo": summary.get("repo"),
        "generated_at": summary.get("generated_at"),
        "summary_source": str(source),
        "implementation_plan": summary.get("implementation_plan"),
        "dry_run": bool(summary.get("dry_run")),
        "selected_waves": selected_waves,
        "selected_task_ids": list(summary.get("selected_task_ids") or []),
        "totals": {
            "waves": len(selected_waves),
            "tasks": int(totals.get("tasks") or len(tasks)),
            "by_status": dict(totals.get("by_status") or status_counts(tasks)),
            "wave_statuses": status_counts(waves),
        },
        "waves": waves,
        "failed_waves": failed_waves,
        "failed_tasks": failed_tasks,
        "branches": unique_sorted(item.get("branch") for item in tasks),
        "worktrees": unique_sorted(item.get("worktree") for item in tasks),
        "prompt_paths": unique_sorted(item.get("prompt_path") for item in tasks),
        "pr_numbers": prs,
        "review_request_count": reviews,
        "review_repair_count": repairs,
        "merged_tasks": merges,
        "merge_log_paths": merge_log_paths(tasks),
        "resume_commands": resume_commands(summary, failed_tasks, tasks),
    }


def aggregate_runs(runs_root):
    runs_root = Path(runs_root).expanduser()
    runs = []
    if runs_root.exists():
        for child in sorted(runs_root.iterdir(), key=lambda path: path.name):
            if child.is_dir():
                summary = load_run_summary(child)
                if summary:
                    runs.append(summary)
    by_status = {}
    for run in runs:
        for status, count in run["totals"]["by_status"].items():
            by_status[status] = by_status.get(status, 0) + int(count)
    return {
        "generated_at": now_utc(),
        "runs_root": str(runs_root),
        "totals": {
            "runs": len(runs),
            "dry_runs": sum(1 for run in runs if run["dry_run"]),
            "waves": sum(run["totals"]["waves"] for run in runs),
            "tasks": sum(run["totals"]["tasks"] for run in runs),
            "prs": sum(len(run["pr_numbers"]) for run in runs),
            "review_requests": sum(run["review_request_count"] for run in runs),
            "review_repairs": sum(run["review_repair_count"] for run in runs),
            "merged_tasks": sum(run["merged_tasks"] for run in runs),
            "failed_waves": sum(len(run["failed_waves"]) for run in runs),
            "by_status": by_status,
        },
        "runs": runs,
    }


def write_markdown(path, aggregate):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Implementation Wave Run Report",
        "",
        f"Runs root: {aggregate['runs_root']}",
        "",
        "## Totals",
        "",
        f"- Runs: {aggregate['totals']['runs']}",
        f"- Dry runs: {aggregate['totals']['dry_runs']}",
        f"- Waves: {aggregate['totals']['waves']}",
        f"- Tasks: {aggregate['totals']['tasks']}",
        f"- PRs: {aggregate['totals']['prs']}",
        f"- Review requests: {aggregate['totals']['review_requests']}",
        f"- Review repairs: {aggregate['totals']['review_repairs']}",
        f"- Merged tasks: {aggregate['totals']['merged_tasks']}",
        f"- Failed waves: {aggregate['totals']['failed_waves']}",
    ]
    for status, count in sorted(aggregate["totals"]["by_status"].items()):
        lines.append(f"- {status}: {count}")
    lines += ["", "## Runs", ""]
    for run in aggregate["runs"]:
        status_text = ", ".join(
            f"{status}: {count}"
            for status, count in sorted(run["totals"]["by_status"].items())
        ) or "no tasks"
        mode = "dry-run" if run["dry_run"] else "real"
        line = f"- {run['name']}: {run['totals']['tasks']} tasks ({status_text}); {mode}"
        if run["selected_waves"]:
            line += "; waves=" + ", ".join(str(wave) for wave in run["selected_waves"])
        if run["failed_tasks"]:
            line += f"; failed={', '.join(run['failed_tasks'])}"
        if run["failed_waves"]:
            line += "; failed_waves=" + ", ".join(str(wave) for wave in run["failed_waves"])
        if run["branches"]:
            line += "; branches=" + ", ".join(run["branches"])
        if run["pr_numbers"]:
            line += "; PRs=" + ", ".join(f"#{number}" for number in run["pr_numbers"])
        if run["review_request_count"]:
            line += f"; review_requests={run['review_request_count']}"
        if run["review_repair_count"]:
            line += f"; review_repairs={run['review_repair_count']}"
        if run["merged_tasks"]:
            line += f"; merged={run['merged_tasks']}"
        lines.append(line)
        for command in run.get("resume_commands") or []:
            lines.append(f"  - Resume: `{command}`")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Aggregate implementation-wave orchestration runs.")
    parser.add_argument("--runs-root", default="~/.codex/runs/implementation-waves")
    parser.add_argument("--output-json")
    parser.add_argument("--output-md")
    args = parser.parse_args()

    aggregate = aggregate_runs(args.runs_root)
    if args.output_json:
        write_json(args.output_json, aggregate)
        print(args.output_json)
    else:
        print(json.dumps(aggregate, indent=2, sort_keys=True))
    if args.output_md:
        write_markdown(args.output_md, aggregate)
        print(args.output_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
