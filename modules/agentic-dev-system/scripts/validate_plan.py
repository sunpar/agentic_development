#!/usr/bin/env python3
"""Validate agentic plan JSON against required schema and wave safety rules."""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import shutil
import subprocess
from pathlib import Path

REQUIRED_ROOT = {"feature", "source_documents", "assumptions", "open_questions", "epics", "tasks", "waves"}
REQUIRED_TASK = {
    "id",
    "epic_id",
    "wave",
    "title",
    "branch",
    "objective",
    "non_goals",
    "context_to_load",
    "read_set",
    "write_set",
    "dependencies",
    "parallel_conflicts",
    "implementation_steps",
    "tests_to_write_first",
    "verification_commands",
    "acceptance_criteria",
    "review_focus",
    "rollback_notes",
}
ROOT_LIST_FIELDS = {"source_documents", "assumptions", "open_questions", "epics", "tasks", "waves"}
TASK_LIST_FIELDS = {
    "non_goals",
    "context_to_load",
    "read_set",
    "write_set",
    "dependencies",
    "parallel_conflicts",
    "implementation_steps",
    "tests_to_write_first",
    "verification_commands",
    "acceptance_criteria",
    "review_focus",
}
RISKY_TOKENS = [
    "schema",
    "migration",
    "migrations",
    "public_api",
    "generated",
    "global_config",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "requirements.txt",
    "pyproject.toml",
    "poetry.lock",
    "go.mod",
    "cargo.toml",
]
PROTECTED_BRANCH_NAMES = {"main", "master", "develop", "dev", "trunk"}


