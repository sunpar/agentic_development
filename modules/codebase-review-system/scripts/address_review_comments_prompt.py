#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


MUST_FIX_TERMS = [
    'must',
    'required',
    'blocker',
    'broken',
    'incorrect',
    'security',
    'regression',
    'missing test',
    'failing',
]
SHOULD_FIX_TERMS = ['should', 'please', 'need', 'fix', 'change', 'requested']
CLARIFY_TERMS = ['clarify', 'unclear', 'question', '?']
NONBLOCKING_RE = [
    re.compile(r'\bnon[- ]blocking\b\s*:?', re.I),
    re.compile(r'\bno\s+changes?\s+requested\b\.?', re.I),
    re.compile(r'\bno\s+(?:p0|p1|p2|critical|blocking|blocker|must[- ]?fix)\s+(?:findings?|issues?|comments?)\b', re.I),
]


def strip_nonblocking_phrases(body):
    text = str(body or '')
    for pattern in NONBLOCKING_RE:
        text = pattern.sub('', text)
    return text


def classify(body):
    text = strip_nonblocking_phrases(body).lower()
    if any(term in text for term in MUST_FIX_TERMS):
        return 'must_fix'
    if any(term in text for term in CLARIFY_TERMS):
        return 'clarify'
    if any(term in text for term in SHOULD_FIX_TERMS):
        return 'should_fix'
    return 'note'


def normalize_classification(item):
    severity = str(item.get('severity') or '').lower()
    if severity in {'must_fix', 'should_fix'}:
        stripped = strip_nonblocking_phrases(item.get('body')).strip()
        if not re.search(r'[A-Za-z0-9]', stripped):
            return 'note'
        return severity
    return classify(item.get('body') or '')


def normalize_items(payload):
    items = []
    source_items = payload.get('actionable_comments')
    if source_items is None:
        source_items = payload.get('actionable', [])
    for idx, item in enumerate(source_items or [], start=1):
        body = (item.get('body') or '').strip()
        if not body:
            continue
        items.append({
            'id': idx,
            'classification': normalize_classification(item),
            'source': item.get('source', 'unknown'),
            'author': item.get('author', 'unknown'),
            'url': item.get('url', ''),
            'path': item.get('path'),
            'line': item.get('line'),
            'body': body,
        })
    return items


def render_section(title, items):
    lines = [f'## {title}']
    if not items:
        lines.append('- None')
        return lines
    for item in items:
        url = f" ({item['url']})" if item.get('url') else ''
        location = ''
        if item.get('path'):
            location = f" at {item['path']}"
            if item.get('line'):
                location += f":{item['line']}"
        lines.append(f"{item['id']}. {item['author']} [{item['source']}]{location}{url}: {item['body']}")
    return lines


def render_prompt(payload, slice_id=None):
    items = normalize_items(payload)
    by_class = {
        kind: [item for item in items if item['classification'] == kind]
        for kind in ('must_fix', 'should_fix', 'clarify', 'note')
    }
    lines = [
        '# Address PR Review Comments',
        '',
        f"PR: {payload.get('pr') or 'unknown'}",
    ]
    if payload.get('pr_url'):
        lines.append(f"URL: {payload['pr_url']}")
    if slice_id:
        lines.append(f'Slice: {slice_id}')
    lines.extend([
        '',
        'Fix only in-scope must-fix and should-fix review comments.',
        'Verify each comment against the current code before editing.',
        'Explain invalid or out-of-scope comments instead of broadening scope.',
        'Do not address clarify-only items until ambiguity is resolved.',
        'Run verification, commit and push follow-up changes, and reply with evidence.',
        '',
    ])
    lines.extend(render_section('Must Fix', by_class['must_fix']))
    lines.append('')
    lines.extend(render_section('Should Fix', by_class['should_fix']))
    lines.append('')
    lines.extend(render_section('Needs Clarification', by_class['clarify']))
    lines.append('')
    lines.extend(render_section('Notes', by_class['note']))
    lines.append('')
    lines.extend([
        '## Required Completion Note',
        '- Files changed',
        '- Review comments addressed',
        '- Verification commands and results',
        '- Comments replied to with evidence',
        '- Remaining risks or unresolved clarifications',
    ])
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description='Create Codex prompt from review comments JSON.')
    parser.add_argument('comments_json')
    parser.add_argument('--slice-id')
    parser.add_argument('--output')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    payload = json.loads(Path(args.comments_json).read_text(encoding='utf-8'))
    prompt = render_prompt(payload, slice_id=args.slice_id)
    if args.dry_run:
        if args.output:
            print(f'DRY-RUN: would write prompt to {args.output}')
        print(prompt, end='')
        return 0
    if args.output:
        Path(args.output).write_text(prompt, encoding='utf-8')
        print(args.output)
        return 0
    print(prompt, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
