#!/usr/bin/env python3
import os, re, subprocess, sys
from pathlib import Path


strict = os.environ.get('CODEBASE_REVIEW_FACTORY_STRICT') == '1'
factory = Path(__file__).resolve().parents[1]
checker = factory/'scripts'/'deslop_check.py'
sys.path.insert(0, str(factory / 'scripts'))
from deslop_check import PATTERNS  # noqa: E402


def changed_files():
    env = os.environ.get('CODEBASE_REVIEW_FACTORY_SLOP_PATHS')
    if env:
        return [p for chunk in env.split(os.pathsep) for p in chunk.split(',') if p]
    result = subprocess.run(['git', 'diff', '--name-only'], text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def added_line_findings(paths):
    result = subprocess.run(
        ['git', 'diff', '--unified=0', '--', *paths],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        return []
    findings = []
    current_path = None
    current_line = None
    for line in result.stdout.splitlines():
        if line.startswith('+++ b/'):
            current_path = line.removeprefix('+++ b/')
            continue
        if line.startswith('@@'):
            match = re.search(r'\+(\d+)', line)
            current_line = int(match.group(1)) if match else None
            continue
        if line.startswith('---') or line.startswith('diff --git') or line.startswith('index '):
            continue
        if line.startswith('+') and current_path:
            text = line[1:]
            line_no = current_line or 0
            for name, rx in PATTERNS:
                if rx.search(text):
                    findings.append((current_path, line_no, name, text.strip()))
            if current_line is not None:
                current_line += 1
        elif current_line is not None and not line.startswith('-'):
            current_line += 1
    return findings


paths = changed_files()
if not paths:
    print('[codebase-review-factory] slop_guard: no changed files detected')
    sys.exit(0)
if not os.environ.get('CODEBASE_REVIEW_FACTORY_SLOP_PATHS'):
    findings = added_line_findings(paths)
    for path, line, name, text in findings:
        print(f'{path}:{line} {name} {text}')
    sys.exit(1 if strict and findings else 0)
cmd = [sys.executable, str(checker), *paths]
if strict:
    cmd.append('--strict')
sys.exit(subprocess.run(cmd).returncode)