def load_plan(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def coerce_int(value, label: str, errors: list[str]):
    try:
        return int(value)
    except (TypeError, ValueError):
        errors.append(f"{label} must be an integer")
        return None


def as_list(value, label: str, errors: list[str]):
    if isinstance(value, list):
        return value
    errors.append(f"{label} must be a list")
    return []


def normalize_path(value) -> str:
    text = str(value).strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text.rstrip("/") if text != "/" else text


def path_overlaps(a, b) -> bool:
    left = normalize_path(a)
    right = normalize_path(b)
    if not left or not right:
        return False
    if left == right:
        return True
    for pattern, concrete in ((left, right), (right, left)):
        if any(ch in pattern for ch in "*?["):
            if fnmatch.fnmatch(concrete, pattern):
                return True
            prefix = pattern.split("*", 1)[0].split("?", 1)[0].split("[", 1)[0]
            if prefix and concrete.startswith(prefix):
                return True
        elif concrete.startswith(pattern + "/"):
            return True
    return False


def is_valid_branch_name(branch: str) -> bool:
    if not isinstance(branch, str) or not branch.strip():
        return False
    if shutil.which("git"):
        result = subprocess.run(
            ["git", "check-ref-format", "--branch", branch],
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return result.returncode == 0
    return bool(re.match(r"^(?!/)(?!.*\.\.)(?!.*//)(?!.*@\{)(?!.*[ ~^:?*\\[]).+(?<![/.])$", branch))


def sanitized_worktree_name(branch: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "-", branch).strip("-") or "task-worktree"


def branch_namespace_conflict(left: str, right: str) -> bool:
    return left.startswith(right + "/") or right.startswith(left + "/")


def has_risky_write_set(task: dict) -> bool:
    joined = " ".join(str(item) for item in task.get("write_set", [])).lower()
    return any(token in joined for token in RISKY_TOKENS)


def validate_plan(plan):
    errors = []
    warnings = []

    missing_root = REQUIRED_ROOT.difference(plan)
    if missing_root:
        errors.append(f"missing root keys: {sorted(missing_root)}")
    for field in ROOT_LIST_FIELDS.intersection(plan):
        as_list(plan.get(field), f"root {field}", errors)

    epics = plan.get("epics") or []
    tasks = plan.get("tasks") or []
    waves = plan.get("waves") or []

    epic_ids = set()
    for e in epics:
        if not isinstance(e, dict) or not e.get("id"):
            errors.append("epic entry must include id")
        else:
            epic_ids.add(e.get("id"))

    task_map = {}
    task_wave = {}
    task_ids = set()
    branch_owner = {}
    sanitized_branch_owner = {}
    for idx, task in enumerate(tasks):
        if not isinstance(task, dict):
            errors.append(f"task index {idx} is not an object")
            continue
        tid = task.get("id")
        if tid in task_ids:
            errors.append(f"duplicate task id: {tid}")
        if tid:
            task_ids.add(tid)
            task_map[tid] = task
            task_wave[tid] = coerce_int(task.get("wave"), f"task {tid} wave", errors)
        missing = REQUIRED_TASK.difference(task)
        if missing:
            errors.append(f"task {tid or idx} missing fields: {sorted(missing)}")
        for field in TASK_LIST_FIELDS.intersection(task):
            as_list(task.get(field), f"task {tid or idx} {field}", errors)
        branch = str(task.get("branch") or "").strip()
        if "branch" in task and not is_valid_branch_name(task.get("branch")):
            errors.append(f"task {tid or idx} has invalid branch name: {task.get('branch')}")
        if branch.lower() in PROTECTED_BRANCH_NAMES:
            errors.append(f"task {tid or idx} uses protected branch name: {branch}")
        if branch:
            previous = branch_owner.get(branch)
            if previous:
                errors.append(f"duplicate task branch {branch}: {previous} and {tid or idx}")
            else:
                branch_owner[branch] = tid or idx
            sanitized = sanitized_worktree_name(branch)
            previous_sanitized = sanitized_branch_owner.get(sanitized)
            if previous_sanitized:
                errors.append(f"task branch worktree path collision {sanitized}: {previous_sanitized} and {tid or idx}")
            else:
                sanitized_branch_owner[sanitized] = tid or idx
        if task.get("merge_safe") and not str(task.get("merge_safe_reason", "")).strip():
            errors.append(f"task {tid or idx} has merge_safe=true without merge_safe_reason")
        write_set = as_list(task.get("write_set", []), f"task {tid or idx} write_set", errors)
        normalized_write_set = [normalize_path(path) for path in write_set]
        duplicates = sorted({path for path in normalized_write_set if normalized_write_set.count(path) > 1})
        if duplicates:
            errors.append(f"task {tid or idx} has duplicate write_set paths: {duplicates}")

    for task in tasks:
        if not isinstance(task, dict):
            continue
        tid = task.get("id")
        if task.get("epic_id") not in epic_ids:
            errors.append(f"task {tid} references missing epic {task.get('epic_id')}")

    for task in tasks:
        if not isinstance(task, dict):
            continue
        tid = task.get("id")
        for dep in as_list(task.get("dependencies", []), f"task {tid} dependencies", errors):
            if dep not in task_map:
                errors.append(f"task {tid} has missing dependency {dep}")

    for task in tasks:
        if not isinstance(task, dict):
            continue
        tid = task.get("id")
        current_wave = task_wave.get(tid)
        for conflict in as_list(task.get("parallel_conflicts", []), f"task {tid} parallel_conflicts", errors):
            if conflict not in task_map:
                errors.append(f"task {tid} has missing parallel_conflicts task {conflict}")
                continue
            conflict_wave = task_wave.get(conflict)
            if current_wave is not None and conflict_wave == current_wave:
                errors.append(f"task {tid} parallel_conflicts lists {conflict} in same wave {current_wave}")

    for task in tasks:
        if not isinstance(task, dict):
            continue
        tid = task.get("id")
        current_wave = task_wave.get(tid)
        for dep in as_list(task.get("dependencies", []), f"task {tid} dependencies", errors):
            dep_wave = task_wave.get(dep)
            if dep_wave is None or current_wave is None:
                continue
            if dep_wave == current_wave:
                errors.append(f"dependency {dep} -> {tid} is disallowed in same wave")
            elif dep_wave > current_wave:
                errors.append(f"dependency {dep} -> {tid} is in a later wave")

    for idx, wave in enumerate(waves):
        if not isinstance(wave, dict):
            errors.append("wave entry not object")
            continue
        wave_num = coerce_int(wave.get("wave"), f"wave entry {idx} wave", errors)
        post_wave = wave.get("post_wave_verification")
        if not isinstance(post_wave, list) or not post_wave:
            errors.append(f"wave {wave_num} post_wave_verification must be a non-empty list")
        for tid in as_list(wave.get("task_ids", []), f"wave {wave_num} task_ids", errors):
            if tid not in task_map:
                errors.append(f"wave {wave_num} references unknown task {tid}")
            elif task_wave.get(tid, None) != wave_num:
                errors.append(f"task {tid} listed in wrong wave bucket")
        integration_order = wave.get("integration_order")
        if integration_order is not None:
            order = as_list(integration_order, f"wave {wave_num} integration_order", errors)
            task_ids_for_wave = wave.get("task_ids", []) if isinstance(wave.get("task_ids"), list) else []
            if set(order) != set(task_ids_for_wave):
                errors.append(f"wave {wave_num} integration_order must match task_ids")

    branches = sorted(branch_owner)
    for index, left in enumerate(branches):
        for right in branches[index + 1:]:
            if branch_namespace_conflict(left, right):
                errors.append(
                    f"task branch namespace conflict: {branch_owner[left]} uses {left} and {branch_owner[right]} uses {right}"
                )

    wave_membership = {tid: 0 for tid in task_ids}
    for wave in waves:
        if not isinstance(wave, dict):
            continue
        for tid in as_list(wave.get("task_ids", []), f"wave {wave.get('wave')} task_ids", errors):
            if tid in wave_membership:
                wave_membership[tid] += 1
    for tid, count in wave_membership.items():
        if count != 1:
            errors.append(f"task {tid} appears in {count} wave buckets; expected exactly 1")

    for wave_num in sorted({v for v in task_wave.values() if v is not None}):
        wave_tasks = [t for t in tasks if isinstance(t, dict) and task_wave.get(t.get("id")) == wave_num]
        for i, a in enumerate(wave_tasks):
            if not isinstance(a, dict):
                continue
            ws_a = set(as_list(a.get("write_set", []), f"task {a.get('id')} write_set", errors))
            safe_a = bool(a.get("merge_safe", False))
            for b in wave_tasks[i + 1 :]:
                ws_b = set(as_list(b.get("write_set", []), f"task {b.get('id')} write_set", errors))
                overlap = ws_a.intersection(ws_b)
                if overlap and not (safe_a and b.get("merge_safe", False)):
                    errors.append(f"same-wave write conflict in wave {wave_num}: {a.get('id')} and {b.get('id')} overlap {sorted(overlap)}")
                path_overlap = sorted(
                    {
                        f"{left} <-> {right}"
                        for left in ws_a
                        for right in ws_b
                        if left != right and path_overlaps(left, right)
                    }
                )
                if path_overlap and not (safe_a and b.get("merge_safe", False)):
                    errors.append(f"same-wave path overlap in wave {wave_num}: {a.get('id')} and {b.get('id')} overlap {path_overlap}")

    for wave_num in sorted({v for v in task_wave.values() if v is not None}):
        wave_tasks = [t for t in tasks if isinstance(t, dict) and task_wave.get(t.get("id")) == wave_num]
        if len(wave_tasks) <= 1:
            continue
        for task in wave_tasks:
            if has_risky_write_set(task) and not task.get("merge_safe", False):
                errors.append(f"wave {wave_num} includes risky write set in task {task.get('id')}")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan_path")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    try:
        plan = load_plan(Path(args.plan_path))
    except Exception as exc:
        print(f"ERROR: cannot load plan: {exc}")
        return 2

    errors, warnings = validate_plan(plan)
    payload = {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "plan_feature": plan.get("feature"),
    }
    if args.as_json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"valid={payload['valid']}")
        if warnings:
            print("warnings:")
            for w in warnings:
                print(f" - {w}")
        if errors:
            print("errors:")
            for e in errors:
                print(f" - {e}")
    return 0 if payload["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
