#!/usr/bin/env python3
"""Execute codebase review/refactor slices wave-by-wave."""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as _dt
import fnmatch
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from validate_slice_plan import validate as validate_slice_plan  # noqa: E402


MODEL_ARGS = ['--model', 'gpt-5.3-codex-spark', '-c', 'model_reasoning_effort="xhigh"']
RISKY_PARALLEL_PATTERNS = [
    '*lock*',
    'package.json',
    'package-lock.json',
    'pnpm-lock.yaml',
    'yarn.lock',
    'pyproject.toml',
    'requirements*.txt',
    '.github/**',
    '**/migrations/**',
    '**/schema*',
    '**/schemas/**',
    '**/route*',
    '**/router*',
    '**/fixtures/**',
    '**/generated/**',
    '**/config*',
]


def now_utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def run_cmd(cmd, cwd=None, timeout=None):
    return subprocess.run(
        cmd,
        cwd=cwd,
        timeout=timeout,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def worktree_shell_env(cwd: Path):
    env = os.environ.copy()
    root = Path(cwd)
    env['VIRTUAL_ENV'] = str(root / '.venv')
    env['PATH'] = os.pathsep.join([
        str(root / '.venv' / 'bin'),
        str(root / 'frontend' / 'node_modules' / '.bin'),
        env.get('PATH', ''),
    ])
    return env


def run_shell(command: str, cwd: Path):
    return subprocess.run(
        command,
        cwd=cwd,
        env=worktree_shell_env(cwd),
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def load_waves(path):
    data = load_json(path)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        waves = data.get('waves', [])
        if not isinstance(waves, list):
            raise SystemExit('waves must be a list')
        return waves
    raise SystemExit('waves file must be a JSON object with waves or a JSON list')


def safe_extra_args(value):
    args = shlex.split(value) if value else []
    banned = {'--model', '-m', '--sandbox', '-s', '--dangerously-bypass-approvals-and-sandbox', '--dangerously-bypass-hook-trust'}
    for i, arg in enumerate(args):
        if arg in banned or arg.startswith('--model=') or arg.startswith('--sandbox='):
            raise SystemExit(f'unsafe --codex-extra-args token blocked: {arg}')
        if arg in {'-c', '--config'}:
            nxt = args[i + 1] if i + 1 < len(args) else ''
            if any(k in nxt for k in ['model', 'model_reasoning_effort', 'sandbox', 'danger']):
                raise SystemExit(f'unsafe --codex-extra-args config blocked: {nxt}')
    return args


def repo_root(cwd='.'):
    result = run_cmd(['git', 'rev-parse', '--show-toplevel'], cwd=cwd)
    if result.returncode:
        raise RuntimeError('not inside a git repository')
    return Path(result.stdout.strip()).resolve()


def current_branch(cwd):
    result = run_cmd(['git', 'branch', '--show-current'], cwd=cwd)
    return result.stdout.strip() if result.returncode == 0 else ''


def default_branch(cwd):
    sym = run_cmd(['git', 'symbolic-ref', '--short', 'refs/remotes/origin/HEAD'], cwd=cwd)
    if sym.returncode == 0 and sym.stdout.strip().startswith('origin/'):
        return sym.stdout.strip().split('/', 1)[1]
    branch = current_branch(cwd)
    return branch or 'main'


def command_exists(name):
    return shutil.which(name) is not None


def path_executables(name):
    seen = set()
    candidates = []
    for directory in os.environ.get('PATH', '').split(os.pathsep):
        if not directory:
            continue
        candidate = Path(directory) / name
        if str(candidate) in seen:
            continue
        seen.add(str(candidate))
        if candidate.is_file() and os.access(candidate, os.X_OK):
            candidates.append(candidate)
    return candidates


def resolve_codex_binary(explicit=None):
    candidates = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    else:
        candidates.extend(path_executables('codex'))
        app_binary = Path('/Applications/Codex.app/Contents/Resources/codex')
        if app_binary not in candidates:
            candidates.append(app_binary)

    failures = []
    for candidate in candidates:
        result = run_cmd([str(candidate), '--version'], timeout=15)
        if result.returncode == 0:
            return str(candidate.resolve())
        failures.append(f'{candidate}: {(result.stderr or result.stdout or "failed").strip()}')
        if explicit:
            break
    detail = '; '.join(failures) if failures else 'no codex executable found on PATH'
    raise RuntimeError('no working codex binary found: ' + detail)


def gh_auth_ok(cwd):
    return run_cmd(['gh', 'auth', 'status'], cwd=cwd).returncode == 0


def sanitize_worktree_name(branch):
    return re.sub(r'[^a-zA-Z0-9_.-]', '-', branch).strip('-') or 'slice-worktree'


def branch_exists(branch, cwd):
    return run_cmd(['git', 'show-ref', '--verify', f'refs/heads/{branch}'], cwd=cwd).returncode == 0


def valid_branch_name(branch, cwd):
    return run_cmd(['git', 'check-ref-format', '--branch', branch], cwd=cwd).returncode == 0


def rev_parse(cwd, rev):
    result = run_cmd(['git', 'rev-parse', '--verify', rev], cwd=cwd)
    if result.returncode:
        raise RuntimeError(result.stderr or f'git rev-parse failed for {rev}')
    return result.stdout.strip()


def file_sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def origin_url(cwd):
    result = run_cmd(['git', 'remote', 'get-url', 'origin'], cwd=cwd)
    return result.stdout.strip() if result.returncode == 0 else ''


def slice_branch_map(plan):
    branches = {}
    for item in plan.get('slices', []):
        if isinstance(item, dict) and item.get('id'):
            sid = item['id']
            branches[sid] = item.get('branch') or f'codebase-review/{sid.lower()}'
    return branches


def parse_status_paths(output):
    paths = []
    for line in output.splitlines():
        if not line:
            continue
        path = line[3:]
        if ' -> ' in path:
            before, after = path.split(' -> ', 1)
            paths.append(before.strip('"'))
            path = after
        paths.append(path.strip('"'))
    return paths


def changed_paths(cwd):
    result = run_cmd(['git', 'status', '--porcelain=v1', '-z'], cwd=cwd)
    if result.returncode:
        raise RuntimeError(result.stderr or 'git status failed')
    entries = result.stdout.split('\0')
    paths = []
    idx = 0
    while idx < len(entries):
        entry = entries[idx]
        if not entry:
            idx += 1
            continue
        status = entry[:2]
        path = entry[3:]
        if path:
            paths.append(path)
        if status[0] in {'R', 'C'} or status[1] in {'R', 'C'}:
            idx += 1
            if idx < len(entries) and entries[idx]:
                paths.append(entries[idx])
        idx += 1
    return list(dict.fromkeys(paths))


def path_allowed(path, patterns):
    path = path.replace('\\', '/')
    for pattern in patterns:
        p = pattern.replace('\\', '/')
        if path == p or fnmatch.fnmatch(path, p):
            return True
        if p.endswith('/**') and path.startswith(p[:-3].rstrip('/') + '/'):
            return True
    return False


def risky_parallel_path(path):
    return any(path_allowed(path, [pattern]) for pattern in RISKY_PARALLEL_PATTERNS)


def validate_parallel_rules(waves, by_id):
    errors = []
    for wave in waves:
        slice_ids = wave.get('slice_ids', [])
        rationale = str(wave.get('parallel_safety_rationale', '')).strip()
        if not rationale:
            errors.append(f'wave {wave.get("wave")} parallel_safety_rationale required')
        if len(slice_ids) <= 1:
            continue
        rationale_lower = rationale.lower()
        for sid in slice_ids:
            if sid not in by_id:
                continue
            for path in by_id[sid].get('files_allowed_to_edit', []):
                if risky_parallel_path(path) and 'merge-safe' not in rationale_lower:
                    errors.append(f'wave {wave.get("wave")} risky parallel path requires explicit merge-safe rationale: {sid} {path}')
    return errors


def validate_selected_plan(plan, waves):
    combined = dict(plan)
    combined['waves'] = waves
    errors = validate_slice_plan(combined)
    by_id = {s['id']: s for s in plan.get('slices', []) if isinstance(s, dict) and s.get('id')}
    errors += validate_parallel_rules(waves, by_id)
    return errors, by_id


def allowed_dirty(path, repo, slice_plan, waves_path):
    rel = path.replace('\\', '/')
    allowed = ['docs/agentic-system/**']
    for candidate in [slice_plan, waves_path]:
        try:
            resolved = Path(candidate).resolve()
            if resolved.is_relative_to(repo):
                allowed.append(str(resolved.relative_to(repo)).replace('\\', '/'))
        except AttributeError:
            resolved = Path(candidate).resolve()
            try:
                rel_candidate = str(resolved.relative_to(repo)).replace('\\', '/')
            except ValueError:
                continue
            allowed.append(rel_candidate)
        except ValueError:
            continue
    return path_allowed(rel, allowed)


def ensure_clean_or_orchestration_only(repo, slice_plan, waves_path):
    dirty = changed_paths(repo)
    bad = [p for p in dirty if not allowed_dirty(p, repo, slice_plan, waves_path)]
    if bad:
        raise RuntimeError('unrelated dirty changes before orchestration: ' + ', '.join(bad))


def create_or_reuse_worktree(
    repo,
    worktree_dir,
    branch,
    base_ref,
    reuse,
    allowed=None,
    allow_scoped_dirty=False,
    slice_id=None,
    slice_dir=None,
    reset_stale_clean=False,
):
    if not valid_branch_name(branch, repo):
        raise RuntimeError(f'invalid branch name: {branch}')
    worktree_dir.mkdir(parents=True, exist_ok=True)
    path = worktree_dir / sanitize_worktree_name(branch)
    exists = path.exists()
    existing_branch = branch_exists(branch, repo)
    if exists:
        if not reuse:
            raise RuntimeError(f'worktree already exists: {path}')
        actual = current_branch(path)
        if actual != branch:
            raise RuntimeError(f'stale worktree {path}: expected branch {branch}, found {actual}')
        if slice_id and slice_dir:
            move_legacy_slice_artifacts(path, slice_id, slice_dir)
        dirty = changed_paths(path)
        if dirty:
            if not allow_scoped_dirty:
                raise RuntimeError(f'reused worktree is not clean: {path}: {", ".join(dirty)}')
            outside = [changed for changed in dirty if not path_allowed(changed, allowed or [])]
            if outside:
                raise RuntimeError(f'reused worktree has out-of-scope dirty changes: {path}: {", ".join(outside)}')
        ancestor = run_cmd(['git', 'merge-base', '--is-ancestor', base_ref, 'HEAD'], cwd=path)
        reset_info = None
        if ancestor.returncode:
            if not reset_stale_clean or dirty:
                raise RuntimeError(f'reused worktree is not based on {base_ref}: {path}')
            old_head = rev_parse(path, 'HEAD')
            new_base = rev_parse(path, base_ref)
            reset = run_cmd(['git', 'reset', '--hard', base_ref], cwd=path)
            if reset.returncode:
                raise RuntimeError(reset.stderr or reset.stdout or f'git reset --hard {base_ref} failed')
            reset_info = {
                'old_head': old_head,
                'new_head': new_base,
                'base_ref': base_ref,
                'reason': 'clean reused worktree was behind or had squash-merged prior-wave history',
            }
        return path, bool(dirty), reset_info
    if existing_branch and not reuse:
        raise RuntimeError(f'branch already exists: {branch}')
    if existing_branch:
        cmd = ['git', 'worktree', 'add', str(path), branch]
    else:
        cmd = ['git', 'worktree', 'add', '-b', branch, str(path), base_ref]
    result = run_cmd(cmd, cwd=repo)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout or 'git worktree add failed')
    reset_info = None
    if existing_branch:
        ancestor = run_cmd(['git', 'merge-base', '--is-ancestor', base_ref, 'HEAD'], cwd=path)
        if ancestor.returncode:
            if not reset_stale_clean:
                raise RuntimeError(f'reused branch is not based on {base_ref}: {branch}')
            old_head = rev_parse(path, 'HEAD')
            new_base = rev_parse(path, base_ref)
            reset = run_cmd(['git', 'reset', '--hard', base_ref], cwd=path)
            if reset.returncode:
                raise RuntimeError(reset.stderr or reset.stdout or f'git reset --hard {base_ref} failed')
            reset_info = {
                'old_head': old_head,
                'new_head': new_base,
                'base_ref': base_ref,
                'reason': 'clean reused branch was behind or had squash-merged prior-wave history',
            }
    return path, False, reset_info


def state_initial(repo, run_dir, slice_plan, waves_path, plan_hash, waves_hash, branches, remote_url):
    return {
        'created_at': now_utc(),
        'repo': str(repo),
        'repo_remote_url': remote_url,
        'run_dir': str(run_dir),
        'slice_plan': str(slice_plan),
        'waves_path': str(waves_path),
        'slice_plan_sha256': plan_hash,
        'waves_sha256': waves_hash,
        'slice_branches': branches,
        'waves': {},
        'slices': {},
    }


def validate_or_migrate_state(state, run_dir, repo, slice_plan, waves_path, plan_hash, waves_hash, branches, remote_url):
    required_binding_keys = {
        'repo_remote_url',
        'slice_plan_sha256',
        'waves_sha256',
        'slice_branches',
    }
    has_saved_progress = any(
        isinstance(item, dict) and item.get('status') in {'succeeded', 'no_changes', 'pr_ready', 'merged', 'running', 'failed'}
        for item in (state.get('slices') or {}).values()
    )
    if has_saved_progress:
        missing = sorted(key for key in required_binding_keys if key not in state)
        if missing:
            raise RuntimeError('run-state is missing binding metadata: ' + ', '.join(missing))
    if state.get('repo') and Path(state['repo']).resolve() != repo:
        raise RuntimeError(f'run-state repo mismatch: expected {repo}, got {state.get("repo")}')
    if state.get('slice_plan') and Path(state['slice_plan']).resolve() != slice_plan:
        raise RuntimeError(f'run-state slice plan path mismatch: expected {slice_plan}, got {state.get("slice_plan")}')
    if state.get('waves_path') and Path(state['waves_path']).resolve() != waves_path:
        raise RuntimeError(f'run-state waves path mismatch: expected {waves_path}, got {state.get("waves_path")}')
    if state.get('repo_remote_url') is not None and state.get('repo_remote_url') != remote_url:
        raise RuntimeError('run-state repo remote mismatch')
    if state.get('slice_plan_sha256') is not None and state.get('slice_plan_sha256') != plan_hash:
        raise RuntimeError('run-state slice plan hash mismatch')
    if state.get('waves_sha256') is not None and state.get('waves_sha256') != waves_hash:
        raise RuntimeError('run-state waves hash mismatch')
    if state.get('slice_branches') is not None and state.get('slice_branches') != branches:
        raise RuntimeError('run-state slice branch map mismatch')

    state.setdefault('repo', str(repo))
    state.setdefault('repo_remote_url', remote_url)
    state.setdefault('run_dir', str(run_dir))
    state.setdefault('slice_plan', str(slice_plan))
    state.setdefault('waves_path', str(waves_path))
    state.setdefault('slice_plan_sha256', plan_hash)
    state.setdefault('waves_sha256', waves_hash)
    state.setdefault('slice_branches', branches)
    state.setdefault('waves', {})
    state.setdefault('slices', {})
    return state


def load_state(run_dir, repo, slice_plan, waves_path, resume, plan_hash, waves_hash, branches, remote_url):
    state_path = run_dir / 'run-state.json'
    if resume and state_path.exists():
        state = load_json(state_path)
        return validate_or_migrate_state(state, run_dir, repo, slice_plan, waves_path, plan_hash, waves_hash, branches, remote_url)
    return state_initial(repo, run_dir, slice_plan, waves_path, plan_hash, waves_hash, branches, remote_url)


def build_prompt(slice_item, plan_copy, artifact_dir):
    return '\n'.join([
        f'Use slice-review-workflow and slice-refactor-workflow for {slice_item["id"]}.',
        f'Slice ID: {slice_item["id"]}',
        f'Slice plan copy: {plan_copy}',
        f'Write review/refactor result artifacts under this external artifact directory, not inside the target repo: {artifact_dir}',
        f'Allowed edit scope: {slice_item.get("files_allowed_to_edit", [])}',
        f'Files not allowed to edit: {slice_item.get("files_not_allowed_to_edit", [])}',
        f'Verification commands: {slice_item.get("verification_commands", [])}',
        'Apply only in-scope behavior-preserving findings.',
        'Do not create, update, or merge PRs; the orchestrator owns PR and merge steps.',
    ])


def codex_command(args, prompt, writable_dirs=None):
    cmd = [args.codex_bin, 'exec'] + MODEL_ARGS
    if args.codex_profile:
        cmd += ['--profile', args.codex_profile]
    cmd += safe_extra_args(args.codex_extra_args)
    for directory in writable_dirs or []:
        cmd += ['--add-dir', str(Path(directory).resolve())]
    cmd.append(prompt)
    return cmd


def verification_results(commands, cwd):
    results = []
    for command in commands:
        result = run_shell(command, cwd)
        results.append({
            'command': command,
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
        })
        if result.returncode:
            break
    return results


def setup_results(commands, cwd):
    return verification_results(commands, cwd)


def fail_on_verification(results):
    return next((r for r in results if r['returncode'] != 0), None)


def commit_slice(worktree, slice_item, files):
    diff_check = run_cmd(['git', 'diff', '--check'], cwd=worktree)
    if diff_check.returncode:
        raise RuntimeError(diff_check.stderr or diff_check.stdout or 'git diff --check failed')
    add = run_cmd(['git', 'add', '--'] + files, cwd=worktree)
    if add.returncode:
        raise RuntimeError(add.stderr or add.stdout or 'git add failed')
    commit = run_cmd(['git', 'commit', '-m', f'{slice_item["id"]}: review/refactor slice'], cwd=worktree)
    if commit.returncode:
        raise RuntimeError(commit.stderr or commit.stdout or 'git commit failed')
    head = run_cmd(['git', 'rev-parse', 'HEAD'], cwd=worktree)
    if head.returncode:
        raise RuntimeError(head.stderr or 'git rev-parse HEAD failed')
    return head.stdout.strip()


def gh_json(cmd, cwd):
    result = run_cmd(cmd, cwd=cwd)
    if result.returncode:
        return None
    try:
        return json.loads(result.stdout or '{}')
    except json.JSONDecodeError:
        return None


def pr_marker(slice_id):
    return f'Slice-ID: {slice_id}'


def create_or_reuse_pr(worktree, slice_item, pr_base_branch):
    branch = slice_item['branch']
    fields = 'number,headRefName,baseRefName,headRefOid,body,state'
    existing = gh_json(['gh', 'pr', 'view', branch, '--json', fields], cwd=worktree)
    if existing:
        body = existing.get('body') or ''
        if existing.get('headRefName') != branch:
            raise RuntimeError(f'existing PR head does not match branch {branch}')
        if existing.get('baseRefName') != pr_base_branch:
            raise RuntimeError(f'existing PR base does not match {pr_base_branch}')
        if pr_marker(slice_item['id']) not in body:
            raise RuntimeError(f'existing PR for {branch} lacks slice marker {pr_marker(slice_item["id"])}')
        return existing.get('number')

    body = '\n'.join([
        'Slice-scoped codebase review/refactor update.',
        '',
        pr_marker(slice_item['id']),
    ])
    result = run_cmd([
        'gh', 'pr', 'create',
        '--base', pr_base_branch,
        '--head', branch,
        '--title', slice_item.get('pr_title') or f'[codebase-review] {slice_item["id"]}',
        '--body', body,
    ], cwd=worktree)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout or 'gh pr create failed')
    created = gh_json(['gh', 'pr', 'view', branch, '--json', fields], cwd=worktree)
    if not created or not created.get('number'):
        raise RuntimeError('gh pr create succeeded but PR number could not be resolved')
    return created.get('number')


