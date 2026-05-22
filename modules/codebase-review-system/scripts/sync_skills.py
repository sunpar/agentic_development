#!/usr/bin/env python3
import argparse, os, shutil
from pathlib import Path
from datetime import datetime

HOME = Path.home()
SRC = HOME / '.codex' / 'codebase-review-factory' / 'skills'
DEST_DIR = HOME / '.agents' / 'skills'
DEST = DEST_DIR / 'codebase-review-factory'

def main():
    ap = argparse.ArgumentParser(description='Sync codebase-review-factory skills into ~/.agents/skills.')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    print(f'source={SRC}')
    print(f'dest={DEST}')
    if args.dry_run:
        print('[dry-run] would ensure dest dir and symlink')
        return 0
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    if DEST.exists() or DEST.is_symlink():
        if DEST.is_symlink() and Path(os.readlink(DEST)) == SRC:
            print('symlink already correct')
            return 0
        backup = DEST.with_name(DEST.name + '.bak-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
        if DEST.is_dir() and not DEST.is_symlink():
            shutil.copytree(DEST, backup)
        else:
            shutil.copy2(DEST, backup, follow_symlinks=False)
        if DEST.is_dir() and not DEST.is_symlink():
            shutil.rmtree(DEST)
        else:
            DEST.unlink()
        print(f'backed up existing dest to {backup}')
    os.symlink(SRC, DEST, target_is_directory=True)
    print('created symlink')
    return 0
if __name__ == '__main__': raise SystemExit(main())
