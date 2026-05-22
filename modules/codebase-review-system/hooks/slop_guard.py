#!/usr/bin/env python3
import os, subprocess, sys
from pathlib import Path


strict = os.environ.get('CODEBASE_REVIEW_FACTORY_STRICT') == '1'
factory = Path(__file__).resolve().parents[1]
checker = factory/'scripts'/'deslop_check.py'


def changed_files():
    env = os.environ.get('CODEBASE_REVIEW_FACTORY_SLOP_PATHS')
    if env:
        return [p for chunk in env.split(os.pathsep) for p in chunk.split(',') if p]
    result = subprocess.run(['git', 'diff', '--name-only'], text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


paths = changed_files()
if not paths:
    print('[codebase-review-factory] slop_guard: no changed files detected')
    sys.exit(0)
cmd = [sys.executable, str(checker), *paths]
if strict:
    cmd.append('--strict')
sys.exit(subprocess.run(cmd).returncode)
