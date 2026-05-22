#!/usr/bin/env python3
import argparse, subprocess
def main():
    ap=argparse.ArgumentParser(description='Request Codex/Copilot PR review.'); ap.add_argument('--provider',choices=['codex','copilot','both'],default='codex'); ap.add_argument('--focus',default='correctness, tests, API compatibility, slice scope'); ap.add_argument('--dry-run',action='store_true'); args=ap.parse_args()
    if args.provider in ['codex','both']:
        cmd=['gh','pr','comment','--body',f'@codex review\n\nFocus: {args.focus}']; print(' '.join(cmd));
        if not args.dry_run and subprocess.run(cmd).returncode: return 1
    if args.provider in ['copilot','both']: print('Copilot review request availability is repo-dependent; use gh pr edit --add-reviewer @copilot when supported.')
    return 0
if __name__=='__main__': raise SystemExit(main())
