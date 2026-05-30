#!/usr/bin/env python3
"""Aggregate codebase review orchestration run summaries."""
from __future__ import annotations

import argparse
import datetime as _dt
import json
from pathlib import Path


def now_utc():
    return _dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def status_counts(items):
    counts = {}
    for item in items:
        status = str(item.get('status') or 'unknown')
        counts[status] = counts.get(status, 0) + 1
    return counts


def sorted_mapping_items(mapping):
    return [
        (key, value)
        for key, value in sorted((mapping or {}).items(), key=lambda item: str(item[0]))
        if isinstance(value, dict)
    ]


def summary_from_state(run_dir):
    state = load_json(run_dir / 'run-state.json')
    waves = [
        {
            'wave': wave_id,
            'status': wave.get('status'),
            'slice_ids': wave.get('slice_ids', []),
        }
        for wave_id, wave in sorted_mapping_items(state.get('waves'))
    ]
    slices = [
        {
            'id': slice_id,
            'status': item.get('status'),
            'branch': item.get('branch'),
            'pr_number': item.get('pr_number'),
            'error': item.get('error'),
        }
        for slice_id, item in sorted_mapping_items(state.get('slices'))
    ]
    return {
        'generated_at': state.get('updated_at') or state.get('created_at'),
        'repo': state.get('repo'),
        'run_dir': state.get('run_dir') or str(run_dir),
        'totals': {
            'waves': len(waves),
            'slices': len(slices),
            'by_status': status_counts(slices),
        },
        'waves': waves,
        'slices': slices,
    }


def load_run_summary(run_dir):
    summary_path = run_dir / 'run-summary.json'
    state_path = run_dir / 'run-state.json'
    if summary_path.exists():
        summary = load_json(summary_path)
        source = summary_path
    elif state_path.exists():
        summary = summary_from_state(run_dir)
        source = state_path
    else:
        return None

    slices = summary.get('slices') or []
    pr_numbers = sorted({
        int(item['pr_number'])
        for item in slices
        if isinstance(item, dict) and item.get('pr_number') is not None
    })
    failed_slices = [
        str(item.get('id'))
        for item in slices
        if isinstance(item, dict) and str(item.get('status') or '') in {'failed', 'error'}
    ]
    totals = summary.get('totals') or {}
    return {
        'name': run_dir.name,
        'run_dir': str(run_dir),
        'repo': summary.get('repo'),
        'generated_at': summary.get('generated_at'),
        'summary_source': str(source),
        'totals': {
            'waves': int(totals.get('waves') or 0),
            'slices': int(totals.get('slices') or 0),
            'by_status': dict(totals.get('by_status') or {}),
        },
        'failed_slices': failed_slices,
        'pr_numbers': pr_numbers,
    }


def aggregate_runs(runs_root):
    runs_root = Path(runs_root).expanduser()
    runs = []
    if runs_root.exists():
        for child in sorted(runs_root.iterdir(), key=lambda path: path.name):
            if child.is_dir():
                summary = load_run_summary(child)
                if summary:
                    runs.append(summary)
    by_status = {}
    for run in runs:
        for status, count in run['totals']['by_status'].items():
            by_status[status] = by_status.get(status, 0) + int(count)
    return {
        'generated_at': now_utc(),
        'runs_root': str(runs_root),
        'totals': {
            'runs': len(runs),
            'waves': sum(run['totals']['waves'] for run in runs),
            'slices': sum(run['totals']['slices'] for run in runs),
            'by_status': by_status,
        },
        'runs': runs,
    }


def write_markdown(path, aggregate):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        '# Codebase Review Run Report',
        '',
        f'Runs root: {aggregate["runs_root"]}',
        '',
        '## Totals',
        '',
        f'- Runs: {aggregate["totals"]["runs"]}',
        f'- Waves: {aggregate["totals"]["waves"]}',
        f'- Slices: {aggregate["totals"]["slices"]}',
    ]
    for status, count in sorted(aggregate['totals']['by_status'].items()):
        lines.append(f'- {status}: {count}')
    lines += ['', '## Runs', '']
    for run in aggregate['runs']:
        status_text = ', '.join(
            f'{status}: {count}'
            for status, count in sorted(run['totals']['by_status'].items())
        ) or 'no slices'
        line = f'- {run["name"]}: {run["totals"]["slices"]} slices ({status_text})'
        if run['failed_slices']:
            line += f'; failed={", ".join(run["failed_slices"])}'
        if run['pr_numbers']:
            line += '; PRs=' + ', '.join(f'#{number}' for number in run['pr_numbers'])
        lines.append(line)
    path.write_text('\n'.join(lines).rstrip() + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description='Aggregate codebase review orchestration runs.')
    parser.add_argument('--runs-root', default='~/.codex/runs/codebase-review')
    parser.add_argument('--output-json')
    parser.add_argument('--output-md')
    args = parser.parse_args()

    aggregate = aggregate_runs(args.runs_root)
    if args.output_json:
        write_json(args.output_json, aggregate)
        print(args.output_json)
    else:
        print(json.dumps(aggregate, indent=2, sort_keys=True))
    if args.output_md:
        write_markdown(args.output_md, aggregate)
        print(args.output_md)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
