#!/usr/bin/env python3
import os, sys


strict = os.environ.get('CODEBASE_REVIEW_FACTORY_STRICT') == '1'
summary = os.environ.get('CODEBASE_REVIEW_FACTORY_STOP_SUMMARY', '')
if not summary and not sys.stdin.isatty():
    summary = sys.stdin.read()
text = summary.lower()
has_validation = any(word in text for word in ['test', 'tests', 'validation', 'verified', 'not run'])
has_scope = any(word in text for word in ['changed', 'fixed', 'implemented', 'updated', 'blocked'])
if has_validation and has_scope:
    print('[codebase-review-factory] stop_summary_guard: summary contains scope and validation signal')
    sys.exit(0)
print('[codebase-review-factory] stop_summary_guard: summary should include work scope and tests/validation status')
sys.exit(1 if strict else 0)
