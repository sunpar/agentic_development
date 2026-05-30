#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


PACKAGE_BY_MANIFEST = {
    'package.json': 'npm',
    'package-lock.json': 'npm',
    'pnpm-lock.yaml': 'pnpm',
    'yarn.lock': 'yarn',
    'pyproject.toml': 'python',
    'requirements.txt': 'python',
    'requirements-dev.txt': 'python',
    'uv.lock': 'python',
    'Cargo.toml': 'cargo',
    'go.mod': 'go',
}

LANGUAGE_BY_PACKAGE = {
    'npm': 'JavaScript/TypeScript',
    'pnpm': 'JavaScript/TypeScript',
    'yarn': 'JavaScript/TypeScript',
    'python': 'Python',
    'cargo': 'Rust',
    'go': 'Go',
}

TEST_COMMAND_BY_PACKAGE = {
    'npm': 'npm test',
    'pnpm': 'pnpm test',
    'yarn': 'yarn test',
    'python': 'python -m pytest',
    'cargo': 'cargo test',
    'go': 'go test ./...',
}


def unique_in_order(values):
    seen = set()
    result = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def package_tools(inv):
    declared = inv.get('package_managers') or []
    inferred = [
        PACKAGE_BY_MANIFEST.get(Path(manifest).name)
        for manifest in inv.get('manifests', [])
    ]
    return unique_in_order([*declared, *inferred])


def primary_languages(tools):
    return unique_in_order(LANGUAGE_BY_PACKAGE.get(tool) for tool in tools)


def test_commands(tools):
    return unique_in_order(TEST_COMMAND_BY_PACKAGE.get(tool) for tool in tools)


def build_model(inv):
    repo = inv.get('repo', {})
    tools = package_tools(inv)
    source_roots = inv.get('source_roots', [])
    docs = inv.get('docs', [])
    tests = inv.get('tests', [])
    schemas = inv.get('schemas', [])
    manifests = inv.get('manifests', [])
    return {
        'repo': {
            'name': repo.get('name', 'unknown'),
            'root': repo.get('root', '.'),
            'analyzed_at': datetime.now(timezone.utc).isoformat(),
            'primary_languages': primary_languages(tools),
            'package_managers': tools,
            'test_commands': test_commands(tools),
            'ci_files': inv.get('ci_files', []),
        },
        'codebase_summary': 'Conservative skeleton generated from inventory; refine with feature-model-builder.',
        'architecture': {
            'components': [{
                'id': 'COMP-REPO',
                'name': 'Repository',
                'description': 'Initial repository component',
                'paths': source_roots,
                'entry_points': [],
                'dependencies': [],
            }],
        },
        'features': [{
            'id': 'FEATURE-REPO-STRUCTURE',
            'name': 'Repository structure',
            'category': 'internal-platform',
            'summary': 'Initial low-confidence feature inferred from inventory.',
            'intended_behavior': 'Repository should build/test according to discovered tooling.',
            'user_or_system_value': 'Provides base for later feature modeling.',
            'entry_points': [],
            'code_paths': source_roots,
            'docs': docs[:10],
            'tests': tests[:10],
            'data_models': schemas,
            'related_components': ['COMP-REPO'],
            'related_features': [],
            'known_risks': ['Heuristic skeleton requires human/Codex refinement.'],
            'doc_code_mismatches': [],
            'confidence': 'low',
        }],
        'unknowns': ['Run codebase-deep-analyzer for evidence-backed refinement.'],
        'evidence': [{
            'claim': 'Inventory was generated',
            'files': docs[:5] + manifests[:5],
            'notes': 'Heuristic evidence only.',
        }],
    }


def main():
    parser = argparse.ArgumentParser(description='Build conservative feature model skeleton from repo inventory.')
    parser.add_argument('inventory')
    parser.add_argument('--analysis')
    parser.add_argument('--output', default='feature-model.json')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    inv = json.loads(Path(args.inventory).read_text(encoding='utf-8'))
    text = json.dumps(build_model(inv), indent=2, sort_keys=True) + '\n'
    if args.dry_run:
        print(text)
        return 0

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding='utf-8')
    Path(str(out).replace('.json', '.md')).write_text(
        '# Feature Model\n\nGenerated skeleton. Refine with feature-model-builder.\n',
        encoding='utf-8',
    )
    print(out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
