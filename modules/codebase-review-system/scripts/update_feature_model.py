#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def append_unique(values, value):
    if value and value not in values:
        values.append(value)


def update_model(data, status_note):
    unknowns = data.setdefault('unknowns', [])
    append_unique(unknowns, status_note)
    return data


def main():
    parser = argparse.ArgumentParser(description='Update feature model metadata after runs.')
    parser.add_argument('feature_model')
    parser.add_argument('--status-note', default='updated')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    path = Path(args.feature_model)
    data = json.loads(path.read_text(encoding='utf-8'))
    update_model(data, args.status_note)
    text = json.dumps(data, indent=2, sort_keys=True) + '\n'

    if args.dry_run:
        print(text, end='')
        return 0

    path.write_text(text, encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
