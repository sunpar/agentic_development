#!/usr/bin/env python3
"""Convert plan.json to tasks.csv."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

COLUMNS = [
    "id",
    "epic_id",
    "wave",
    "title",
    "branch",
    "dependencies",
    "context_to_load",
    "read_set",
    "write_set",
    "verification_commands",
    "task_file",
]


def build_rows(plan):
    feature = plan.get("feature", "feature")
    tasks = plan.get("tasks", []) or []
    rows = []
    for task in tasks:
        task_id = task.get("id", "")
        task_file = task.get("task_file")
        if not task_file:
            task_file = f"docs/agent-plans/{feature}/tasks/{task_id}.md"
        rows.append({
            "id": task_id,
            "epic_id": task.get("epic_id", ""),
            "wave": task.get("wave", ""),
            "title": task.get("title", ""),
            "branch": task.get("branch", ""),
            "dependencies": ";".join(task.get("dependencies", [])),
            "context_to_load": ";".join(task.get("context_to_load", [])),
            "read_set": ";".join(task.get("read_set", [])),
            "write_set": ";".join(task.get("write_set", [])),
            "verification_commands": ";".join(task.get("verification_commands", [])),
            "task_file": task_file,
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan_path")
    parser.add_argument("--output")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    plan = json.loads(Path(args.plan_path).read_text(encoding="utf-8"))
    rows = build_rows(plan)

    if args.output and args.dry_run:
        print(f"DRY-RUN: would write CSV to {args.output}")
        writer = csv.DictWriter(sys.stdout, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    elif args.output:
        with Path(args.output).open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
    else:
        writer = csv.DictWriter(sys.stdout, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
