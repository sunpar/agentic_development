#!/usr/bin/env python3
import argparse, sys
from factory_common import load_json, required, fail_or_print
REQ_REPO=['name','root','analyzed_at','primary_languages','package_managers','test_commands','ci_files']
REQ_FEATURE=['id','name','category','summary','intended_behavior','user_or_system_value','entry_points','code_paths','docs','tests','data_models','related_components','related_features','known_risks','doc_code_mismatches','confidence']

def validate(data):
    errors=[]; errors+=required(data,['repo','codebase_summary','architecture','features','unknowns','evidence'])
    if 'repo' in data: errors+=required(data['repo'],REQ_REPO,'repo')
    ids=set()
    for i,f in enumerate(data.get('features',[]) if isinstance(data.get('features'),list) else []):
        errors+=required(f,REQ_FEATURE,f'features[{i}]')
        fid=f.get('id','')
        if not fid or ' ' in fid: errors.append(f'features[{i}].id must be nonempty and space-free')
        if fid in ids: errors.append(f'duplicate feature id {fid}')
        ids.add(fid)
        if f.get('confidence') not in ['high','medium','low']: errors.append(f'{fid}.confidence invalid')
    if not data.get('evidence'): errors.append('evidence must not be empty')
    return errors

def main():
    ap=argparse.ArgumentParser(description='Validate feature model.')
    ap.add_argument('path'); ap.add_argument('--json', action='store_true')
    args=ap.parse_args(); return fail_or_print(validate(load_json(args.path)), args.json)
if __name__=='__main__': raise SystemExit(main())
