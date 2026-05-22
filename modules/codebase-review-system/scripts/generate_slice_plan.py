#!/usr/bin/env python3
import argparse
import csv
import json
import re
from pathlib import Path


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-') or 'slice'


def build_slice(n, feature, model):
    sid = f'SLICE-{n:03d}'
    title = f"Review {feature.get('name', 'feature')}"
    return {
        'id': sid,
        'feature_id': feature.get('id'),
        'title': title,
        'slice_type': 'review-only',
        'description': f'Review and identify safe refactor opportunities for {feature.get("name")}.',
        'intended_behavior': feature.get('intended_behavior', 'Preserve behavior.'),
        'why_this_slice_exists': 'Initial conservative slice from feature model.',
        'files_to_read': feature.get('code_paths', [])[:10],
        'docs_to_read': feature.get('docs', [])[:10],
        'tests_to_read': feature.get('tests', [])[:10],
        'files_allowed_to_edit': feature.get('code_paths', [])[:5] or ['docs/agentic-system/**'],
        'files_not_allowed_to_edit': ['package-lock.json', 'pnpm-lock.yaml', 'yarn.lock'],
        'entry_points': feature.get('entry_points', []),
        'invariants': ['Preserve documented behavior.'],
        'non_goals': ['New product behavior.'],
        'review_questions': ['Does code match intended behavior?'],
        'refactor_targets': ['Remove local duplication if safe.'],
        'verification_commands': model.get('repo', {}).get('test_commands', []) or ['document validation command before editing'],
        'expected_pr_size': {'max_files_changed': 8, 'max_lines_changed_soft': 500},
        'dependencies': [],
        'parallel_conflicts': [],
        'risk': 'medium',
        'risk_notes': feature.get('known_risks', []),
        'acceptance_criteria': ['Review completed and any changes verified.'],
        'branch': f'codebase-review/{sid}-{slug(title)}',
        'pr_title': f'[codebase-review] {sid}: {title}',
        'review_focus': ['correctness', 'tests', 'scope'],
    }


def build_waves(slices):
    waves = []
    for n, item in enumerate(slices, 1):
        sid = item['id']
        waves.append({
            'wave': n,
            'slice_ids': [sid],
            'preconditions': [],
            'parallel_safety_rationale': 'Not proven; serialized by default.',
            'integration_order': [sid],
            'post_wave_verification_commands': item.get('verification_commands', []),
        })
    return waves


def main():
    ap = argparse.ArgumentParser(description='Generate conservative slice plan from feature model.')
    ap.add_argument('feature_model')
    ap.add_argument('--output-dir', default='.')
    ap.add_argument('--feature')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    model = json.loads(Path(args.feature_model).read_text())
    out = Path(args.output_dir)
    slices = []
    for n, feature in enumerate(model.get('features', []), 1):
        if args.feature and feature.get('id') != args.feature:
            continue
        slices.append(build_slice(n, feature, model))

    plan = {'slices': slices, 'waves': build_waves(slices)}
    text = json.dumps(plan, indent=2, sort_keys=True) + '\n'
    if args.dry_run:
        print(text)
        return 0

    out.mkdir(parents=True, exist_ok=True)
    (out/'slices').mkdir(exist_ok=True)
    (out/'slice-plan.json').write_text(text, encoding='utf-8')
    (out/'slice-plan.md').write_text('# Slice Plan\n\n' + '\n'.join(f'- {s["id"]}: {s["title"]}' for s in slices) + '\n', encoding='utf-8')
    with (out/'slices.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'feature_id', 'title', 'branch', 'risk'])
        writer.writeheader()
        writer.writerows({k: s.get(k, '') for k in ['id', 'feature_id', 'title', 'branch', 'risk']} for s in slices)
    for item in slices:
        (out/'slices'/f'{item["id"]}.md').write_text('# ' + item['title'] + '\n\n' + item['description'] + '\n', encoding='utf-8')
    print(out/'slice-plan.json')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