def request_review(worktree, pr_number, slice_item):
    focus = ', '.join(slice_item.get('review_focus', [])) or 'correctness, tests, API compatibility, slice scope'
    body = f'@codex review\n\nSlice: {slice_item["id"]}\nFocus: {focus}'
    requested_at = now_utc()
    result = run_cmd(['gh', 'pr', 'comment', str(pr_number), '--body', body], cwd=worktree)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout or 'gh pr comment failed')
    return requested_at


def push_branch(worktree):
    result = run_cmd(['git', 'push', '-u', 'origin', 'HEAD'], cwd=worktree)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout or 'git push failed')


def changed_files_in_scope(worktree, allowed):
    files = changed_paths(worktree)
    outside = [path for path in files if not path_allowed(path, allowed)]
    if outside:
        raise RuntimeError('outside scope changes: ' + ', '.join(outside))
    return files


def move_legacy_slice_artifacts(worktree, slice_id, slice_dir):
    artifact_root = Path(worktree) / 'docs' / 'agentic-system'
    if not artifact_root.exists():
        return []
    moved = []
    for artifact in sorted(artifact_root.glob(f'{slice_id}.*.json')):
        target = slice_dir / artifact.name
        target.parent.mkdir(parents=True, exist_ok=True)
        artifact.replace(target)
        moved.append(str(target))
    for directory in [artifact_root, artifact_root.parent]:
        try:
            directory.rmdir()
        except OSError:
            pass
    return moved


