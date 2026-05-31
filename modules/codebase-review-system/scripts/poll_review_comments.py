#!/usr/bin/env python3
"""Poll and classify pull request review comments."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from pathlib import Path


MUST_FIX_RE = re.compile(r'\b(p0|p1|critical|block(?:er|ing)?|must[- ]?fix|changes requested)\b', re.I)
SHOULD_FIX_RE = re.compile(r'\b(should[- ]?fix|should change|please fix|needs? follow[- ]?up)\b', re.I)
P2_RE = re.compile(r'(?:\[p2\]|\bp2\b)', re.I)
NONBLOCKING_RE = [
    re.compile(r'\bnon[- ]blocking\b\s*:?', re.I),
    re.compile(r'\bno\s+changes?\s+requested\b\.?', re.I),
    re.compile(r'\bno\s+(?:p0|p1|p2|critical|blocking|blocker|must[- ]?fix|changes requested)\s+(?:findings?|issues?|comments?)\b', re.I),
    re.compile(r'\b(?:p0|p1|p2|critical|blocking|blocker|must[- ]?fix|changes requested)\s+(?:findings?|issues?)\s*:\s*(?:none|no|0|zero)\b', re.I),
    re.compile(r"\bdidn'?t find (?:any )?(?:major|blocking|critical) issues?\b", re.I),
]


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def author_login(item):
    author = item.get('author') or item.get('user') or {}
    if isinstance(author, dict):
        return str(author.get('login') or '')
    return str(author or '')


def provider_for_login(login):
    value = str(login or '').lower()
    if 'codex' in value:
        return 'codex'
    if 'copilot' in value:
        return 'copilot'
    if value:
        return 'human'
    return 'unknown'


def strip_nonblocking_phrases(body):
    text = str(body or '')
    for pattern in NONBLOCKING_RE:
        text = pattern.sub('', text)
    return text


def classify_severity(body, state=''):
    state = str(state or '').upper()
    text = strip_nonblocking_phrases(body)
    if state == 'CHANGES_REQUESTED' or MUST_FIX_RE.search(text):
        return 'must_fix'
    if SHOULD_FIX_RE.search(text) or P2_RE.search(text):
        return 'should_fix'
    return 'info'


def normalize_item(item, source, index):
    raw_id = item.get('id')
    item_id = f'{source}-{raw_id if raw_id is not None else index}'
    body = str(item.get('body') or '')
    login = author_login(item)
    state = item.get('state') if source == 'review' else ''
    return {
        'id': item_id,
        'source': source,
        'author': login,
        'provider': provider_for_login(login),
        'state': state or '',
        'severity': classify_severity(body, state),
        'created_at': item.get('createdAt') or item.get('created_at') or item.get('submittedAt') or item.get('submitted_at'),
        'path': item.get('path'),
        'line': item.get('line'),
        'body': body,
        'url': item.get('url') or item.get('html_url'),
    }


def reviews_from_payload(payload):
    if 'latestReviews' in payload:
        return payload.get('latestReviews') or []
    return payload.get('reviews') or []


def normalize_payload(payload):
    comments = [
        normalize_item(item, 'comment', index)
        for index, item in enumerate(payload.get('comments') or [], 1)
        if isinstance(item, dict)
    ]
    reviews = [
        normalize_item(item, 'review', index)
        for index, item in enumerate(reviews_from_payload(payload), 1)
        if isinstance(item, dict)
    ]
    items = comments + reviews
    provider_counts = {}
    for item in items:
        provider_counts[item['provider']] = provider_counts.get(item['provider'], 0) + 1
    actionable = [item for item in items if item['severity'] in {'must_fix', 'should_fix'}]
    severity_counts = {}
    for item in actionable:
        severity_counts[item['severity']] = severity_counts.get(item['severity'], 0) + 1
    return {
        'status': 'ok',
        'url': payload.get('url'),
        'number': payload.get('number'),
        'title': payload.get('title'),
        'provider_counts': provider_counts,
        'actionable_counts_by_severity': severity_counts,
        'comments': items,
        'actionable_comments': actionable,
    }


def write_markdown(path, report):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        '# PR Review Comment Report',
        '',
        f'URL: {report.get("url") or ""}',
        '',
        '## Providers',
        '',
    ]
    for provider, count in sorted(report.get('provider_counts', {}).items()):
        lines.append(f'- {provider}: {count}')
    lines += [
        '',
        '## Actionable Review Comments',
        '',
    ]
    if not report.get('actionable_comments'):
        lines.append('- None')
    for item in report.get('actionable_comments') or []:
        detail = f'- {item["id"]}: {item["severity"]} from {item["author"] or "unknown"}'
        if item.get('path'):
            detail += f' at {item["path"]}'
            if item.get('line'):
                detail += f':{item["line"]}'
        lines.append(detail)
    path.write_text('\n'.join(lines).rstrip() + '\n', encoding='utf-8')


def gh_pr_view(args):
    cmd = ['gh', 'pr', 'view']
    if args.pr:
        cmd.append(str(args.pr))
    if args.repo:
        cmd += ['--repo', args.repo]
    cmd += ['--json', 'comments,latestReviews,url,number,title']
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def repo_from_pr_url(url):
    match = re.search(r'github\.com[/:]([^/\s]+/[^/\s]+)/pull/\d+', str(url or ''))
    if not match:
        return None
    repo = match.group(1)
    return repo[:-4] if repo.endswith('.git') else repo


def gh_repo_name_with_owner():
    result = subprocess.run(
        ['gh', 'repo', 'view', '--json', 'nameWithOwner'],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    return payload.get('nameWithOwner')


def repo_full_name(args, payload):
    if args.repo:
        return args.repo
    return repo_from_pr_url(payload.get('url')) or gh_repo_name_with_owner()


def fetch_inline_review_comments(args, payload):
    repo = repo_full_name(args, payload)
    number = payload.get('number') or args.pr
    if not repo or not number:
        return []
    result = subprocess.run(
        ['gh', 'api', f'repos/{repo}/pulls/{number}/comments', '--paginate'],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []
    return parse_paginated_json_arrays(result.stdout)


def parse_paginated_json_arrays(text):
    decoder = json.JSONDecoder()
    comments = []
    index = 0
    text = str(text or '')
    while index < len(text):
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            break
        try:
            payload, index = decoder.raw_decode(text, index)
        except json.JSONDecodeError:
            return []
        if isinstance(payload, list):
            comments.extend(item for item in payload if isinstance(item, dict))
        elif isinstance(payload, dict):
            comments.append(payload)
    return comments


def merge_inline_review_comments(payload, inline_comments):
    comments = list(payload.get('comments') or [])
    seen = {str(item.get('id')) for item in comments if isinstance(item, dict) and item.get('id') is not None}
    for item in inline_comments:
        if not isinstance(item, dict):
            continue
        item_id = item.get('id')
        if item_id is not None and str(item_id) in seen:
            continue
        comments.append(item)
        if item_id is not None:
            seen.add(str(item_id))
    payload = dict(payload)
    payload['comments'] = comments
    return payload


def fetch_payload(args):
    if args.input_json:
        return load_json(args.input_json)
    end = time.time() + args.timeout
    while True:
        result = gh_pr_view(args)
        if result.returncode == 0:
            payload = json.loads(result.stdout)
            return merge_inline_review_comments(payload, fetch_inline_review_comments(args, payload))
        if time.time() >= end:
            return {'status': 'timeout', 'comments': [], 'latestReviews': [], 'error': result.stderr or result.stdout}
        time.sleep(max(1, args.poll_seconds))


def main():
    parser = argparse.ArgumentParser(description='Poll PR review comments and write an actionable report.')
    parser.add_argument('--repo')
    parser.add_argument('--pr')
    parser.add_argument('--input-json')
    parser.add_argument('--timeout', type=int, default=600)
    parser.add_argument('--poll-seconds', type=int, default=10)
    parser.add_argument('--output-json', default='review-comments.json')
    parser.add_argument('--output-md', default='review-comments.md')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    if args.dry_run:
        target = args.input_json or f'PR {args.pr or "current"}'
        print(f'would poll/classify review comments for {target} for up to {args.timeout}s and write {args.output_json}, {args.output_md}')
        return 0

    payload = fetch_payload(args)
    if payload.get('status') == 'timeout':
        report = {
            'status': 'timeout',
            'provider_counts': {},
            'actionable_counts_by_severity': {},
            'comments': [],
            'actionable_comments': [],
            'error': payload.get('error'),
        }
    else:
        report = normalize_payload(payload)
    write_json(args.output_json, report)
    write_markdown(args.output_md, report)
    print(args.output_json)
    print(args.output_md)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
