#!/usr/bin/env python3
import argparse, json
from pathlib import Path
from datetime import datetime, timezone

def main():
    ap=argparse.ArgumentParser(description='Build conservative feature model skeleton from repo inventory.')
    ap.add_argument('inventory'); ap.add_argument('--analysis'); ap.add_argument('--output', default='feature-model.json'); ap.add_argument('--dry-run', action='store_true')
    args=ap.parse_args(); inv=json.loads(Path(args.inventory).read_text())
    repo=inv.get('repo',{})
    model={'repo':{'name':repo.get('name','unknown'),'root':repo.get('root','.'),'analyzed_at':datetime.now(timezone.utc).isoformat(),'primary_languages':[],'package_managers':inv.get('package_managers',[]),'test_commands':[],'ci_files':inv.get('ci_files',[])},'codebase_summary':'Conservative skeleton generated from inventory; refine with feature-model-builder.','architecture':{'components':[{'id':'COMP-REPO','name':'Repository','description':'Initial repository component','paths':inv.get('source_roots',[]),'entry_points':[],'dependencies':[]}]},'features':[{'id':'FEATURE-REPO-STRUCTURE','name':'Repository structure','category':'internal-platform','summary':'Initial low-confidence feature inferred from inventory.','intended_behavior':'Repository should build/test according to discovered tooling.','user_or_system_value':'Provides base for later feature modeling.','entry_points':[],'code_paths':inv.get('source_roots',[]),'docs':inv.get('docs',[])[:10],'tests':inv.get('tests',[])[:10],'data_models':inv.get('schemas',[]),'related_components':['COMP-REPO'],'related_features':[],'known_risks':['Heuristic skeleton requires human/Codex refinement.'],'doc_code_mismatches':[],'confidence':'low'}],'unknowns':['Run codebase-deep-analyzer for evidence-backed refinement.'],'evidence':[{'claim':'Inventory was generated','files':inv.get('docs',[])[:5]+inv.get('manifests',[])[:5],'notes':'Heuristic evidence only.'}]}
    text=json.dumps(model,indent=2,sort_keys=True)+'\n'
    if args.dry_run: print(text); return 0
    out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(text); Path(str(out).replace('.json','.md')).write_text('# Feature Model\n\nGenerated skeleton. Refine with feature-model-builder.\n'); print(out); return 0
if __name__=='__main__': raise SystemExit(main())