def run_slice(slice_item, args, repo, worktree_dir, base_ref, run_dir, plan_copy, state, state_lock, pr_base_branch):
    sid = slice_item['id']
    branch = slice_item.get('branch') or f'codebase-review/{sid.lower()}'
    slice_dir = run_dir / 'slices' / sid
    slice_dir.mkdir(parents=True, exist_ok=True)
    previous = state.get('slices', {}).get(sid, {})
    allow_dirty_resume = args.resume and args.reuse_worktrees and previous.get('status') == 'failed'
    allow_stale_clean_reset = (
        args.resume
        and args.reuse_worktrees
        and previous.get('status') in {'failed', 'running'}
        and not previous.get('pr_number')
        and not previous.get('changed_files')
        and not previous.get('head_sha')
    )
    with state_lock:
        state['slices'][sid] = {
            'status': 'running',
            'slice_id': sid,
            'started_at': now_utc(),
            'branch': branch,
            'base_ref': base_ref,
        }
        write_json(run_dir / 'run-state.json', state)

    try:
        worktree, resumed_dirty, reset_info = create_or_reuse_worktree(
            repo,
            worktree_dir,
            branch,
            base_ref,
            args.reuse_worktrees,
            allowed=slice_item.get('files_allowed_to_edit', []),
            allow_scoped_dirty=allow_dirty_resume,
            slice_id=sid,
            slice_dir=slice_dir,
            reset_stale_clean=allow_stale_clean_reset,
        )
        base_sha = run_cmd(['git', 'rev-parse', 'HEAD'], cwd=worktree).stdout.strip()
        setup = setup_results(args.setup_command, worktree)
        write_json(slice_dir / 'setup.json', setup)
        failed_setup = fail_on_verification(setup)
        if failed_setup:
            raise RuntimeError(f'setup failed: {failed_setup["command"]}')

        if not resumed_dirty:
            prompt = build_prompt(slice_item, plan_copy, slice_dir)
            cmd = codex_command(args, prompt, writable_dirs=[run_dir])
            codex = run_cmd(cmd, cwd=worktree)
            (slice_dir / 'codex.stdout.log').write_text(codex.stdout, encoding='utf-8')
            (slice_dir / 'codex.stderr.log').write_text(codex.stderr, encoding='utf-8')
            if codex.returncode:
                raise RuntimeError(f'codex exited {codex.returncode}')

        moved_artifacts = move_legacy_slice_artifacts(worktree, sid, slice_dir)
        changed_files_in_scope(worktree, slice_item.get('files_allowed_to_edit', []))
        verify = verification_results(slice_item.get('verification_commands', []), worktree)
        write_json(slice_dir / 'verification.json', verify)
        failed = fail_on_verification(verify)
        if failed:
            raise RuntimeError(f'verification failed: {failed["command"]}')
        moved_artifacts += move_legacy_slice_artifacts(worktree, sid, slice_dir)
        files = changed_files_in_scope(worktree, slice_item.get('files_allowed_to_edit', []))

        review_requested_at = None
        if not files:
            status = 'no_changes'
            head_sha = base_sha
            pr_number = None
        else:
            if args.allow_pr:
                head_sha = commit_slice(worktree, slice_item, files)
                push_branch(worktree)
                pr_number = create_or_reuse_pr(worktree, slice_item, pr_base_branch)
                if args.allow_review_request:
                    review_requested_at = request_review(worktree, pr_number, slice_item)
                status = 'pr_ready'
            else:
                head = run_cmd(['git', 'rev-parse', 'HEAD'], cwd=worktree)
                head_sha = head.stdout.strip() if head.returncode == 0 else ''
                pr_number = None
                status = 'succeeded'

        result = {
            'status': status,
            'slice_id': sid,
            'completed_at': now_utc(),
            'branch': branch,
            'worktree': str(worktree),
            'base_sha': base_sha,
            'head_sha': head_sha,
            'changed_files': files,
            'pr_number': pr_number,
            'setup': setup,
            'verification': verify,
            'artifacts': moved_artifacts,
            'resumed_from_dirty_worktree': resumed_dirty,
            'reused_stale_worktree_reset': reset_info,
        }
        if review_requested_at:
            result['review_requested_at'] = review_requested_at
        with state_lock:
            state['slices'][sid] = result
            write_json(run_dir / 'run-state.json', state)
        return result
    except Exception as exc:  # noqa: BLE001 - CLI records exact failure and stops wave
        with state_lock:
            state['slices'][sid] = {
                **state['slices'].get(sid, {}),
                'status': 'failed',
                'completed_at': now_utc(),
                'error': str(exc),
            }
            write_json(run_dir / 'run-state.json', state)
        return state['slices'][sid]


