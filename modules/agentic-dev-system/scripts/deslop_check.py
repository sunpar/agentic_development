#!/usr/bin/env python3
"""Detect AI slop in changed files, markdown, or PR body text."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

PATTERNS = [
    (re.compile(r"#\s*(This|The|This method|This function)\s+(does|is)"), "generic comment restating behavior"),
    (re.compile(r"for\s+extensibility|extensible\s+design", re.I), "unnecessary extensibility abstraction"),
    (re.compile(r"this is obviously|it will\s+definitely|must be\s+exactly", re.I), "fake certainty"),
    (re.compile(r"TODO\b(?!:)"), "generic TODO without owner/context"),
    (re.compile(r"manager\b|processor\b|handler\b.*wrapper", re.I), "possible needless abstraction"),
    (re.compile(r"helper\s+fn\b|function\s+tmp|utils?\w*1" , re.I), "weak helper naming"),
    (re.compile(r"duplicat(e|ed) prose|as discussed above", re.I), "duplicated prose"),
]


def get_paths_from_git():
    inside = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if inside.returncode != 0:
        return []
    changed = subprocess.check_output(["git", "diff", "--name-only"], text=True, stderr=subprocess.DEVNULL).splitlines()
    if changed:
        return [p for p in changed if p.strip()]
    status = subprocess.check_output(["git", "status", "--short"], text=True, stderr=subprocess.DEVNULL).splitlines()
    return [p[3:].strip() for p in status if p.strip()]


def scan_text(path: str, text: str):
    findings = []
    for i, line in enumerate(text.splitlines(), start=1):
        for regex, reason in PATTERNS:
            if regex.search(line):
                findings.append({
                    "file": path,
                    "line": i,
                    "reason": reason,
                    "suggested_action": f"Reword/remove line for: {reason}",
                })
    return findings


def scan_file(path: Path):
    try:
        if not path.exists() or path.is_dir():
            return []
        content = path.read_text(encoding="utf-8", errors="ignore")
        return scan_text(str(path), content)
    except Exception:
        return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--pr-body")
    parser.add_argument("--json", dest="json_path")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    findings = []
    if args.paths:
        for p in args.paths:
            findings.extend(scan_file(Path(p).expanduser()))
    else:
        for p in get_paths_from_git():
            findings.extend(scan_file(Path(p)))

    if args.pr_body:
        findings.extend(scan_text("pr-body", args.pr_body))

    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as f:
            json.dump({"count": len(findings), "findings": findings}, f, indent=2)

    if not findings:
        print("No obvious slop detected")
        return 0

    print(f"deslop findings: {len(findings)}")
    for item in findings:
        print(f"- {item['file']}:{item['line']} {item['reason']}")

    if args.strict:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
