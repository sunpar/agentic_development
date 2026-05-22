#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys

PROTECTED = {"main", "master", "trunk", "develop"}


def current_branch():
    try:
        return subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True).strip()
    except Exception:
        return None


def is_strict():
    return os.environ.get("AGENTIC_DEV_STRICT_HOOKS", "0") == "1"


def warn(msg):
    print(f"[branch_hygiene] warning: {msg}", file=sys.stderr)


def fail(msg):
    print(f"[branch_hygiene] blocked: {msg}", file=sys.stderr)


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
    parser = argparse.ArgumentParser(description="Warn or block protected-branch task workflows.")
    parser.parse_args()
    read_hook_payload()

    if subprocess.call(["git", "rev-parse", "--is-inside-work-tree"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
        warn("Not inside a git repository")
        return 0

    branch = current_branch()
    if branch and branch in PROTECTED:
        msg = f"protected branch '{branch}' should not be used for destructive workflows"
        if is_strict():
            fail(msg)
            return 2
        warn(msg)

    expected = os.environ.get("AGENTIC_EXPECT_BRANCH")
    if expected and branch and expected != branch:
        msg = f"current branch '{branch}' does not match expected task branch '{expected}'"
        if is_strict():
            fail(msg)
            return 2
        warn(msg)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