def merge_slice(slice_item, args, run_dir, state):
    sid = slice_item['id']
    result = state['slices'].get(sid, {})
    if result.get('status') in {'no_changes', 'merged'}:
        return False
    pr_number = result.get('pr_number')
    if not pr_number:
        raise RuntimeError(f'{sid} has no PR to merge')
    if args.allow_review_request and not result.get('review_requested_at'):
        raise RuntimeError(f'{sid} review request timestamp missing; refusing to auto-merge after review request mode')
    cmd = [
        sys.executable,
        str(SCRIPT_DIR / 'merge_gate.py'),
        '--pr', str(pr_number),
        '--repo-path', result['worktree'],
        '--allow-merge',
        '--merge-method', args.merge_method,
        '--expected-head-sha', result.get('head_sha', ''),
        '--ci-timeout-seconds', str(args.ci_timeout_seconds),
        '--ci-poll-seconds', str(args.ci_poll_seconds),
        '--review-timeout-seconds', str(args.review_timeout_seconds),
    ]
    if args.allow_review_request:
        cmd += ['--require-review-after', result['review_requested_at']]
    if args.delete_branch:
        cmd.append('--delete-branch')
    merge = run_cmd(cmd)
    slice_dir = run_dir / 'slices' / sid
    (slice_dir / 'merge.stdout.log').write_text(merge.stdout, encoding='utf-8')
    (slice_dir / 'merge.stderr.log').write_text(merge.stderr, encoding='utf-8')
    if merge.returncode:
        raise RuntimeError(f'merge gate failed for {sid}: {merge.stderr or merge.stdout}')
    result['status'] = 'merged'
    result['merged_at'] = now_utc()
    state['slices'][sid] = result
    write_json(run_dir / 'run-state.json', state)
    return True


