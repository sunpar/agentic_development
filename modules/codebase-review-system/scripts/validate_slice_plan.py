#!/usr/bin/env python3
import argparse
from fnmatch import fnmatch
from pathlib import PurePosixPath

from factory_common import load_json, required, fail_or_print, slug_safe


REQ = [
    'id', 'feature_id', 'title', 'slice_type', 'description', 'intended_behavior',
    'why_this_slice_exists', 'files_to_read', 'docs_to_read', 'tests_to_read',
    'files_allowed_to_edit', 'files_not_allowed_to_edit', 'entry_points',
    'invariants', 'non_goals', 'review_questions', 'refactor_targets',
    'verification_commands', 'expected_pr_size', 'dependencies',
    'parallel_conflicts', 'risk', 'risk_notes', 'acceptance_criteria',
    'branch', 'pr_title', 'review_focus',
]

LIST_FIELDS = [
    'files_to_read', 'docs_to_read', 'tests_to_read', 'files_allowed_to_edit',
    'files_not_allowed_to_edit', 'entry_points', 'invariants', 'non_goals',
    'review_questions', 'refactor_targets', 'verification_commands',
    'dependencies', 'parallel_conflicts', 'risk_notes', 'acceptance_criteria',
    'review_focus',
]

SLICE_TYPES = {
    'review-only',
    'review-refactor',
    'refactor-simplify',
    'refactor-performance',
    'refactor-api-coherence',
    'refactor-dead-code',
}
RISKS = {'low', 'medium', 'high', 'critical'}


def unsafe_path(path):
    if not isinstance(path, str) or not path.strip():
        return True
    if '\x00' in path or path.startswith(('/', '~')):
        return True
    parts = PurePosixPath(path.replace('\\', '/')).parts
    return '..' in parts


def paths_conflict(a, b):
    if a == b or fnmatch(a, b) or fnmatch(b, a):
        return True
    a_clean = a.rstrip('/').replace('/**', '')
    b_clean = b.rstrip('/').replace('/**', '')
    return bool(a_clean and b_clean and (a_clean.startswith(b_clean + '/') or b_clean.startswith(a_clean + '/')))


def has_path_conflict(left, right):
    for a in left:
        for b in right:
            if paths_conflict(a, b):
                return a, b
    return None


def find_cycle(graph):
    visiting = set()
    visited = set()
    stack = []

    def visit(node):
        if node in visited:
            return None
        if node in visiting:
            return stack[stack.index(node):] + [node]
        visiting.add(node)
        stack.append(node)
        for dep in graph.get(node, []):
            cycle = visit(dep)
            if cycle:
                return cycle
        stack.pop()
        visiting.remove(node)
        visited.add(node)
        return None

    for node in graph:
        cycle = visit(node)
        if cycle:
            return cycle
    return None


def validate_slice(i, s, ids, errors):
    errors += required(s, REQ, f'slices[{i}]')
    sid = s.get('id', '')
    if not sid or ' ' in sid:
        errors.append(f'slices[{i}].id must be nonempty and space-free')
    if sid in ids:
        errors.append(f'duplicate slice id {sid}')
    ids.add(sid)

    for field in LIST_FIELDS:
        value = s.get(field)
        if field in s and not isinstance(value, list):
            errors.append(f'{sid}.{field} must be list')

    if not s.get('files_allowed_to_edit'):
        errors.append(f'{sid}.files_allowed_to_edit required')
    if not s.get('verification_commands'):
        errors.append(f'{sid}.verification_commands required')

    for field in ['files_to_read', 'docs_to_read', 'tests_to_read', 'files_allowed_to_edit', 'files_not_allowed_to_edit']:
        for path in s.get(field, []):
            if unsafe_path(path):
                errors.append(f'{sid}.{field} unsafe path {path}')

    if s.get('slice_type') and s.get('slice_type') not in SLICE_TYPES:
        errors.append(f'{sid}.slice_type invalid {s.get("slice_type")}')
    if s.get('risk') and s.get('risk') not in RISKS:
        errors.append(f'{sid}.risk invalid {s.get("risk")}')

    expected_size = s.get('expected_pr_size')
    if 'expected_pr_size' in s and not isinstance(expected_size, dict):
        errors.append(f'{sid}.expected_pr_size must be object')
    elif isinstance(expected_size, dict):
        for field in ['max_files_changed', 'max_lines_changed_soft']:
            if not isinstance(expected_size.get(field), int) or expected_size.get(field) <= 0:
                errors.append(f'{sid}.expected_pr_size.{field} must be positive integer')

    br = s.get('branch', '')
    if not slug_safe(br):
        errors.append(f'{sid}.branch unsafe')


