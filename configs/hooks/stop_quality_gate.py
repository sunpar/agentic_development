#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys


def has_completion_note():
    for root, _, files in os.walk('.'):
        for name in files:
            lname = name.lower()
            if 'completion' in lname and (lname.endswith('.md') or lname.endswith('.txt')):
                return True
    return False


def has_test_keywords(text):
    keys = ["pytest", "npm test", "go test", "mvn test", "cargo test", "make test"]
    low = text.lower()
    return any(k in low for k in keys)


def has_tests_evidence():
    for summary in [".agentic-work-summary.txt", ".agentic-completion.md", "CHANGELOG.md"]:
        if os.path.exists(summary):
            try:
                with open(summary, 'r', encoding='utf-8', errors='ignore') as f:
                    if has_test_keywords(f.read()):
                        return True
            except Exception:
                pass
    return False


def has_staged_files():
    inside = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if inside.returncode != 0:
        return False
    result = subprocess.run(["git", "diff", "--name-only", "--cached"], text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if result.returncode != 0:
        return False
    return bool(result.stdout.strip())


def is_strict():
    return os.environ.get('AGENTIC_DEV_STRICT_HOOKS', '0') == '1'


def read_hook_payload():
    if sys.stdin.isatty():
        return {}
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def main():
    parser = argparse.ArgumentParser(description="Warn or block task completion without basic quality evidence.")
    parser.parse_args()
    read_hook_payload()

    issues = []
    if not has_completion_note():
        issues.append("No completion note file found")
    if not has_tests_evidence():
        issues.append("No explicit test evidence found")
    if not has_staged_files():
        issues.append("No staged task files detected")

    for issue in issues:
        print(f"[stop_quality_gate] warning: {issue}", file=sys.stderr)

    if issues and is_strict():
        print("stop_quality_gate blocked in strict mode", file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
