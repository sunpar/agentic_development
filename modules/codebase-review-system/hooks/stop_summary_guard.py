#!/usr/bin/env python3
import json, os, sys
from pathlib import Path


strict = os.environ.get('CODEBASE_REVIEW_FACTORY_STRICT') == '1'


def collect_strings(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out = []
        for item in value:
            out.extend(collect_strings(item))
        return out
    if isinstance(value, dict):
        out = []
        for item in value.values():
            out.extend(collect_strings(item))
        return out
    return []


def transcript_text(path):
    out = []
    try:
        lines = Path(path).read_text(encoding='utf-8', errors='ignore').splitlines()
    except Exception:
        return ''
    for line in lines:
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            out.append(line)
            continue
        out.extend(collect_strings(item))
    return '\n'.join(out)


def payload_summary(raw):
    if not raw:
        return ''
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if isinstance(payload, dict) and payload.get('transcript_path'):
        text = transcript_text(payload['transcript_path'])
        if text:
            return text
    return '\n'.join(collect_strings(payload))


summary = os.environ.get('CODEBASE_REVIEW_FACTORY_STOP_SUMMARY', '')
if not summary and not sys.stdin.isatty():
    summary = payload_summary(sys.stdin.read())
text = summary.lower()
has_validation = any(word in text for word in ['test', 'tests', 'validation', 'verified', 'not run'])
has_scope = any(word in text for word in ['changed', 'fixed', 'implemented', 'updated', 'blocked'])
if has_validation and has_scope:
    print('[codebase-review-factory] stop_summary_guard: summary contains scope and validation signal')
    sys.exit(0)
print('[codebase-review-factory] stop_summary_guard: summary should include work scope and tests/validation status')
sys.exit(1 if strict else 0)
