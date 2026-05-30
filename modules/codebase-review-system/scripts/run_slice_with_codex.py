#!/usr/bin/env python3
import argparse, json, shlex, shutil, subprocess, sys
from pathlib import Path
MODEL_ARGS=['--model','gpt-5.5','-c','model_reasoning_effort="xhigh"']

def safe_extra_args(value):
    args=shlex.split(value) if value else []
    banned={'--model','-m','--sandbox','-s','--dangerously-bypass-approvals-and-sandbox','--dangerously-bypass-hook-trust'}
    for i,arg in enumerate(args):
        if arg in banned or arg.startswith('--model=') or arg.startswith('--sandbox='):
            raise SystemExit(f'unsafe --codex-extra-args token blocked: {arg}')
        if arg in {'-c','--config'}:
            nxt=args[i+1] if i+1 < len(args) else ''
            if any(k in nxt for k in ['model','model_reasoning_effort','sandbox','danger']):
                raise SystemExit(f'unsafe --codex-extra-args config blocked: {nxt}')
    return args

def find_slice(plan, slice_id):
    for item in plan.get('slices', []):
        if item.get('id') == slice_id:
            return item
    return None

def main():
    ap=argparse.ArgumentParser(description='Run or print Codex prompt for one slice.'); ap.add_argument('slice_plan'); ap.add_argument('slice_id'); ap.add_argument('--codex-profile'); ap.add_argument('--codex-agent'); ap.add_argument('--codex-extra-args', default=''); ap.add_argument('--dry-run',action='store_true'); args=ap.parse_args()
    plan=json.loads(Path(args.slice_plan).read_text())
    s=find_slice(plan, args.slice_id)
    if not s:
        print(f'slice {args.slice_id} not found in {args.slice_plan}', file=sys.stderr)
        return 2
    prompt=f"Use slice-review-workflow and slice-refactor-workflow for {s['id']}. Stay within allowed edit scope: {s['files_allowed_to_edit']}. Verify with: {s['verification_commands']}."
    cmd=['codex','exec'] + MODEL_ARGS
    if args.codex_profile: cmd += ['--profile',args.codex_profile]
    cmd += safe_extra_args(args.codex_extra_args)
    cmd.append(prompt)
    if args.dry_run or not shutil.which('codex'):
        print(' '.join(shlex.quote(c) for c in cmd))
        print(prompt)
        return 0
    return subprocess.run(cmd).returncode
if __name__=='__main__': raise SystemExit(main())
