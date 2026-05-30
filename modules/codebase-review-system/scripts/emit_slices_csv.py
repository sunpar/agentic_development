#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


COLS = [
    'id',
    'feature_id',
    'wave',
    'title',
    'slice_type',
    'branch',
    'dependencies',
    'files_to_read',
    'docs_to_read',
    'tests_to_read',
    'files_allowed_to_edit',
    'verification_commands',
    'risk',
    'slice_file',
]


def cell(value):
    if isinstance(value, list):
        return ';'.join(str(item) for item in value)
    return value if value is not None else ''


def build_rows(plan):
    waves = {
        sid: wave.get('wave')
        for wave in plan.get('waves', [])
        for sid in wave.get('slice_ids', [])
    }
    rows = []
    for item in plan.get('slices', []):
        row = {column: cell(item.get(column)) for column in COLS}
        row['wave'] = waves.get(item.get('id'), '')
        row['slice_file'] = f'slices/{item.get("id")}.md'
        rows.append(row)
    return rows


def write_csv(stream, rows):
    writer = csv.DictWriter(stream, fieldnames=COLS)
    writer.writeheader()
    writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description='Emit slices CSV.')
    parser.add_argument('slice_plan')
    parser.add_argument('--output', default='slices.csv')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    plan = json.loads(Path(args.slice_plan).read_text(encoding='utf-8'))
    rows = build_rows(plan)

    if args.dry_run:
        print(f'DRY-RUN: would write CSV to {args.output}')
        write_csv(sys.stdout, rows)
        return 0

    with Path(args.output).open('w', encoding='utf-8', newline='') as stream:
        write_csv(stream, rows)
    print(args.output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
