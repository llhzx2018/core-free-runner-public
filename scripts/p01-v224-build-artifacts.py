#!/usr/bin/env python3
from pathlib import Path
import hashlib, importlib.util, json
ROOT=Path.cwd(); VERSION='2.24.0'; SOURCE_VERSION='2.23.0'; SCHEMA='2026082801'
CANDIDATE='867e3387b8efb70398287d05fd3652540efa77c8'; TREE='5985dab8ee071c881fd1e425864ed363e3bdc905'; SOURCE='6e7d30e6ea0c8f5f70076a69b0d1e6fb9be620b2'
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
base=load('base',ROOT/'proven/scripts/p01-build-release.py'); v2=load('v2',ROOT/'proven/scripts/p01-build-release-v2.py')
sha=lambda b: hashlib.sha256(b).hexdigest()
gate_only={'.gitignore','CHANGELOG.md','DEPLOY-HERE.txt','FULL-PACKAGE-NOTES.txt','README.md','UPGRADE-V2.txt','robots.txt'}
def runtime(files): return {k:v for k,v in files.items() if k!='release-manifest.json' and k not in gate_only and k!='VF-Start-Browser-Extension.zip'}
target_delivery=base.collect(ROOT/'candidate/src'); source_delivery=base.collect(ROOT/'production/src')
if target_delivery['VERSION.txt'].strip()!=VERSION.encode(): raise SystemExit('candidate version mismatch')
if source_delivery['VERSION.txt'].strip()!=SOURCE_VERSION.encode(): raise SystemExit('source version mismatch')
target=runtime(target_delivery); source=runtime(source_delivery)
changed=sorted(k for k in target if k not in source or sha(target[k])!=sha(source[k])); added=sorted(set(target)-set(source)); removed=sorted(set(source)-set(target))
if not changed: raise SystemExit('empty runtime delta')
for r in ['app/SurfaceShell.php','assets/surface-ux-closure.css','system-baseline.php','cli/baseline-verify.php','app/SurfaceRepository.php','cli/surface-verify.php']:
    if r not in target: raise SystemExit('missing target runtime '+r)
manifest={'project':'VF Start','project_id':'P01','project_slug':'vf-start','component_id':'APP','version':VERSION,'source_version':SOURCE_VERSION,'schema_version':SCHEMA,'source_schema_version':SCHEMA,'release_type':'formal','stage':'FORMAL_ARTIFACT_GATE','deployable':True,'release_authorized':False,'source_commit':CANDIDATE,'source_tree':TREE,'production_source_commit':SOURCE,'schema_change':False,'schema_migrations':[],'runtime_data_included':False,'seed_user_business_data_included':False,'runtime_hashed_file_count':len(target),'runtime_files':{k:sha(v) for k,v in sorted(target.items())},'atomic_runtime_boundary':{'source_version':SOURCE_VERSION,'target_version':VERSION,'source_app_gate_count':len(source),'target_app_gate_count':len(target),'added_files':added,'removed_files':removed,'runtime_delta':changed},'browser_extension':{'version':'1.6.4','release_unit':'INDEPENDENT','released_this_round':False},'update':{'project_id':'P01','component_id':'APP','manifest_truth':'llhzx2018/core-updates/projects/P01.json','release_truth':'GitHub Release','asset_name':'VF_Start_V2.24.0_UPDATE.zip','supported_from':[SOURCE_VERSION],'backup_required':True,'rollback_supported':True},'multi_surface':{'surfaces':['start','channels','watch'],'profile_table':'resource_surface_profiles','no_profile_semantics':'START','automatic_reclassification':False},'common_product_baseline':{'id':'VF-COMMON-PRODUCT-BASELINE@2.0','profile':'PERSONAL_SINGLE_ADMIN','current':True}}
mb=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode(); full=dict(target_delivery); full['release-manifest.json']=mb; atomic=dict(target); atomic['release-manifest.json']=mb
repair=v2.build_repair(source,atomic,sha(target['app/UpdateManager.php']))
old="public const SOURCE_VERSION='2.21.14';\n    public const TARGET_VERSION='2.21.15';\n    public const TARGET_SCHEMA='2026080902';"; new="public const SOURCE_VERSION='2.23.0';\n    public const TARGET_VERSION='2.24.0';\n    public const TARGET_SCHEMA='2026082801';"
if repair.count(old)!=1: raise SystemExit('repair constant anchor mismatch')
repair=repair.replace(old,new,1)
out=Path('/tmp/p01-v224-artifacts'); out.mkdir(parents=True,exist_ok=True)
rp=out/'repair-v2.24.0.php'; rp.write_text(repair,encoding='utf-8',newline='\n')
base.deterministic_zip(out/'VF-Start-V2.24.0-FULL.zip',full); base.deterministic_zip(out/'VF-Start-V2.24.0-UPDATE.zip',{rp.name:rp.read_bytes()}); base.deterministic_zip(out/'VF_Start_V2.24.0_UPDATE.zip',{rp.name:rp.read_bytes()})
result={'project_id':'P01','version':VERSION,'source_version':SOURCE_VERSION,'candidate':CANDIDATE,'candidate_tree':TREE,'source_commit':SOURCE,'source_schema':SCHEMA,'schema':SCHEMA,'schema_change':False,'runtime_source_files':len(source),'runtime_target_files':len(target),'runtime_added':added,'runtime_removed':removed,'runtime_delta':changed,'runtime_delta_count':len(changed),'atomic_update':True,'status':'BUILD_PASS'}
(out/'P01-V2.24.0-ARTIFACT-GATE.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
arts=[p for p in sorted(out.iterdir()) if p.is_file()]; (out/'SHA256SUMS.txt').write_text(''.join(f'{base.sha256_file(p)}  {p.name}\n' for p in arts),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))