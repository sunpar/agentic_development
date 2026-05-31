#!/usr/bin/env python3
"""Aggregate codebase review orchestration run summaries."""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import shlex
from pathlib import Path

ORCHESTRATOR = Path.home() / '.codex/codebase-review-factory/scripts/orchestrate_slice_waves.py'


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


SLICE_DETAIL_KEYS = (
    'branch',
    'worktree',
    'pr_number',
    'head_sha',
    'error',
    'review_requested_at',
    'review_gate_required_at',
    'review_requests',
    'review_repair_attempts',
    'merged_at',
)


def slice_summary(slice_id, item):
    summary = {
        'id': slice_id,
        'status': item.get('status'),
    }
    for key in SLICE_DETAIL_KEYS:
        if key in item:
            summary[key] = item.get(key)
    return summary


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
        slice_summary(slice_id, item)
        for slice_id, item in sorted_mapping_items(state.get('slices'))
    ]
    return {
        'generated_at': state.get('updated_at') or state.get('created_at'),
        'repo': state.get('repo'),
        'run_dir': state.get('run_dir') or str(run_dir),
        'slice_plan': state.get('slice_plan'),
        'waves_path': state.get('waves_path'),
        'slice_plan_sha256': state.get('slice_plan_sha256'),
        'waves_sha256': state.get('waves_sha256'),
        'slice_branches': state.get('slice_branches', {}),
        'execution_options': dict(state.get('execution_options') or {}),
        'totals': {
            'waves': len(waves),
            'slices': len(slices),
            'by_status': status_counts(slices),
        },
        'waves': waves,
        'slices': slices,
    }


def unique_sorted(values):
    return sorted({str(value) for value in values if value})


def slice_by_id(slices):
    return {
        str(item.get('id')): item
        for item in slices
        if isinstance(item, dict) and item.get('id')
    }


def fill_missing(base, fallback, keys):
    merged = dict(base)
    for key in keys:
        if merged.get(key) in (None, '', []) or merged.get(key) == {}:
            value = fallback.get(key)
            if value not in (None, '', []) and value != {}:
                merged[key] = value
    return merged


def merge_slice_details(summary_slices, state_slices):
    state_by_id = slice_by_id(state_slices)
    merged = []
    seen = set()
    for item in summary_slices:
        slice_id = str(item.get('id') or '')
        seen.add(slice_id)
        merged.append(fill_missing(item, state_by_id.get(slice_id, {}), SLICE_DETAIL_KEYS))
    for slice_id, item in state_by_id.items():
        if slice_id not in seen:
            merged.append(item)
    return merged


def enrich_summary_from_state(summary, state_summary):
    enriched = dict(summary)
    for key in ('slice_plan', 'waves_path', 'slice_plan_sha256', 'waves_sha256', 'slice_branches', 'repo', 'run_dir', 'execution_options'):
        if enriched.get(key) in (None, '', [], {}):
            value = state_summary.get(key)
            if value not in (None, '', [], {}):
                enriched[key] = value
    enriched['slices'] = merge_slice_details(
        [item for item in enriched.get('slices') or [] if isinstance(item, dict)],
        [item for item in state_summary.get('slices') or [] if isinstance(item, dict)],
    )
    enriched['totals'] = {
        **dict(enriched.get('totals') or {}),
        'waves': len([item for item in enriched.get('waves') or [] if isinstance(item, dict)]),
        'slices': len(enriched['slices']),
        'by_status': status_counts(enriched['slices']),
    }
    return enriched


def common_worktree_dir(slices):
    parents = unique_sorted(str(Path(item['worktree']).parent) for item in slices if item.get('worktree'))
    return parents[0] if len(parents) == 1 else None


def shell_join(parts):
    return ' '.join(shlex.quote(str(part)) for part in parts if part is not None and str(part) != '')


def execution_resume_args(summary):
    options = summary.get('execution_options') or {}
    args = []
    if options.get('max_parallel') is not None:
        args += ['--max-parallel', options.get('max_parallel')]
    for command in options.get('setup_commands') or []:
        args += ['--setup-command', command]
    if options.get('allow_pr'):
        args.append('--allow-pr')
    if options.get('allow_review_request'):
        args.append('--allow-review-request')
        if options.get('review_agents'):
            args += ['--review-agents', options.get('review_agents')]
    if options.get('allow_merge'):
        args.append('--allow-merge')
        if options.get('merge_method'):
            args += ['--merge-method', options.get('merge_method')]
        if options.get('delete_branch'):
            args.append('--delete-branch')
    if options.get('no_merge'):
        args.append('--no-merge')
    return args


def resume_commands(summary, failed_slices, slices):
    slice_plan = summary.get('slice_plan')
    waves_path = summary.get('waves_path')
    run_dir = summary.get('run_dir')
    if not slice_plan or not waves_path or not run_dir or not failed_slices:
        return []
    options = summary.get('execution_options') or {}
    worktree_dir = options.get('worktree_dir') or common_worktree_dir(slices)
    cmd = [
        'python3',
        ORCHESTRATOR,
        slice_plan,
        waves_path,
        '--run-dir',
        run_dir,
    ]
    if worktree_dir:
        cmd += ['--worktree-dir', worktree_dir]
    cmd += execution_resume_args(summary)
    cmd += ['--resume', '--reuse-worktrees']
    command = shell_join(cmd)
    if summary.get('repo'):
        command = f"cd {shlex.quote(str(summary['repo']))} && {command}"
    return [command]


