#!/usr/bin/env python3
"""Generate feature implementation task plans from a feature model."""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


TASK_COLUMNS = [
    'id',
    'epic_id',
    'wave',
    'title',
    'branch',
    'dependencies',
    'context_to_load',
    'read_set',
    'write_set',
    'verification_commands',
    'task_file',
]


def slug(value):
    return re.sub(r'[^a-z0-9]+', '-', str(value).lower()).strip('-') or 'feature'


def as_list(value):
    if isinstance(value, list):
        return value
    if value in (None, ''):
        return []
    return [value]


def unique(values):
    out = []
    for value in values:
        text = str(value).strip()
        if text and text not in out:
            out.append(text)
    return out


def selected_features(model, feature_id=None):
    features = [item for item in model.get('features', []) if isinstance(item, dict)]
    if feature_id:
        features = [item for item in features if item.get('id') == feature_id]
    return features


def feature_title(feature):
    return str(feature.get('name') or feature.get('id') or 'Feature')


def default_verification(model):
    return as_list((model.get('repo') or {}).get('test_commands')) or ['Add and run the focused verification command for this feature.']


def build_epics(features):
    epics = []
    for index, feature in enumerate(features, 1):
        epic_id = f'EPIC-{index:03d}'
        epics.append({
            'id': epic_id,
            'feature_id': feature.get('id'),
            'title': f'Implement {feature_title(feature)}',
            'objective': feature.get('summary') or feature.get('intended_behavior') or f'Implement {feature_title(feature)}.',
            'task_ids': [f'TASK-{index:03d}'],
        })
    return epics


def build_task(index, feature, model, epic_id, feature_to_task):
    task_id = f'TASK-{index:03d}'
    title = f'Implement {feature_title(feature)}'
    code_paths = unique(as_list(feature.get('code_paths')))
    docs = unique(as_list(feature.get('docs')))
    tests = unique(as_list(feature.get('tests')))
    entry_points = unique(as_list(feature.get('entry_points')))
    read_set = unique(docs + code_paths + tests + entry_points)
    write_set = code_paths or ['src/**']
    context_to_load = read_set or ['README.md']
    dependencies = [
        feature_to_task[feature_id]
        for feature_id in as_list(feature.get('related_features'))
        if feature_id in feature_to_task
    ]
    verification = default_verification(model)
    test_targets = tests or [f'Add focused tests for {feature_title(feature)} before implementation.']
    return {
        'id': task_id,
        'epic_id': epic_id,
        'feature_id': feature.get('id'),
        'wave': index,
        'title': title,
        'branch': f'feature/{task_id.lower()}-{slug(feature_title(feature))}',
        'objective': feature.get('intended_behavior') or feature.get('summary') or title,
        'non_goals': ['Do not perform broad review/refactor cleanup outside this feature task.'],
        'context_bundle': {
            'feature_id': feature.get('id'),
            'summary': feature.get('summary', ''),
            'intended_behavior': feature.get('intended_behavior', ''),
            'entry_points': entry_points,
            'known_risks': as_list(feature.get('known_risks')),
        },
        'context_to_load': context_to_load,
        'read_set': read_set,
        'write_set': write_set,
        'dependencies': dependencies,
        'parallel_conflicts': [],
        'implementation_steps': [
            'Map current behavior and identify the smallest implementation surface.',
            'Write or update the focused failing tests listed in tests_to_write_first.',
            'Implement the minimum code needed to satisfy the tests while preserving existing behavior.',
            'Run verification_commands and update docs only when they are part of the feature surface.',
        ],
        'tests_to_write_first': test_targets,
        'tdd_plan': [
            f'Add a failing test that demonstrates {feature.get("intended_behavior") or feature_title(feature)}.',
            'Run the focused test and confirm it fails for the expected reason.',
            'Implement the smallest behavior change.',
            'Run the focused test and full verification commands.',
        ],
        'verification_commands': verification,
        'acceptance_criteria': [
            feature.get('intended_behavior') or f'{feature_title(feature)} behavior is implemented.',
            'All tests_to_write_first pass.',
            'All verification_commands pass.',
        ],
        'review_focus': ['correctness', 'tests', 'scope', 'API compatibility'],
        'rollback_notes': 'Revert this task branch or PR if verification fails or behavior expands beyond the feature objective.',
        'task_file': f'tasks/{task_id}.md',
    }


def mark_parallel_conflicts(tasks):
    for left_index, left in enumerate(tasks):
        left_paths = set(left.get('write_set', []))
        for right in tasks[left_index + 1:]:
            if left_paths.intersection(right.get('write_set', [])):
                left['parallel_conflicts'].append(right['id'])
                right['parallel_conflicts'].append(left['id'])


