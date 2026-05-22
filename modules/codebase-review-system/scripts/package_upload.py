#!/usr/bin/env python3
import argparse
import os
import shutil
import tempfile
import zipfile
from pathlib import Path


EXCLUDE_NAMES = {'.DS_Store', '__pycache__', '.pytest_cache'}
FACTORY = Path(__file__).resolve().parents[1]
HOME = Path.home()
DEFAULT_PATHS = [
    HOME/'.codex'/'manual-workflows',
    HOME/'.codex'/'skills'/'manual-workflow-loader',
    FACTORY,
]
AGENTS = [
    'codebase-analyst.toml',
    'feature-modeler.toml',
    'slice-generator.toml',
    'wave-planner.toml',
    'slice-reviewer.toml',
    'slice-refactorer.toml',
    'wave-orchestrator.toml',
    'pr-review-manager.toml',
    'ci-debugger.toml',
]


def excluded(path):
    name = path.name
    return name in EXCLUDE_NAMES or '.bak-' in name or '.bak.' in name


def copy_tree(src, dst):
    if src.is_symlink():
        target = src.resolve()
        if target.is_dir():
            shutil.copytree(target, dst, ignore=ignore)
        elif target.exists():
            shutil.copy2(target, dst)
        return
    if src.is_dir():
        shutil.copytree(src, dst, ignore=ignore)
    elif src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def ignore(directory, names):
    return {name for name in names if excluded(Path(directory)/name)}


def stage_path(src, staging):
    if not src.exists() and not src.is_symlink():
        return False
    rel = Path(*src.parts[1:]) if src.is_absolute() else src
    dst = staging/rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    copy_tree(src, dst)
    return True


def write_manifest(staging, included, missing):
    manifest = staging/'TOUCHED_MANIFEST.txt'
    lines = [
        'Included touched paths:',
        *[f'- {p}' for p in included],
        '',
        'Missing paths:',
        *[f'- {p}' for p in missing],
        '',
        'Excluded patterns:',
        '- *.bak-*',
        '- *.bak.*',
        '- __pycache__',
        '- .pytest_cache',
        '- .DS_Store',
        '',
        'Skill discovery symlink to recreate after extraction:',
        '- ~/.agents/skills/codebase-review-factory -> ~/.codex/codebase-review-factory/skills',
        '',
        'Removed skill directories not included because they no longer exist:',
        '- ~/.codex/skills/deslop',
        '- ~/.codex/skills/personal-refactor',
        '- ~/.codex/skills/keep-codex-fast',
        '- ~/.codex/skills/gh-resolve-review-comments',
    ]
    manifest.write_text('\n'.join(lines) + '\n')


def zip_dir(staging, output):
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for path in staging.rglob('*'):
            if path.is_file() and not excluded(path):
                zf.write(path, path.relative_to(staging))


def main():
    ap = argparse.ArgumentParser(description='Create a clean upload zip of touched Codex factory assets.')
    ap.add_argument('--output', default=str(HOME/'codex-review-factory-upload.zip'))
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    paths = list(DEFAULT_PATHS) + [HOME/'.codex'/'agents'/name for name in AGENTS]
    included = [str(p) for p in paths if p.exists() or p.is_symlink()]
    missing = [str(p) for p in paths if not p.exists() and not p.is_symlink()]
    if args.dry_run:
        print('would include:')
        for p in included:
            print(p)
        if missing:
            print('missing:')
            for p in missing:
                print(p)
        return 0

    output = Path(args.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='codex-review-factory-upload-') as td:
        staging = Path(td)
        for src in paths:
            stage_path(src, staging)
        write_manifest(staging, included, missing)
        zip_dir(staging, output)
    print(output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
