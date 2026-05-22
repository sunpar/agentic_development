import argparse, csv, fnmatch, json, os, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTECTED_BRANCHES = {'main', 'master', 'develop', 'trunk'}
SAFE_BRANCH_RE = re.compile(r'^[A-Za-z0-9._/-]+$')


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def write_json(path, data, dry_run=False):
    path = Path(path)
    if dry_run:
        print(f'[dry-run] write {path}')
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def git_root(path='.'):
    p = run(['git', 'rev-parse', '--show-toplevel'], cwd=path)
    if p.returncode != 0:
        return None
    return p.stdout.strip()


def default_branch(cwd='.'):
    gh = run(['gh', 'repo', 'view', '--json', 'defaultBranchRef', '--jq', '.defaultBranchRef.name'], cwd=cwd)
    if gh.returncode == 0 and gh.stdout.strip():
        return gh.stdout.strip()
    sym = run(['git', 'symbolic-ref', '--short', 'refs/remotes/origin/HEAD'], cwd=cwd)
    if sym.returncode == 0 and sym.stdout.strip().startswith('origin/'):
        return sym.stdout.strip().split('/', 1)[1]
    return None


def required(obj, fields, prefix=''):
    errors = []
    if not isinstance(obj, dict):
        return [f'{prefix or "object"} must be object']
    for field in fields:
        if field not in obj:
            errors.append(f'{prefix + "." if prefix else ""}{field} is required')
    return errors


def slug_safe(value):
    return bool(value and SAFE_BRANCH_RE.match(value) and '..' not in value and not value.startswith('/'))


def fail_or_print(errors, json_output=False):
    if json_output:
        print(json.dumps({'valid': not errors, 'errors': errors}, indent=2))
    else:
        if errors:
            print('INVALID')
            for e in errors:
                print(f'- {e}')
        else:
            print('VALID')
    return 1 if errors else 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Shared helpers for codebase-review-factory scripts.')
    parser.parse_args()
    print('factory_common.py is a helper module; import it from other scripts.')
