#!/usr/bin/env python3
import fnmatch, os, subprocess, sys


strict = os.environ.get('CODEBASE_REVIEW_FACTORY_STRICT') == '1'
raw_scope = os.environ.get('CODEBASE_REVIEW_FACTORY_ALLOWED_SCOPE', '')
allowed = [p.strip() for chunk in raw_scope.split(os.pathsep) for p in chunk.split(',') if p.strip()]


def changed_files():
    result = subprocess.run(['git', 'diff', '--name-only'], text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


changed = changed_files()
if not changed:
    print('[codebase-review-factory] slice_scope_guard: no changed files detected')
    sys.exit(0)
if not allowed:
    print('[codebase-review-factory] slice_scope_guard: CODEBASE_REVIEW_FACTORY_ALLOWED_SCOPE not set')
    sys.exit(1 if strict and os.environ.get('CODEBASE_REVIEW_FACTORY_REQUIRE_SCOPE') == '1' else 0)

outside = [path for path in changed if not any(fnmatch.fnmatch(path, pattern) for pattern in allowed)]
if outside:
    print('[codebase-review-factory] slice_scope_guard: files outside allowed scope:')
    for path in outside:
        print(path)
    sys.exit(1 if strict else 0)
print('[codebase-review-factory] slice_scope_guard: changed files within allowed scope')
sys.exit(0)
