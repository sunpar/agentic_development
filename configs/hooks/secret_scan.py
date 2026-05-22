#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys

PATTERNS = [
    re.compile(r"(?i)\b(api[_-]?key|secret|token|password|private[_-]?key)\b\s*[:=]\s*['\"]?[^\s'\"`]{8,}"),
    re.compile(r"BEGIN\s+RSA\s+PRIVATE\s+KEY"),
    re.compile(r"-----BEGIN\s+OPENSSH\s+PRIVATE\s+KEY-----"),
]


def mask(v):
    if not v:
        return v
    return v[:2] + "***" + v[-2:]


def is_strict():
    return os.environ.get("AGENTIC_DEV_STRICT_HOOKS", "0") == "1"


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


def file_changed_paths():
    inside = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if inside.returncode != 0:
        return []
    try:
        out = subprocess.check_output(["git", "diff", "--name-only", "--cached"], text=True, stderr=subprocess.DEVNULL)
        paths = [p.strip() for p in out.splitlines() if p.strip()]
        if paths:
            return paths
        out = subprocess.check_output(["git", "diff", "--name-only"], text=True, stderr=subprocess.DEVNULL)
        return [p.strip() for p in out.splitlines() if p.strip()]
    except Exception:
        return []


def scan_file(path):
    findings = []
    if not os.path.isfile(path):
        return findings
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f, start=1):
                for p in PATTERNS:
                    m = p.search(line)
                    if m:
                        val = m.group(0).split("=", 1)[-1].strip()[:20]
                        findings.append((path, i, mask(val), p.pattern))
    except Exception:
        return findings
    return findings


def main():
    parser = argparse.ArgumentParser(description="Scan changed files for obvious secret literals.")
    parser.parse_args()
    read_hook_payload()

    findings = []
    for path in file_changed_paths():
        findings.extend(scan_file(path))

    for path, line, snippet, pattern in findings:
        print(
            f"warning: potential secret in {path}:{line} pattern={pattern} value={snippet}",
            file=sys.stderr,
        )

    if findings and is_strict():
        print(
            f"secret_scan found {len(findings)} suspicious item(s) in strict mode",
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
