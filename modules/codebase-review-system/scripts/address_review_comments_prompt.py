#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
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


def classify(body):
    text = body.lower()
    if any(term in text for term in MUST_FIX_TERMS):
        return 'must_fix'
    if any(term in text for term in CLARIFY_TERMS):
        return 'clarify'
    if any(term in text for term in SHOULD_FIX_TERMS):
        return 'should_fix'
    return 'note'


def normalize_items(payload):
    items = []
    for idx, item in enumerate(payload.get('actionable', []), start=1):
        body = (item.get('body') or '').strip()
        if not body:
            continue
        items.append({
            'id': idx,
            'classification': classify(body),
            'source': item.get('source', 'unknown'),
            'author': item.get('author', 'unknown'),
            'url': item.get('url', ''),
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
        lines.append(f"{item['id']}. {item['author']} [{item['source']}]{url}: {item['body']}")
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
