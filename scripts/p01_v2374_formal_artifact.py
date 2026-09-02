from pathlib import Path
import hashlib, importlib.util, json, os, re, shutil
ROOT=Path(os.environ['GITHUB_WORKSPACE']); FORMAL=ROOT/'formal'; PRODUCTION=ROOT/'production'; PROVEN=ROOT/'proven'
OUT=Path(os.environ.get('OUT','/tmp/p01-v2374-formal-artifacts'))
VERSION='2.37.4'; SOURCE_VERSION='2.37.3'; SCHEMA='2026082901'
FORMAL_SOURCE='4532e6443805cefe141efc1f70f1689e532450b9'; FORMAL_TREE='b2c5ac50e07c851dc960bbc0d2b04f33271346cb'; RUNTIME_TREE='369f24a5320b9c7ebbb950a06c2711b8ca3b4f93'
SOURCE='cec95e310771feb6813a51c7ee3340884295ee38'; SOURCE_TREE='8fc025e93aaf730414e70a3fcbdc6d43fe954653'; SOURCE_RUNTIME='e56459ebadc120c749cc5336821d762001db5218'
READINESS_RUN=33604312715; FORMAL_BIND_RUN=33604457692

def load(name,path):
    s=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
base=load('base',PROVEN/'scripts/p01-build-release.py'); v2=load('v2',PROVEN/'scripts/p01-build-release-v2.py')
sha=lambda b: hashlib.sha256(b).hexdigest()
gate_only={'.gitignore','CHANGELOG.md','DEPLOY-HERE.txt','FULL-PACKAGE-NOTES.txt','README.md','UPGRADE-V2.txt','robots.txt'}
def runtime(files): return {k:v for k,v in files.items() if k!='release-manifest.json' and k not in gate_only and k!='VF-Start-Browser-Extension.zip'}

