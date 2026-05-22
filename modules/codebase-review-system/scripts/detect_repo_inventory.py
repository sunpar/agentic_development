#!/usr/bin/env python3
import argparse, fnmatch, json, os
from pathlib import Path

def matches(path, globs):
    s=str(path)
    return any(fnmatch.fnmatch(s,g) for g in globs)

def main():
    ap=argparse.ArgumentParser(description='Detect repository inventory.')
    ap.add_argument('--output', default='docs/agentic-system/repo-inventory.json')
    ap.add_argument('--include', action='append', default=[])
    ap.add_argument('--exclude', action='append', default=['.git/**','node_modules/**','.venv/**','dist/**','build/**'])
    ap.add_argument('--dry-run', action='store_true')
    args=ap.parse_args()
    root=Path.cwd()
    files=[]
    for p in root.rglob('*'):
        if not p.is_file(): continue
        rel=p.relative_to(root)
        if args.include and not matches(rel,args.include): continue
        if matches(rel,args.exclude): continue
        files.append(str(rel))
    inv={'repo':{'name':root.name,'root':str(root)},'docs':[f for f in files if f.lower().endswith(('.md','.rst','.txt'))], 'source_roots':[d for d in ['src','app','lib','server','backend','frontend','packages'] if (root/d).exists()], 'tests':[f for f in files if 'test' in f.lower() or f.startswith('tests/')], 'manifests':[f for f in files if Path(f).name in ['package.json','pyproject.toml','Cargo.toml','go.mod','Makefile','justfile','Taskfile.yml']], 'ci_files':[f for f in files if f.startswith('.github/workflows/')], 'package_managers':[], 'frameworks':[], 'generated':[f for f in files if 'generated' in f.lower()], 'schemas':[f for f in files if 'schema' in f.lower()], 'migrations':[f for f in files if 'migration' in f.lower() or 'migrations/' in f], 'apis':[f for f in files if 'api' in f.lower()], 'clis':[f for f in files if 'cli' in f.lower()], 'jobs':[f for f in files if 'job' in f.lower() or 'worker' in f.lower()], 'config':[f for f in files if Path(f).suffix in ['.toml','.yaml','.yml','.json','.ini']]}
    text=json.dumps(inv,indent=2,sort_keys=True)+'\n'
    if args.dry_run: print(text); return 0
    out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(text); print(out); return 0
if __name__=='__main__': raise SystemExit(main())
