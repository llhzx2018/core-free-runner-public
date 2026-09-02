from pathlib import Path
import hashlib, importlib.util, json, os, re, shutil
ROOT=Path(os.environ['GITHUB_WORKSPACE']); FORMAL=ROOT/'formal'; PRODUCTION=ROOT/'production'; PROVEN=ROOT/'proven'
OUT=Path(os.environ.get('OUT','/tmp/p01-v2375-formal-artifacts'))
VERSION='2.37.5'; SOURCE_VERSION='2.37.4'; SCHEMA='2026082901'
FORMAL_SOURCE='cefda28149dbf29164adc8ebfa57edacad122474'; FORMAL_TREE='8999753c57e8b1156de6506f8e5f861136f41e5a'; RUNTIME_TREE='467c56faa900a6bfcc7caadd0fd570b9c6a76567'
SOURCE='4532e6443805cefe141efc1f70f1689e532450b9'; SOURCE_TREE='b2c5ac50e07c851dc960bbc0d2b04f33271346cb'; SOURCE_RUNTIME='369f24a5320b9c7ebbb950a06c2711b8ca3b4f93'
READINESS_RUN=33610132981; FORMAL_BIND_RUN=33610766833

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
    expected=['VERSION.txt','app/FunctionalWorkspaceShell.php','app/bootstrap.php','assets/surface-workspace.css','assets/workspace.js']
    if changed!=expected or added or removed: raise SystemExit('runtime boundary mismatch '+json.dumps({'changed':changed,'added':added,'removed':removed}))
    if (FORMAL/'src/app/ResourceCoverCache.php').read_bytes() != (PRODUCTION/'src/app/ResourceCoverCache.php').read_bytes():
        raise SystemExit('remote fetch policy unexpectedly changed')
    manifest={
      'project':'VF Start','project_id':'P01','component_id':'APP','version':VERSION,'source_version':SOURCE_VERSION,'schema_version':SCHEMA,'source_schema_version':SCHEMA,
      'release_type':'formal','stage':'FORMAL_ARTIFACT','deployable':True,'release_authorized':True,
      'formal_source_commit':FORMAL_SOURCE,'formal_source_tree':FORMAL_TREE,'runtime_source_tree':RUNTIME_TREE,
      'production_source_commit':SOURCE,'production_source_tree':SOURCE_TREE,'production_runtime_tree':SOURCE_RUNTIME,
      'candidate_readiness_run':READINESS_RUN,'formal_bind_run':FORMAL_BIND_RUN,'schema_change':False,'schema_migrations':[],'runtime_data_included':False,
      'runtime_files':{k:sha(v) for k,v in sorted(target.items())},
      'atomic_runtime_boundary':{'source_version':SOURCE_VERSION,'target_version':VERSION,'source_schema':SCHEMA,'target_schema':SCHEMA,'added_files':added,'removed_files':removed,'changed_files':changed},
      'update':{'asset_name':'VF_Start_V2.37.5_UPDATE.zip','supported_from':[SOURCE_VERSION],'backup_required':True,'rollback_supported':True},
      'hotfix':{'purpose':'production cover failure diagnostics and explicit manual retry','legacy_exact_replay_run':33608249098,'legacy_exact_replay':'12/12 PASS','edge_diagnostic_run':33608705736,'edge_diagnostic':'BOTH WWW IPv4 200+OG / BOTH STATIC IPv4 200 WEBP','focused_gate':33609124506,'retry_revision':'v6','persistent_admin_error_surface':True,'manual_retry_bypasses_browser_backoff':True,'remote_fetch_policy_change':False}
    }
    mb=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode(); full=dict(td); full['release-manifest.json']=mb; atomic=dict(target); atomic['release-manifest.json']=mb
    repair=v2.build_repair(source,atomic,sha(target['app/UpdateManager.php']))
    repair,n=re.subn(r"public const SOURCE_VERSION='[^']+';\n    public const TARGET_VERSION='[^']+';\n    public const TARGET_SCHEMA='[^']+';",f"public const SOURCE_VERSION='{SOURCE_VERSION}';\n    public const TARGET_VERSION='{VERSION}';\n    public const TARGET_SCHEMA='{SCHEMA}';",repair,count=1)
    if n!=1: raise SystemExit('repair constant anchor mismatch')
    rp=dest/'repair-v2.37.5.php'; rp.write_text(repair,encoding='utf-8',newline='\n')
    fullp=dest/'VF-Start-V2.37.5-FULL.zip'; upp=dest/'VF_Start_V2.37.5_UPDATE.zip'; base.deterministic_zip(fullp,full); base.deterministic_zip(upp,{rp.name:rp.read_bytes()})
    meta={'status':'FORMAL_ARTIFACT_PASS','version':VERSION,'source_version':SOURCE_VERSION,'schema':SCHEMA,'formal_source':FORMAL_SOURCE,'formal_tree':FORMAL_TREE,'runtime_tree':RUNTIME_TREE,'changed_runtime':changed,'schema_change':False,'migration':None,'candidate_readiness_run':READINESS_RUN,'formal_bind_run':FORMAL_BIND_RUN,'owner_production_write':False}
    (dest/'P01-V2.37.5-FORMAL.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    notes='''# VF Start V2.37.5\n\nProduction Cover Failure Diagnostics + Manual Retry Hotfix.\n\n- Exact replay of the original historical IYF record succeeded 12/12 in the current release runtime, so V2.37.5 stops blind changes to the remote fetch policy.\n- Both observed www.iyf.tv IPv4 edges returned HTTP 200 with OG cover metadata; both static.iyf.tv IPv4 edges returned HTTP 200 WebP bytes in the diagnostic gate.\n- Missing-cover Watch cards now expose an administrator-only explicit “重新抓封面” action.\n- Automatic cover failures persist their backend error on the affected card instead of being silently swallowed.\n- Manual retry bypasses the browser one-hour failed-cover backoff. Retry revision moves to v6 so prior failures retry after upgrade.\n- ResourceCoverCache.php / SSRF and remote image validation policy are unchanged from V2.37.4.\n- Candidate Readiness R3 33610132981: Exact Source PASS, diagnostic UX contract PASS, deterministic build PASS, real V2.37.4 → V2.37.5 Atomic PASS, Strict Fresh PASS.\n- Formal Bind 33610766833: PASS.\n- Schema: 2026082901 (unchanged). No migration.\n- Atomic update supports exactly V2.37.4 → V2.37.5.\n'''
    (dest/'P01-V2.37.5-RELEASE-NOTES.md').write_text(notes,encoding='utf-8')
    for p in [fullp,upp,rp]: (dest/(p.name+'.sha256')).write_text(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n',encoding='utf-8')
    return meta
OUT1=OUT; OUT2=Path('/tmp/p01-v2375-formal-artifacts-rebuild'); meta=build(OUT1); build(OUT2)
for name in sorted(p.name for p in OUT1.iterdir()):
    a=OUT1/name; b=OUT2/name
    if not b.exists() or hashlib.sha256(a.read_bytes()).digest()!=hashlib.sha256(b.read_bytes()).digest(): raise SystemExit('determinism mismatch '+name)
print(json.dumps(meta,ensure_ascii=False))
