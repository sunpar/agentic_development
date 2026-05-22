#!/usr/bin/env python3
import argparse, re, sys
from pathlib import Path
PATTERNS=[('apology/as-requested', re.compile(r'\b(as requested|sorry|apologize)\b',re.I)),('ai-prose', re.compile(r'\b(delve|seamlessly|robust|comprehensive solution)\b',re.I)),('vague-todo', re.compile(r'TODO:?( fix| improve| handle)?$',re.I)),('generic-comment', re.compile(r'#\s*(This function|This method|Loop through|Set the)\b',re.I))]
def scan(path):
    findings=[]
    try: lines=Path(path).read_text(errors='ignore').splitlines()
    except Exception as e: return [(path,0,'read-error',str(e))]
    for i,line in enumerate(lines,1):
        for name,rx in PATTERNS:
            if rx.search(line): findings.append((path,i,name,line.strip()))
    return findings
def main():
    ap=argparse.ArgumentParser(description='Warning-first slop check.'); ap.add_argument('paths',nargs='*',default=['.']); ap.add_argument('--strict',action='store_true'); ap.add_argument('--dry-run',action='store_true'); args=ap.parse_args(); findings=[]
    for p in args.paths:
        pp=Path(p)
        files=[pp] if pp.is_file() else [x for x in pp.rglob('*') if x.is_file() and x.suffix in ['.py','.js','.ts','.tsx','.md','.txt']]
        for f in files: findings+=scan(f)
    for f in findings: print(f'{f[0]}:{f[1]} {f[2]} {f[3]}')
    strict=args.strict or bool(__import__('os').environ.get('CODEBASE_REVIEW_FACTORY_STRICT'))
    return 1 if strict and findings else 0
if __name__=='__main__': raise SystemExit(main())