def resolve_pr_base_branch(base_ref_arg, default_branch_name, repo):
    if not base_ref_arg:
        return default_branch_name
    base_ref = base_ref_arg.strip()
    if base_ref.startswith('origin/'):
        return base_ref.split('/', 1)[1]
    if base_ref.startswith('refs/heads/'):
        return base_ref.removeprefix('refs/heads/')
    if base_ref.startswith('refs/remotes/origin/'):
        return base_ref.removeprefix('refs/remotes/origin/')
    if run_cmd(['git', 'show-ref', '--verify', f'refs/heads/{base_ref}'], cwd=repo).returncode == 0:
        return base_ref
    if run_cmd(['git', 'show-ref', '--verify', f'refs/remotes/origin/{base_ref}'], cwd=repo).returncode == 0:
        return base_ref
    raise RuntimeError(f'--base-ref cannot be used for PR mode unless it names a local branch or origin branch: {base_ref_arg}')


def print_dry_run(args, waves, merge_mode):
    print(f'waves={len(waves)} max_parallel={args.max_parallel} dry_run={args.dry_run} merge={merge_mode}')
    for w in waves:
        print(f"wave {w.get('wave')}: {w.get('slice_ids')}")
    print('codex args:', ' '.join(shlex.quote(c) for c in MODEL_ARGS + (['--profile', args.codex_profile] if args.codex_profile else []) + safe_extra_args(args.codex_extra_args)))


