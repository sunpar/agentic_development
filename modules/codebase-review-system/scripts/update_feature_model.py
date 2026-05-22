#!/usr/bin/env python3
import argparse, json
from pathlib import Path
def main():
    ap=argparse.ArgumentParser(description='Update feature model metadata after runs.'); ap.add_argument('feature_model'); ap.add_argument('--status-note',default='updated'); ap.add_argument('--dry-run',action='store_true'); args=ap.parse_args(); data=json.loads(Path(args.feature_model).read_text()); data.setdefault('unknowns',[]).append(args.status_note)
    if args.dry_run: print(json.dumps(data,indent=2)); return 0
    Path(args.feature_model).write_text(json.dumps(data,indent=2,sort_keys=True)+'\n'); return 0
if __name__=='__main__': raise SystemExit(main())