def build_plan(model, feature_id=None):
    features = selected_features(model, feature_id)
    epics = build_epics(features)
    feature_to_task = {
        feature.get('id'): f'TASK-{index:03d}'
        for index, feature in enumerate(features, 1)
        if feature.get('id')
    }
    tasks = [
        build_task(index, feature, model, epics[index - 1]['id'], feature_to_task)
        for index, feature in enumerate(features, 1)
    ]
    mark_parallel_conflicts(tasks)
    milestone = {
        'id': 'MILESTONE-001',
        'title': 'Feature implementation tasks',
        'epic_ids': [epic['id'] for epic in epics],
    }
    release = {
        'id': 'RELEASE-001',
        'title': 'Feature implementation release',
        'milestone_ids': [milestone['id']],
    }
    waves = [
        {
            'wave': task['wave'],
            'task_ids': [task['id']],
            'dependencies': task['dependencies'],
            'parallel_safety_rationale': 'Serialized by default until implementation tasks are proven independent.',
            'integration_order': [task['id']],
            'post_wave_verification_commands': task['verification_commands'],
        }
        for task in tasks
    ]
    return {
        'source': 'feature_task_generator.py',
        'feature_model_repo': (model.get('repo') or {}).get('name'),
        'epics': epics,
        'milestones': [milestone],
        'releases': [release],
        'tasks': tasks,
        'waves': waves,
    }


def write_csv(path, tasks):
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=TASK_COLUMNS)
        writer.writeheader()
        for task in tasks:
            writer.writerow({
                'id': task['id'],
                'epic_id': task['epic_id'],
                'wave': task['wave'],
                'title': task['title'],
                'branch': task['branch'],
                'dependencies': ';'.join(task['dependencies']),
                'context_to_load': ';'.join(task['context_to_load']),
                'read_set': ';'.join(task['read_set']),
                'write_set': ';'.join(task['write_set']),
                'verification_commands': ';'.join(task['verification_commands']),
                'task_file': task['task_file'],
            })


def task_markdown(task):
    lines = [
        f'# {task["id"]}: {task["title"]}',
        '',
        f'Epic: {task["epic_id"]}',
        f'Branch: `{task["branch"]}`',
        '',
        '## Objective',
        '',
        task['objective'],
        '',
        '## Context To Load',
        '',
        *[f'- `{item}`' for item in task['context_to_load']],
        '',
        '## Tests To Write First',
        '',
        *[f'- {item}' for item in task['tests_to_write_first']],
        '',
        '## TDD Plan',
        '',
        *[f'- {item}' for item in task['tdd_plan']],
        '',
        '## Implementation Steps',
        '',
        *[f'- {item}' for item in task['implementation_steps']],
        '',
        '## Verification Commands',
        '',
        *[f'- `{item}`' for item in task['verification_commands']],
        '',
        '## Acceptance Criteria',
        '',
        *[f'- {item}' for item in task['acceptance_criteria']],
    ]
    return '\n'.join(lines).rstrip() + '\n'


def epic_markdown(epic):
    return '\n'.join([
        f'# {epic["id"]}: {epic["title"]}',
        '',
        epic['objective'],
        '',
        '## Tasks',
        '',
        *[f'- {task_id}' for task_id in epic['task_ids']],
        '',
    ])


def write_artifacts(out: Path, plan):
    out.mkdir(parents=True, exist_ok=True)
    (out / 'tasks').mkdir(exist_ok=True)
    (out / 'epics').mkdir(exist_ok=True)
    text = json.dumps(plan, indent=2, sort_keys=True) + '\n'
    (out / 'implementation-plan.json').write_text(text, encoding='utf-8')
    (out / 'waves.json').write_text(json.dumps({'waves': plan['waves']}, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    write_csv(out / 'tasks.csv', plan['tasks'])
    for task in plan['tasks']:
        (out / task['task_file']).write_text(task_markdown(task), encoding='utf-8')
    for epic in plan['epics']:
        (out / 'epics' / f'{epic["id"]}.md').write_text(epic_markdown(epic), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description='Generate feature implementation tasks from a feature model.')
    parser.add_argument('feature_model')
    parser.add_argument('--output-dir', default='.')
    parser.add_argument('--feature')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    model = json.loads(Path(args.feature_model).read_text(encoding='utf-8'))
    plan = build_plan(model, args.feature)
    if args.dry_run:
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 0
    out = Path(args.output_dir)
    write_artifacts(out, plan)
    print(out / 'implementation-plan.json')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