def parse_args():
    ap = argparse.ArgumentParser(description='Orchestrate slice waves.')
    ap.add_argument('slice_plan')
    ap.add_argument('waves')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--max-parallel', type=int, default=1)
    ap.add_argument('--codex-profile')
    ap.add_argument('--codex-bin')
    ap.add_argument('--codex-agent')
    ap.add_argument('--codex-extra-args', default='')
    ap.add_argument('--no-pr', action='store_true')
    ap.add_argument('--allow-pr', action='store_true')
    ap.add_argument('--allow-review-request', action='store_true')
    ap.add_argument('--allow-merge', action='store_true')
    ap.add_argument('--no-merge', '--pr-only', dest='no_merge', action='store_true')
    ap.add_argument('--run-dir')
    ap.add_argument('--worktree-dir', default=str(Path.home() / '.codex' / 'worktrees' / 'codebase-review'))
    ap.add_argument('--base-ref')
    ap.add_argument('--reuse-worktrees', action='store_true')
    ap.add_argument('--resume', action='store_true')
    ap.add_argument('--setup-command', action='append', default=[])
    ap.add_argument('--merge-method', choices=['squash', 'merge', 'rebase'], default='squash')
    ap.add_argument('--delete-branch', action='store_true')
    ap.add_argument('--ci-timeout-seconds', type=int, default=1800)
    ap.add_argument('--ci-poll-seconds', type=int, default=15)
    ap.add_argument('--review-timeout-seconds', type=int, default=1800)
    return ap.parse_args()


