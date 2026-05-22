#!/usr/bin/env python3
import argparse, json, subprocess, time
def main():
    ap=argparse.ArgumentParser(description='Poll PR review comments.'); ap.add_argument('--timeout',type=int,default=600); ap.add_argument('--output-json',default='review-comments.json'); ap.add_argument('--output-md',default='review-comments.md'); ap.add_argument('--dry-run',action='store_true'); args=ap.parse_args()
    if args.dry_run:
        print(f'would poll PR reviews/comments for up to {args.timeout}s and write {args.output_json}, {args.output_md}')
        return 0
    end=time.time()+args.timeout; data={'comments':[],'status':'timeout'}
    while time.time()<end:
        p=subprocess.run(['gh','pr','view','--json','comments,reviews,url'],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        if p.returncode==0: data=json.loads(p.stdout); data['status']='ok'; break
        time.sleep(10)
    open(args.output_json,'w').write(json.dumps(data,indent=2)+'\n'); open(args.output_md,'w').write('# Review Comments\n\nSee JSON output.\n'); print(args.output_json); return 0
if __name__=='__main__': raise SystemExit(main())