def pr_numbers(slices):
    return sorted({
        int(item['pr_number'])
        for item in slices
        if isinstance(item, dict) and item.get('pr_number') is not None
    })


def review_request_agents_for_slice(item):
    requests = item.get('review_requests')
    if isinstance(requests, dict):
        agents = requests.get('agents')
        if isinstance(agents, dict):
            return [
                str(agent)
                for agent, record in agents.items()
                if agent and isinstance(record, dict) and record.get('status') == 'completed'
            ]
        if isinstance(agents, list):
            return [
                str(agent.get('agent') if isinstance(agent, dict) else agent)
                for agent in agents
                if agent and (not isinstance(agent, dict) or agent.get('returncode') in (0, None))
            ]
        return [''] if requests.get('requested_at') else []
    if isinstance(requests, list):
        agents = []
        for request in requests:
            if isinstance(request, dict):
                if request.get('returncode') in (0, None) and request.get('status', 'completed') == 'completed':
                    agents.append(str(request.get('agent') or ''))
            elif request:
                agents.append(str(request))
        return agents
    return [''] if item.get('review_requested_at') else []


def review_request_count(slices):
    return sum(len(review_request_agents_for_slice(item)) for item in slices if isinstance(item, dict))


def review_request_agents(slices):
    agents = []
    for item in slices:
        if isinstance(item, dict):
            agents.extend(review_request_agents_for_slice(item))
    return unique_sorted(agent for agent in agents if agent)


def merged_slice_count(slices):
    return sum(
        1
        for item in slices
        if isinstance(item, dict) and str(item.get('status') or '') == 'merged'
    )


def load_run_summary(run_dir):
    summary_path = run_dir / 'run-summary.json'
    state_path = run_dir / 'run-state.json'
    if summary_path.exists():
        summary = load_json(summary_path)
        source = summary_path
        if state_path.exists():
            try:
                summary = enrich_summary_from_state(summary, summary_from_state(run_dir))
            except (OSError, json.JSONDecodeError, ValueError):
                pass
    elif state_path.exists():
        summary = summary_from_state(run_dir)
        source = state_path
    else:
        return None

    slices = [item for item in summary.get('slices') or [] if isinstance(item, dict)]
    prs = pr_numbers(slices)
    reviews = review_request_count(slices)
    merges = merged_slice_count(slices)
    failed_slices = [
        str(item.get('id'))
        for item in slices
        if str(item.get('status') or '') in {'failed', 'error'}
    ]
    totals = summary.get('totals') or {}
    if not totals.get('slices') or not totals.get('by_status'):
        totals = {
            **dict(totals),
            'waves': len([item for item in summary.get('waves') or [] if isinstance(item, dict)]),
            'slices': len(slices),
            'by_status': status_counts(slices),
        }
    return {
        'name': run_dir.name,
        'run_dir': str(run_dir),
        'repo': summary.get('repo'),
        'generated_at': summary.get('generated_at'),
        'summary_source': str(source),
        'slice_plan': summary.get('slice_plan'),
        'waves_path': summary.get('waves_path'),
        'totals': {
            'waves': int(totals.get('waves') or 0),
            'slices': int(totals.get('slices') or 0),
            'by_status': dict(totals.get('by_status') or {}),
        },
        'failed_slices': failed_slices,
        'branches': unique_sorted(item.get('branch') for item in slices),
        'worktrees': unique_sorted(item.get('worktree') for item in slices),
        'pr_numbers': prs,
        'review_request_count': reviews,
        'review_request_agents': review_request_agents(slices),
        'merged_slices': merges,
        'resume_commands': resume_commands(summary, failed_slices, slices),
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
            'prs': sum(len(run['pr_numbers']) for run in runs),
            'review_requests': sum(run['review_request_count'] for run in runs),
            'merged_slices': sum(run['merged_slices'] for run in runs),
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
        f'- PRs: {aggregate["totals"]["prs"]}',
        f'- Review requests: {aggregate["totals"]["review_requests"]}',
        f'- Merged slices: {aggregate["totals"]["merged_slices"]}',
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
        if run['branches']:
            line += '; branches=' + ', '.join(run['branches'])
        if run['worktrees']:
            line += '; worktrees=' + ', '.join(run['worktrees'])
        if run['pr_numbers']:
            line += '; PRs=' + ', '.join(f'#{number}' for number in run['pr_numbers'])
        if run['review_request_count']:
            line += f'; review_requests={run["review_request_count"]}'
        if run['merged_slices']:
            line += f'; merged={run["merged_slices"]}'
        lines.append(line)
        for command in run.get('resume_commands') or []:
            lines.append(f'  - Resume: `{command}`')
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
