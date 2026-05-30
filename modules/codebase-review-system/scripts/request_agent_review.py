#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shlex
import subprocess


def run(cmd):
    return subprocess.run(cmd)


def providers_from_arg(provider):
    return {'codex', 'copilot'} if provider == 'both' else {provider}


def build_review_body(providers, focus):
    focus = (focus or '').strip()
    lines = []
    if 'codex' in providers:
        lines.append(f'@codex review for {focus}' if focus else '@codex review')
    if 'copilot' in providers:
        lines.append(f'@copilot please review this PR for {focus}' if focus else '@copilot please review this PR')
    body = '\n'.join(lines)
    focus_items = [item.strip() for item in focus.split(',') if item.strip()]
    if focus_items:
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


def post_request(pr_number, providers, focus, repo=None):
    return run(review_command(pr_number, providers, focus, repo=repo))


def main():
    parser = argparse.ArgumentParser(description='Request Codex/Copilot PR review.')
    parser.add_argument('--provider', choices=['codex', 'copilot', 'both'], default='codex')
    parser.add_argument('--focus', default='correctness, tests, API compatibility, slice scope')
    parser.add_argument('--pr-number', type=int)
    parser.add_argument('--repo')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    providers = providers_from_arg(args.provider)
    cmd = review_command(args.pr_number, providers, args.focus, repo=args.repo)
    if args.dry_run:
        print('DRY-RUN: would run ' + shlex.join(cmd))
        print(build_review_body(providers, args.focus))
        return 0

    result = run(cmd)
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