def build(dest: Path):
    shutil.rmtree(dest,ignore_errors=True); dest.mkdir(parents=True,exist_ok=True)
    td=base.collect(FORMAL/'src'); sd=base.collect(PRODUCTION/'src'); target=runtime(td); source=runtime(sd)
    changed=sorted(k for k in target if k in source and sha(target[k])!=sha(source[k])); added=sorted(set(target)-set(source)); removed=sorted(set(source)-set(target))
    expected=['VERSION.txt','app/ResourceCoverCache.php','app/bootstrap.php','assets/workspace.js']
    if changed!=expected or added or removed: raise SystemExit('runtime boundary mismatch '+json.dumps({'changed':changed,'added':added,'removed':removed}))
    manifest={
      'project':'VF Start','project_id':'P01','component_id':'APP','version':VERSION,'source_version':SOURCE_VERSION,'schema_version':SCHEMA,'source_schema_version':SCHEMA,
      'release_type':'formal','stage':'FORMAL_ARTIFACT','deployable':True,'release_authorized':True,
      'formal_source_commit':FORMAL_SOURCE,'formal_source_tree':FORMAL_TREE,'runtime_source_tree':RUNTIME_TREE,
      'production_source_commit':SOURCE,'production_source_tree':SOURCE_TREE,'production_runtime_tree':SOURCE_RUNTIME,
      'candidate_readiness_run':READINESS_RUN,'formal_bind_run':FORMAL_BIND_RUN,'schema_change':False,'schema_migrations':[],'runtime_data_included':False,
      'runtime_files':{k:sha(v) for k,v in sorted(target.items())},
      'atomic_runtime_boundary':{'source_version':SOURCE_VERSION,'target_version':VERSION,'source_schema':SCHEMA,'target_schema':SCHEMA,'added_files':added,'removed_files':removed,'changed_files':changed},
      'update':{'asset_name':'VF_Start_V2.37.4_UPDATE.zip','supported_from':[SOURCE_VERSION],'backup_required':True,'rollback_supported':True},
      'hotfix':{'purpose':'iyf remote cover content-negotiation alignment','hotfix_gate_r1':33603764352,'hotfix_gate':33603844441,'real_iyf_first_attempt':'3/3 PASS','avif_advertised':False,'remote_formats':['image/webp','image/png','image/jpeg','image/gif'],'retry_revision':'v5','manual_upload_policy':'UNCHANGED'}
    }
    mb=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode(); full=dict(td); full['release-manifest.json']=mb; atomic=dict(target); atomic['release-manifest.json']=mb
    repair=v2.build_repair(source,atomic,sha(target['app/UpdateManager.php']))
    repair,n=re.subn(r"public const SOURCE_VERSION='[^']+';\n    public const TARGET_VERSION='[^']+';\n    public const TARGET_SCHEMA='[^']+';",f"public const SOURCE_VERSION='{SOURCE_VERSION}';\n    public const TARGET_VERSION='{VERSION}';\n    public const TARGET_SCHEMA='{SCHEMA}';",repair,count=1)
    if n!=1: raise SystemExit('repair constant anchor mismatch')
    rp=dest/'repair-v2.37.4.php'; rp.write_text(repair,encoding='utf-8',newline='\n')
    fullp=dest/'VF-Start-V2.37.4-FULL.zip'; upp=dest/'VF_Start_V2.37.4_UPDATE.zip'; base.deterministic_zip(fullp,full); base.deterministic_zip(upp,{rp.name:rp.read_bytes()})
    meta={'status':'FORMAL_ARTIFACT_PASS','version':VERSION,'source_version':SOURCE_VERSION,'schema':SCHEMA,'formal_source':FORMAL_SOURCE,'formal_tree':FORMAL_TREE,'runtime_tree':RUNTIME_TREE,'changed_runtime':changed,'schema_change':False,'migration':None,'candidate_readiness_run':READINESS_RUN,'formal_bind_run':FORMAL_BIND_RUN,'owner_production_write':False}
    (dest/'P01-V2.37.4-FORMAL.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    notes='''# VF Start V2.37.4\n\nIYF Cover Content-Negotiation Hotfix.\n\n- V2.37.3 can still leave real IYF cards on letter placeholders even after the GIF validator fix.\n- The remote image request advertised AVIF although the security validator did not accept AVIF. CDN responses may vary by Accept negotiation.\n- V2.37.4 stops advertising unsupported AVIF and negotiates only WebP/PNG/JPEG/GIF, all already validated by the existing safe image pipeline.\n- No AVIF parser/storage support is added. Manual cover uploads remain WebP/JPG/PNG only.\n- Browser failed-cover retry revision moves from v4 to v5 so V2.37.3 failures retry immediately after upgrade.\n- Focused R2 33603844441: three real IYF URLs succeeded on first attempt; all three CDN responses were negotiated/stored as WebP despite .gif source URLs.\n- Candidate Readiness 33604312715: real V2.37.3 → V2.37.4 Atomic PASS, Fresh Install PASS, IYF first-attempt 3/3 PASS.\n- Schema: 2026082901 (unchanged). No migration.\n- Atomic update supports exactly V2.37.3 → V2.37.4.\n'''
    (dest/'P01-V2.37.4-RELEASE-NOTES.md').write_text(notes,encoding='utf-8')
    for p in [fullp,upp,rp]: (dest/(p.name+'.sha256')).write_text(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n',encoding='utf-8')
    return meta
OUT1=OUT; OUT2=Path('/tmp/p01-v2374-formal-artifacts-rebuild'); meta=build(OUT1); build(OUT2)
for name in sorted(p.name for p in OUT1.iterdir()):
    a=OUT1/name; b=OUT2/name
    if not b.exists() or hashlib.sha256(a.read_bytes()).digest()!=hashlib.sha256(b.read_bytes()).digest(): raise SystemExit('determinism mismatch '+name)
print(json.dumps(meta,ensure_ascii=False))
