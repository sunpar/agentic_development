#!/usr/bin/env python3
import os, subprocess, sys


strict = os.environ.get('CODEBASE_REVIEW_FACTORY_STRICT') == '1'
protected = {
    b.strip()
    for b in os.environ.get('CODEBASE_REVIEW_FACTORY_PROTECTED_BRANCHES', 'main,master,develop,trunk').split(',')
    if b.strip()
}


def current_branch():
    result = subprocess.run(['git', 'branch', '--show-current'], text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if result.returncode != 0:
        return ''
    return result.stdout.strip()


branch = current_branch()
if not branch:
    print('[codebase-review-factory] protected_branch_guard: not in a git branch')
    sys.exit(0)
if branch in protected:
    print(f'[codebase-review-factory] protected_branch_guard: protected branch {branch}')
    sys.exit(1 if strict else 0)
print(f'[codebase-review-factory] protected_branch_guard: branch {branch} allowed')
sys.exit(0)
