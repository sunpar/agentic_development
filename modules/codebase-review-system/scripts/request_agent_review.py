#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shlex
import subprocess
import types


def run(cmd):
    return subprocess.run(cmd)


def providers_from_arg(provider):
    return {'codex', 'copilot'} if provider == 'both' else {provider}


def build_review_body(providers, focus):
    focus = (focus or '').strip()
    lines = []
    if 'codex' in providers:
        lines.append(f'@codex review for {focus}' if focus else '@codex review')
    body = '\n'.join(lines)
    focus_items = [item.strip() for item in focus.split(',') if item.strip()]
    if focus_items and body:
        body += '\n\nFocus:\n- ' + '\n- '.join(focus_items)
    return body


def review_command(pr_number, providers, focus, repo=None):
    cmd = ['gh', 'pr', 'comment']
    if pr_number is not None:
        cmd.append(str(pr_number))
    cmd += ['--body', build_review_body(providers, focus)]
    if repo:
        cmd += ['--repo', repo]
    return cmd


def copilot_review_command(pr_number, repo=None):
    cmd = ['gh', 'pr', 'edit']
    if pr_number is not None:
        cmd.append(str(pr_number))
    cmd += ['--add-reviewer', '@copilot']
    if repo:
        cmd += ['--repo', repo]
    return cmd


def review_commands(pr_number, providers, focus, repo=None):
    commands = []
    if 'codex' in providers:
        commands.append(review_command(pr_number, {'codex'}, focus, repo=repo))
    if 'copilot' in providers:
        commands.append(copilot_review_command(pr_number, repo=repo))
    return commands


def post_request(pr_number, providers, focus, repo=None):
    results = [run(cmd) for cmd in review_commands(pr_number, providers, focus, repo=repo)]
    returncode = next((result.returncode for result in results if result.returncode), 0)
    return types.SimpleNamespace(returncode=returncode, results=results)


def dry_run_text(pr_number, providers, focus, repo=None):
    lines = []
    for cmd in review_commands(pr_number, providers, focus, repo=repo):
        lines.append('DRY-RUN: would run ' + shlex.join(cmd))
    body = build_review_body({'codex'} if 'codex' in providers else set(), focus)
    if body:
        lines.append(body)
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Request Codex/Copilot PR review.')
    parser.add_argument('--provider', choices=['codex', 'copilot', 'both'], default='codex')
    parser.add_argument('--focus', default='correctness, tests, API compatibility, slice scope')
    parser.add_argument('--pr-number', type=int)
    parser.add_argument('--repo')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    providers = providers_from_arg(args.provider)
    if args.dry_run:
        print(dry_run_text(args.pr_number, providers, args.focus, repo=args.repo))
        return 0

    result = post_request(args.pr_number, providers, args.focus, repo=args.repo)
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
