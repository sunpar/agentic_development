#!/usr/bin/env python3
import argparse, subprocess
def run(c): print('+',' '.join(c)); return subprocess.run(c).returncode
def main():
    ap=argparse.ArgumentParser(description='Commit, push, and create/update PR safely.'); ap.add_argument('--message',default='Update slice'); ap.add_argument('--title',default='[codebase-review] Slice update'); ap.add_argument('--body',default='Slice-scoped update.'); ap.add_argument('--paths',nargs='+',help='In-scope paths to stage'); ap.add_argument('--dry-run',action='store_true'); args=ap.parse_args()
    if not args.paths:
        print('refusing to stage without --paths; pass only in-scope files')
        return 2
    cmds=[['git','status','--short'],['git','diff','--check'],['git','add','--']+args.paths,['git','commit','-m',args.message],['git','push','-u','origin','HEAD'],['gh','pr','create','--fill','--title',args.title,'--body',args.body]]
    if args.dry_run:
        for c in cmds: print(' '.join(c))
        return 0
    for c in cmds:
        rc=run(c)
        if rc: return rc
    return 0
if __name__=='__main__': raise SystemExit(main())
