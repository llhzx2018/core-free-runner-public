#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, importlib.util, json
from pathlib import Path

HERE=Path(__file__).resolve().parent
VERSION='2.21.20'
SOURCE_VERSION='2.21.19'
SCHEMA='2026080902'
GATE_ONLY_FILES={'.gitignore','CHANGELOG.md','DEPLOY-HERE.txt','FULL-PACKAGE-NOTES.txt','README.md','UPGRADE-V2.txt','robots.txt'}
LEGACY_EXTENSION_ZIP='VF-Start-Browser-Extension.zip'

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None: raise SystemExit(f'cannot load {path}')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
base=load('p01_base_v22120',HERE/'p01-build-release.py')
v2=load('p01_atomic_v22120',HERE/'p01-build-release-v2.py')
def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def runtime_boundary(files):
    return {k:v for k,v in files.items() if k!='release-manifest.json' and k not in GATE_ONLY_FILES and k!=LEGACY_EXTENSION_ZIP}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--candidate',required=True);ap.add_argument('--production',required=True);ap.add_argument('--out',required=True);ap.add_argument('--candidate-commit',required=True);ap.add_argument('--candidate-tree',required=True);ap.add_argument('--production-commit',required=True);a=ap.parse_args()
    cand=Path(a.candidate).resolve();prod=Path(a.production).resolve();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    td=base.collect(cand);sd=base.collect(prod)
    if td.get('VERSION.txt',b'').strip()!=VERSION.encode():raise SystemExit('candidate VERSION mismatch')
    if sd.get('VERSION.txt',b'').strip()!=SOURCE_VERSION.encode():raise SystemExit('production VERSION mismatch')
    tr=runtime_boundary(td);sr=runtime_boundary(sd)
    changed=sorted(k for k in set(tr)&set(sr) if sha(tr[k])!=sha(sr[k]));added=sorted(set(tr)-set(sr));removed=sorted(set(sr)-set(tr))
    expected_added=['assets/sidebar-refinement.css']
    required_changed={'VERSION.txt','app/bootstrap.php','assets/reference-ui.js','index.php'}
    if added!=expected_added:raise SystemExit(f'unexpected runtime added: {added}')
    if removed:raise SystemExit(f'unexpected runtime removed: {removed}')
    if not required_changed.issubset(set(changed)):raise SystemExit(f'missing expected runtime changes: {sorted(required_changed-set(changed))}')
    ext=json.loads(td['browser-extension/manifest.json'].decode())
    if str(ext.get('version'))!='1.6.4':raise SystemExit('browser extension version drift')
    rm=dict(json.loads(td.get('release-manifest.json',b'{}').decode() or '{}'))
    rm.update({'project':'VF Start','project_id':'P01','project_slug':'vf-start','version':VERSION,'source_version':SOURCE_VERSION,'release_type':'formal-artifact-candidate-gate','stage':'FORMAL_ARTIFACT_CANDIDATE_GATE','deployable':True,'release_authorized':False,'source_commit':a.candidate_commit,'source_tree':a.candidate_tree,'production_source_commit':a.production_commit,'schema_version':SCHEMA,'schema_change':False,'schema_migrations':[],'runtime_data_included':False,'seed_user_business_data_included':False,'runtime_hashed_file_count':len(tr),'runtime_files':{k:sha(v) for k,v in sorted(tr.items())},'atomic_runtime_boundary':{'source_version':SOURCE_VERSION,'target_version':VERSION,'source_app_gate_count':len(sr),'target_app_gate_count':len(tr),'gate_only_files_excluded':sorted(GATE_ONLY_FILES),'legacy_extension_zip_excluded':LEGACY_EXTENSION_ZIP,'runtime_shape_changed':True,'runtime_changed':changed,'runtime_added':added,'runtime_removed':removed},'browser_extension':{'version':'1.6.4','release_unit':'INDEPENDENT','released_this_round':False,'mechanical_version_bump':False},'update':{'project_id':'P01','component_id':'APP','manifest_truth':'llhzx2018/core-updates/projects/P01.json','release_truth':'GitHub Release','asset_name':f'VF_Start_V{VERSION}_UPDATE.zip','supported_from':[SOURCE_VERSION],'backup_required':True,'rollback_supported':True}})
    rmb=(json.dumps(rm,ensure_ascii=False,indent=2)+'\n').encode();delivery=dict(td);delivery['release-manifest.json']=rmb;atomic_target=dict(tr);atomic_target['release-manifest.json']=rmb
    repair=v2.build_repair(sr,atomic_target,sha(tr['app/UpdateManager.php']))
    old_s="public const SOURCE_VERSION='2.21.14';";old_t="public const TARGET_VERSION='2.21.15';";new_s=f"public const SOURCE_VERSION='{SOURCE_VERSION}';";new_t=f"public const TARGET_VERSION='{VERSION}';"
    if repair.count(old_s)!=1 or repair.count(old_t)!=1:raise SystemExit('atomic version template anchor mismatch')
    repair=repair.replace(old_s,new_s,1).replace(old_t,new_t,1)
    rn=f'repair-v{VERSION}.php';rp=out/rn;rp.write_text(repair,encoding='utf-8',newline='\n')
    base.deterministic_zip(out/f'VF_Start_V{VERSION}_FULL.zip',delivery);base.deterministic_zip(out/f'VF_Start_V{VERSION}_SOURCE.zip',delivery)
    rb=rp.read_bytes();base.deterministic_zip(out/f'VF_Start_V{VERSION}_ATOMIC.zip',{rn:rb});base.deterministic_zip(out/f'VF_Start_V{VERSION}_UPDATE.zip',{rn:rb})
    (out/f'VF_Start_V{VERSION}_RELEASE_NOTES.md').write_text(f'# VF Start V{VERSION} Formal Artifact Candidate Gate\n\n- Source: V{SOURCE_VERSION}\n- Candidate: V{VERSION}\n- Sidebar: secondary-category readability refinement\n- Release: NOT AUTHORIZED\n- Production: UNCHANGED\n- Schema: UNCHANGED\n- Browser Helper: 1.6.4 / UNCHANGED\n',encoding='utf-8')
    formal={'project_id':'P01','component_id':'APP','version':VERSION,'source_version':SOURCE_VERSION,'candidate_commit':a.candidate_commit,'candidate_tree':a.candidate_tree,'production_commit':a.production_commit,'schema':SCHEMA,'release_authorized':False,'runtime_source_files':len(sr),'runtime_target_files':len(tr),'runtime_changed':changed,'runtime_added':added,'runtime_removed':removed,'browser_extension':'1.6.4 / UNCHANGED','artifact_gate':'PENDING_EXECUTION'}
    (out/f'VF_Start_V{VERSION}_RELEASE_MANIFEST.json').write_text(json.dumps(formal,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    artifacts=[p for p in sorted(out.iterdir()) if p.is_file() and p.name!='SHA256SUMS.txt'];(out/'SHA256SUMS.txt').write_text(''.join(f'{base.sha256_file(p)}  {p.name}\n' for p in artifacts),encoding='utf-8')
    report={'status':'BUILD_PASS','version':VERSION,'source_version':SOURCE_VERSION,'candidate_commit':a.candidate_commit,'candidate_tree':a.candidate_tree,'production_commit':a.production_commit,'runtime_source_files':len(sr),'runtime_target_files':len(tr),'runtime_changed':changed,'runtime_added':added,'runtime_removed':removed,'artifacts':{p.name:{'bytes':p.stat().st_size,'sha256':base.sha256_file(p)} for p in artifacts}}
    print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
