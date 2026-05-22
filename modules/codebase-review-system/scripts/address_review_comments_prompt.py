#!/usr/bin/env python3
import argparse, json
def main():
    ap=argparse.ArgumentParser(description='Create Codex prompt from review comments JSON.'); ap.add_argument('comments_json'); ap.add_argument('--slice-id'); args=ap.parse_args(); data=json.load(open(args.comments_json))
    print(f"Fix only in-scope must-fix/should-fix review comments for {args.slice_id or 'this slice'}. Verify each comment against code, apply valid fixes, explain invalid/out-of-scope items, commit and push follow-ups, and reply with evidence. Comments JSON: {json.dumps(data)[:4000]}")
    return 0
if __name__=='__main__': raise SystemExit(main())