def main():
    args = parse_args()
    if args.codex_agent:
        print('--codex-agent is not supported by this local orchestrator yet', file=sys.stderr)
        return 2
    if args.no_pr:
        args.allow_pr = False
    if args.max_parallel <= 0:
        print('--max-parallel must be greater than zero', file=sys.stderr)
        return 2
    merge_enabled = args.allow_merge and not args.no_merge
    merge_mode = 'disabled' if not merge_enabled else 'allowed'
    if args.allow_review_request and not args.allow_pr:
        print('--allow-review-request requires --allow-pr', file=sys.stderr)
        return 2
    if merge_enabled and not args.allow_pr:
        print('--allow-merge requires --allow-pr', file=sys.stderr)
        return 2

    slice_plan_path = Path(args.slice_plan).resolve()
    waves_path = Path(args.waves).resolve()
    plan = load_json(slice_plan_path)
    waves = load_waves(waves_path)
    errors, by_id = validate_selected_plan(plan, waves)
    if errors:
        print('slice plan invalid: ' + '; '.join(errors), file=sys.stderr)
        return 1

    if args.dry_run:
        print_dry_run(args, waves, merge_mode)
        return 0

    try:
        repo = repo_root('.')
        ensure_clean_or_orchestration_only(repo, slice_plan_path, waves_path)
        args.codex_bin = resolve_codex_binary(args.codex_bin)
        if (args.allow_pr or args.allow_review_request or merge_enabled) and not command_exists('gh'):
            raise RuntimeError('gh binary not found')
        if (args.allow_pr or args.allow_review_request or merge_enabled) and not gh_auth_ok(repo):
            raise RuntimeError('gh auth status failed')

        repo_name = repo.name
        run_dir = Path(args.run_dir).expanduser() if args.run_dir else Path.home() / '.codex' / 'runs' / 'codebase-review' / f'{repo_name}-{_dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")}'
        run_dir = run_dir.resolve()
        run_dir.mkdir(parents=True, exist_ok=True)
        plan_hash = file_sha256(slice_plan_path)
        waves_hash = file_sha256(waves_path)
        branches = slice_branch_map(plan)
        state = load_state(run_dir, repo, slice_plan_path, waves_path, args.resume, plan_hash, waves_hash, branches, origin_url(repo))
        state['codex_bin'] = args.codex_bin
        state_lock = threading.Lock()
        write_json(run_dir / 'run-state.json', state)
        plan_copy = run_dir / 'slice-plan.json'
        shutil.copyfile(slice_plan_path, plan_copy)

        default_branch_name = default_branch(repo)
        base_ref = args.base_ref or f'origin/{default_branch_name}'
        if args.base_ref is None and run_cmd(['git', 'rev-parse', '--verify', base_ref], cwd=repo).returncode:
            base_ref = 'HEAD'
        pr_base_branch = resolve_pr_base_branch(args.base_ref, default_branch_name, repo) if args.allow_pr else default_branch_name

        print(f'waves={len(waves)} max_parallel={args.max_parallel} dry_run=False merge={merge_mode}')
        print(f'run_dir={run_dir}')
        worktree_dir = Path(args.worktree_dir).expanduser().resolve()

        for wave in waves:
            wave_id = str(wave.get('wave'))
            slice_ids = wave.get('slice_ids', [])
            print(f'wave {wave_id}: {slice_ids}')
            state['waves'][wave_id] = {'status': 'running', 'started_at': now_utc(), 'slice_ids': slice_ids}
            write_json(run_dir / 'run-state.json', state)
            pending = []
            for sid in slice_ids:
                if args.resume and state.get('slices', {}).get(sid, {}).get('status') in {'succeeded', 'no_changes', 'pr_ready', 'merged'}:
                    print(f'skip {sid}: already {state["slices"][sid]["status"]}')
                    continue
                pending.append(by_id[sid])

            with concurrent.futures.ThreadPoolExecutor(max_workers=min(args.max_parallel, max(1, len(pending)))) as executor:
                futures = [
                    executor.submit(run_slice, item, args, repo, worktree_dir, base_ref, run_dir, plan_copy, state, state_lock, pr_base_branch)
                    for item in pending
                ]
                results = [future.result() for future in concurrent.futures.as_completed(futures)]

            failed = [r for r in results if r.get('status') == 'failed']
            if failed:
                state['waves'][wave_id]['status'] = 'failed'
                state['waves'][wave_id]['completed_at'] = now_utc()
                write_json(run_dir / 'run-state.json', state)
                for item in failed:
                    print(f'{item.get("slice_id", item.get("branch", "slice"))} failed: {item.get("error", "unknown error")}', file=sys.stderr)
                print(f'wave {wave_id} failed; later waves blocked', file=sys.stderr)
                return 1

            if merge_enabled:
                for sid in wave.get('integration_order', slice_ids):
                    did_merge = merge_slice(by_id[sid], args, run_dir, state)
                    if did_merge:
                        fetch = run_cmd(['git', 'fetch', 'origin', default_branch_name], cwd=repo)
                        if fetch.returncode:
                            raise RuntimeError(fetch.stderr or fetch.stdout or 'git fetch failed after merge')
                        base_ref = f'origin/{default_branch_name}'

            state['waves'][wave_id]['status'] = 'succeeded'
            state['waves'][wave_id]['completed_at'] = now_utc()
            write_json(run_dir / 'run-state.json', state)

        return 0
    except Exception as exc:  # noqa: BLE001 - CLI entrypoint reports precise failure
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
