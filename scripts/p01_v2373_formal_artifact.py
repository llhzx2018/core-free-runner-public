from pathlib import Path
import hashlib, importlib.util, json, os, re, shutil

ROOT=Path(os.environ['GITHUB_WORKSPACE'])
FORMAL=ROOT/'formal'; PRODUCTION=ROOT/'production'; PROVEN=ROOT/'proven'
OUT=Path(os.environ.get('OUT','/tmp/p01-v2373-formal-artifacts'))
VERSION='2.37.3'; SOURCE_VERSION='2.37.2'; SCHEMA='2026082901'
FORMAL_SOURCE='cec95e310771feb6813a51c7ee3340884295ee38'
FORMAL_TREE='8fc025e93aaf730414e70a3fcbdc6d43fe954653'
RUNTIME_TREE='e56459ebadc120c749cc5336821d762001db5218'
SOURCE='1f5a16796511620760a45cb81b3c8019b91e505b'
SOURCE_TREE='e423df9391c48e4176c041db0f38a32b28c21d44'
SOURCE_RUNTIME='70b627513327aee0a37fae245b0f4042ad69b5a4'
READINESS_RUN=33600570356; FORMAL_BIND_RUN=33600694106

def load(name,path):
    s=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
base=load('base',PROVEN/'scripts/p01-build-release.py')
v2=load('v2',PROVEN/'scripts/p01-build-release-v2.py')
sha=lambda b: hashlib.sha256(b).hexdigest()
gate_only={'.gitignore','CHANGELOG.md','DEPLOY-HERE.txt','FULL-PACKAGE-NOTES.txt','README.md','UPGRADE-V2.txt','robots.txt'}
def runtime(files): return {k:v for k,v in files.items() if k!='release-manifest.json' and k not in gate_only and k!='VF-Start-Browser-Extension.zip'}

def build(dest: Path):
    shutil.rmtree(dest,ignore_errors=True); dest.mkdir(parents=True,exist_ok=True)
    td=base.collect(FORMAL/'src'); sd=base.collect(PRODUCTION/'src')
    target=runtime(td); source=runtime(sd)
    changed=sorted(k for k in target if k in source and sha(target[k])!=sha(source[k]))
    added=sorted(set(target)-set(source)); removed=sorted(set(source)-set(target))
    expected=['VERSION.txt','app/ResourceCoverCache.php','app/bootstrap.php','assets/workspace.js']
    if changed!=expected or added or removed:
        raise SystemExit('runtime boundary mismatch '+json.dumps({'changed':changed,'added':added,'removed':removed}))
    manifest={
      'project':'VF Start','project_id':'P01','component_id':'APP','version':VERSION,
      'source_version':SOURCE_VERSION,'schema_version':SCHEMA,'source_schema_version':SCHEMA,
      'release_type':'formal','stage':'FORMAL_ARTIFACT','deployable':True,'release_authorized':True,
      'formal_source_commit':FORMAL_SOURCE,'formal_source_tree':FORMAL_TREE,'runtime_source_tree':RUNTIME_TREE,
      'production_source_commit':SOURCE,'production_source_tree':SOURCE_TREE,'production_runtime_tree':SOURCE_RUNTIME,
      'candidate_readiness_run':READINESS_RUN,'formal_bind_run':FORMAL_BIND_RUN,
      'schema_change':False,'schema_migrations':[],'runtime_data_included':False,
      'runtime_files':{k:sha(v) for k,v in sorted(target.items())},
      'atomic_runtime_boundary':{'source_version':SOURCE_VERSION,'target_version':VERSION,'source_schema':SCHEMA,'target_schema':SCHEMA,'added_files':added,'removed_files':removed,'changed_files':changed},
      'update':{'asset_name':'VF_Start_V2.37.3_UPDATE.zip','supported_from':[SOURCE_VERSION],'backup_required':True,'rollback_supported':True},
      'hotfix':{'purpose':'iyf gif auto-cover validation','diagnostic_r2':33599532987,'hotfix_gate':33600058990,'first_attempt_e2e':'3/3 PASS','manual_upload_policy':'UNCHANGED'}
    }
    mb=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode()
    full=dict(td); full['release-manifest.json']=mb
    atomic=dict(target); atomic['release-manifest.json']=mb
    update_manager_sha=sha(target['app/UpdateManager.php'])
    repair=v2.build_repair(source,atomic,update_manager_sha)
    repair,n=re.subn(r"public const SOURCE_VERSION='[^']+';\n    public const TARGET_VERSION='[^']+';\n    public const TARGET_SCHEMA='[^']+';",f"public const SOURCE_VERSION='{SOURCE_VERSION}';\n    public const TARGET_VERSION='{VERSION}';\n    public const TARGET_SCHEMA='{SCHEMA}';",repair,count=1)
    if n!=1: raise SystemExit('repair constant anchor mismatch')
    rp=dest/'repair-v2.37.3.php'; rp.write_text(repair,encoding='utf-8',newline='\n')
    fullp=dest/'VF-Start-V2.37.3-FULL.zip'; upp=dest/'VF_Start_V2.37.3_UPDATE.zip'
    base.deterministic_zip(fullp,full)
    base.deterministic_zip(upp,{rp.name:rp.read_bytes()})
    meta={'status':'FORMAL_ARTIFACT_PASS','version':VERSION,'source_version':SOURCE_VERSION,'schema':SCHEMA,'formal_source':FORMAL_SOURCE,'formal_tree':FORMAL_TREE,'runtime_tree':RUNTIME_TREE,'changed_runtime':changed,'schema_change':False,'migration':None,'candidate_readiness_run':READINESS_RUN,'formal_bind_run':FORMAL_BIND_RUN,'owner_production_write':False}
    (dest/'P01-V2.37.3-FORMAL.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    notes='''# VF Start V2.37.3\n\nIYF GIF Auto-cover Hotfix.\n\n- Fix IYF covers that were correctly discovered by V2.37.2 but rejected when the CDN returned the actual poster as GIF.\n- Automatic remote cover validation now safely accepts GIF87a/GIF89a in addition to PNG/JPG/WebP, while retaining byte-size, image validity and dimension checks.\n- Manual cover upload policy remains unchanged: WebP/JPG/PNG only.\n- Keep the V2.37.2 mview.iyf.tv same-ID metadata fallback; stored user URLs remain unchanged.\n- Reset browser-side failed-cover retry revision from v3 to v4 so V2.37.2 failed resources retry immediately.\n- Real first-attempt IYF E2E: 3/3 persisted and 3/3 served through resource-cover.php.\n- Schema: 2026082901 (unchanged). No migration.\n- Atomic update supports exactly V2.37.2 → V2.37.3.\n'''
    (dest/'P01-V2.37.3-RELEASE-NOTES.md').write_text(notes,encoding='utf-8')
    for p in [fullp,upp,rp]:
        (dest/(p.name+'.sha256')).write_text(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n',encoding='utf-8')
    return meta

OUT1=OUT; OUT2=Path('/tmp/p01-v2373-formal-artifacts-rebuild')
meta=build(OUT1); build(OUT2)
for name in sorted(p.name for p in OUT1.iterdir()):
    a=OUT1/name; b=OUT2/name
    if not b.exists() or hashlib.sha256(a.read_bytes()).digest()!=hashlib.sha256(b.read_bytes()).digest():
        raise SystemExit('determinism mismatch '+name)
print(json.dumps(meta,ensure_ascii=False))
