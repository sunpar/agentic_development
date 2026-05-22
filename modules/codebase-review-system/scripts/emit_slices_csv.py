#!/usr/bin/env python3
import argparse, csv, json
from pathlib import Path
COLS=['id','feature_id','wave','title','slice_type','branch','dependencies','files_to_read','docs_to_read','tests_to_read','files_allowed_to_edit','verification_commands','risk','slice_file']
def main():
    ap=argparse.ArgumentParser(description='Emit slices CSV.'); ap.add_argument('slice_plan'); ap.add_argument('--output', default='slices.csv'); ap.add_argument('--dry-run', action='store_true'); args=ap.parse_args()
    plan=json.loads(Path(args.slice_plan).read_text()); waves={sid:w.get('wave') for w in plan.get('waves',[]) for sid in w.get('slice_ids',[])}
    rows=[]
    for s in plan.get('slices',[]): rows.append({c: (';'.join(s.get(c,[])) if isinstance(s.get(c),list) else s.get(c,'')) for c in COLS} | {'wave':waves.get(s.get('id'),''),'slice_file':f'slices/{s.get("id")}.md'})
    if args.dry_run: print(rows); return 0
    with open(args.output,'w',newline='') as f: w=csv.DictWriter(f,fieldnames=COLS); w.writeheader(); w.writerows(rows)
    print(args.output); return 0
if __name__=='__main__': raise SystemExit(main())