def validate_waves(data, slices, by_id, errors):
    waves = data.get('waves')
    if not isinstance(waves, list) or not waves:
        errors.append('waves must be nonempty list')
        return

    membership = {sid: [] for sid in by_id}
    wave_index = {}
    for i, wave in enumerate(waves):
        if not isinstance(wave, dict):
            errors.append(f'waves[{i}] must be object')
            continue
        errors += required(wave, ['wave', 'slice_ids', 'parallel_safety_rationale', 'integration_order'], f'waves[{i}]')
        slice_ids = wave.get('slice_ids', [])
        if not isinstance(slice_ids, list):
            errors.append(f'waves[{i}].slice_ids must be list')
            continue
        for sid in slice_ids:
            if sid not in by_id:
                errors.append(f'waves[{i}].slice_ids unknown {sid}')
                continue
            membership[sid].append(i)
            wave_index[sid] = i

        integration_order = wave.get('integration_order', [])
        if isinstance(integration_order, list):
            if set(integration_order) != set(slice_ids):
                errors.append(f'waves[{i}].integration_order must match slice_ids')
        elif 'integration_order' in wave:
            errors.append(f'waves[{i}].integration_order must be list')

        for left_pos, left_id in enumerate(slice_ids):
            if left_id not in by_id:
                continue
            left = by_id[left_id]
            for right_id in slice_ids[left_pos + 1:]:
                if right_id not in by_id:
                    continue
                right = by_id[right_id]
                conflict = has_path_conflict(left.get('files_allowed_to_edit', []), right.get('files_allowed_to_edit', []))
                if conflict:
                    errors.append(f'same-wave edit conflict {left_id} {right_id}: {conflict[0]} vs {conflict[1]}')
                if right_id in left.get('parallel_conflicts', []) or left_id in right.get('parallel_conflicts', []):
                    errors.append(f'same-wave declared parallel conflict {left_id} {right_id}')

    for sid, waves_for_slice in membership.items():
        if len(waves_for_slice) != 1:
            errors.append(f'{sid} must appear in exactly one wave')

    for s in slices:
        sid = s.get('id')
        for dep in s.get('dependencies', []):
            if dep in wave_index and sid in wave_index and wave_index[dep] >= wave_index[sid]:
                errors.append(f'{sid}.dependencies {dep} must be in an earlier wave')


def validate(data):
    errors = []
    slices = data.get('slices')
    if not isinstance(slices, list) or not slices:
        return ['slices must be nonempty list']

    ids = set()
    for i, s in enumerate(slices):
        if not isinstance(s, dict):
            errors.append(f'slices[{i}] must be object')
            continue
        validate_slice(i, s, ids, errors)

    by_id = {s.get('id'): s for s in slices if isinstance(s, dict) and s.get('id')}
    for s in slices:
        if not isinstance(s, dict):
            continue
        sid = s.get('id')
        for dep in s.get('dependencies', []):
            if dep not in ids:
                errors.append(f'{sid}.dependencies unknown {dep}')
        for conflict in s.get('parallel_conflicts', []):
            if conflict not in ids:
                errors.append(f'{sid}.parallel_conflicts unknown {conflict}')

    graph = {s.get('id'): s.get('dependencies', []) for s in slices if isinstance(s, dict) and s.get('id') in ids}
    cycle = find_cycle(graph)
    if cycle:
        errors.append('dependency cycle: ' + ' -> '.join(cycle))

    validate_waves(data, slices, by_id, errors)
    return errors


def main():
    ap = argparse.ArgumentParser(description='Validate slice plan.')
    ap.add_argument('path')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()
    return fail_or_print(validate(load_json(args.path)), args.json)


if __name__ == '__main__':
    raise SystemExit(main())
