#!/usr/bin/env python3
from pathlib import Path
import sys, textwrap

root=Path(sys.argv[1]).resolve()

def replace_once(path:Path, old:str, new:str, label:str):
    s=path.read_text(encoding='utf-8')
    n=s.count(old)
    if n!=1:
        raise SystemExit(f'{label}_SENTINEL_COUNT={n}')
    path.write_text(s.replace(old,new,1),encoding='utf-8')

# Runtime version identity.
(root/'VERSION').write_text('2.5.5\n',encoding='utf-8')

# Runtime build authority: preserve V2.5.4 product runtime and only advance release identity.
p=root/'scripts/build-release-tree.py'
s=p.read_text(encoding='utf-8')
s=s.replace("maintenance_versions={'2.5.1','2.5.2','2.5.3','2.5.4'}", "maintenance_versions={'2.5.1','2.5.2','2.5.3','2.5.4','2.5.5'}")
needle="if version=='2.5.4':\n    version_note='V2.5.4 unifies the full backend UA/UI, fixes update-history final-outcome semantics, normalizes feedback/accessibility/responsive behavior, and keeps Schema/business/provider authority unchanged.'"
repl="if version=='2.5.5':\n    version_note='V2.5.5 preserves the verified V2.5.4 backend UA/UI runtime and fixes the formal Online Handoff packaging contract; Schema/business/provider authority remains unchanged.'\nelif version=='2.5.4':\n    version_note='V2.5.4 unifies the full backend UA/UI, fixes update-history final-outcome semantics, normalizes feedback/accessibility/responsive behavior, and keeps Schema/business/provider authority unchanged.'"
if needle not in s: raise SystemExit('BUILD_RELEASE_TREE_VERSION_NOTE_SENTINEL_DRIFT')
s=s.replace(needle,repl,1)
p.write_text(s,encoding='utf-8')

# Base Atomic builder authority: derive Handoff Marker from the target Runtime consumer contract.
p=root/'scripts/build-v251-maintenance-release.py'
s=p.read_text(encoding='utf-8')
old="runtime=Path(a.target_runtime).resolve(); out=Path(a.output).resolve()\nif out.exists(): shutil.rmtree(out)"
new="""runtime=Path(a.target_runtime).resolve(); out=Path(a.output).resolve()
contract_path=runtime/'app/Core/Update/UpdateContract.php'
if not contract_path.is_file() or contract_path.is_symlink(): raise SystemExit('ONLINE_HANDOFF_CONSUMER_CONTRACT_MISSING')
contract_source=contract_path.read_text(encoding='utf-8')
marker_match=re.search(r\"public\\s+const\\s+HANDOFF_MARKER\\s*=\\s*'([^']+)'\\s*;\",contract_source)
if not marker_match: raise SystemExit('ONLINE_HANDOFF_MARKER_AUTHORITY_MISSING')
HANDOFF_MARKER=marker_match.group(1)
if not re.fullmatch(r'VF_INFRA_ONLINE_HANDOFF_V[0-9]+',HANDOFF_MARKER): raise SystemExit('ONLINE_HANDOFF_MARKER_AUTHORITY_INVALID')
if out.exists(): shutil.rmtree(out)"""
if s.count(old)!=1: raise SystemExit('BASE_RUNTIME_SENTINEL_DRIFT')
s=s.replace(old,new,1)
old="const VF_INFRA_ATOMIC_SOURCE_MANIFEST_SHA256='{source_manifest_sha}';"
new="const VF_INFRA_ATOMIC_SOURCE_MANIFEST_SHA256='{source_manifest_sha}';\nconst VF_INFRA_ONLINE_HANDOFF_MARKER='{HANDOFF_MARKER}';"
if s.count(old)!=1: raise SystemExit('BASE_MARKER_CONST_SENTINEL_DRIFT')
s=s.replace(old,new,1)
old="return ['files'=>count($p),'version'=>$v,'schema'=>VF_INFRA_ATOMIC_SCHEMA,'production_source_manifest_sha256'=>VF_INFRA_ATOMIC_SOURCE_MANIFEST_SHA256];"
new="return ['files'=>count($p),'version'=>$v,'schema'=>VF_INFRA_ATOMIC_SCHEMA,'production_source_manifest_sha256'=>VF_INFRA_ATOMIC_SOURCE_MANIFEST_SHA256,'handoff_marker'=>VF_INFRA_ONLINE_HANDOFF_MARKER];"
if s.count(old)!=1: raise SystemExit('BASE_SELFTEST_RESULT_SENTINEL_DRIFT')
s=s.replace(old,new,1)
old="$state='ready';$headline='准备升级 VF Infra';$lead='V2.5.1 只增加正式维护通道，Schema 与业务模型保持不变。';$details=[];$blocked=false;$authReady=false;$success=false;$failureMessage='';$currentVersion='';$csrf='';$journal=null;"
new="$state='ready';$headline='准备升级 VF Infra';$lead='V2.5.1 只增加正式维护通道，Schema 与业务模型保持不变。';$details=[];$blocked=false;$authReady=false;$success=false;$failureMessage='';$currentVersion='';$csrf='';$journal=null;$onlineHandoffRequest=false;$onlineOperationId='';"
if s.count(old)!=1: raise SystemExit('BASE_STATE_SENTINEL_DRIFT')
s=s.replace(old,new,1)
old="$authReady=Auth::isAuthenticated();"
new="""$authReady=Auth::isAuthenticated();$onlineHandoffRequest=(string)($_SERVER['REQUEST_METHOD']??'GET')==='POST'&&array_key_exists('vf_online_handoff',$_POST);if($onlineHandoffRequest){{if(!$authReady)throw new RuntimeException('在线更新交接需要现有管理员会话。');Auth::verifySameOrigin();$handoffToken=trim((string)($_POST['vf_online_handoff']??''));if($handoffToken==='')throw new RuntimeException('在线更新交接凭据缺失。');$onlinePlan=\\VFInfra\\Core\\Update\\OnlineUpdateHandoff::authorize(VF_INFRA_ATOMIC_TARGET,$handoffToken,basename(__FILE__));$onlineOperationId=(string)($onlinePlan['operation_id']??'');if($onlineOperationId==='')throw new RuntimeException('在线更新 operation_id 缺失。');}}else{{$onlinePlan=\\VFInfra\\Core\\Update\\OnlineUpdateHandoff::readPlan();if(is_array($onlinePlan)&&hash_equals((string)($onlinePlan['target_version']??''),VF_INFRA_ATOMIC_TARGET)&&hash_equals((string)($onlinePlan['repair_file']??''),basename(__FILE__))&&!empty($onlinePlan['authorized_at']))$onlineOperationId=(string)($onlinePlan['operation_id']??'');}}"""
if s.count(old)!=1: raise SystemExit('BASE_AUTH_SENTINEL_DRIFT')
s=s.replace(old,new,1)
old="if((string)($_SERVER['REQUEST_METHOD']??'GET')==='POST'&&!$blocked&&$authReady&&!$success){{"
new="if((string)($_SERVER['REQUEST_METHOD']??'GET')==='POST'&&!$onlineHandoffRequest&&!$blocked&&$authReady&&!$success){{"
if s.count(old)!=1: raise SystemExit('BASE_POST_SENTINEL_DRIFT')
s=s.replace(old,new,1)
old="$tx->commit();$journal->clear();"
new="$tx->commit();$journal->clear();if($onlineOperationId!=='')try{{\\VFInfra\\Core\\Update\\OnlineUpdateHandoff::recordRepairResult($onlineOperationId,'success','',['schema'=>14]);}}catch(Throwable $ignored){{}}"
if s.count(old)!=1: raise SystemExit('BASE_COMMIT_SENTINEL_DRIFT')
s=s.replace(old,new,1)
old="$state='failed';$headline=$dbRestoreFailed===''?'升级失败，已自动回滚':'升级失败，需要人工恢复';"
new="if($onlineOperationId!=='')try{{$onlineResult=($tx instanceof \\VFInfra\\Core\\Release\\AtomicFilesystemTransaction&&$dbRestoreFailed==='')?'rolled_back':'failed';\\VFInfra\\Core\\Update\\OnlineUpdateHandoff::recordRepairResult($onlineOperationId,$onlineResult,'atomic',['reason'=>vfi251_safe_error($e)]);}}catch(Throwable $ignored){{}}$state='failed';$headline=$dbRestoreFailed===''?'升级失败，已自动回滚':'升级失败，需要人工恢复';"
if s.count(old)!=1: raise SystemExit('BASE_FAILURE_SENTINEL_DRIFT')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')

# V2.5.5 wrapper. It reuses the now handoff-aware base builder and carries the complete
# V2.5.4 product delta so real Production 2.5.3 can jump directly to 2.5.5.
base=(root/'scripts/build-v253-update-release.py').read_text(encoding='utf-8')
base=base.replace("TARGET='2.5.3'","TARGET='2.5.5'",1).replace("SOURCE='2.5.2'","SOURCE='2.5.3'",1)
start=base.index('PAYLOAD_PATHS=[')
end=base.index(']\n\n',start)+2
payload="""PAYLOAD_PATHS=[
    'VERSION.txt',
    'api.php',
    'assets/app.js',
    'assets/v254-ui.css',
    'assets/v254-ui.js',
    'index.php',
    'login.php',
    'maintenance.php',
    'app/Core/Update/UpdateHistoryService.php',
    'release-manifest.json',
]"""
base=base[:start]+payload+base[end:]
base=base.replace("prefix='p04-v253-builder-'","prefix='p04-v255-builder-'",1)
base=base.replace("generated=Path(td)/'build-v253-generated.py'","generated=Path(td)/'build-v255-generated.py'",1)
base=base.replace("raise SystemExit('V252_BUILDER_OUTPUT_INCOMPLETE')","raise SystemExit('V255_BUILDER_OUTPUT_INCOMPLETE')",1)
# The old wrapper's narrative substitutions are harmless but not authoritative; add exact V2.5.5 package gates.
insert="""
contract_source=(Path(a.target_runtime).resolve()/'app/Core/Update/UpdateContract.php').read_text(encoding='utf-8')
marker_match=__import__('re').search(r\"public\\s+const\\s+HANDOFF_MARKER\\s*=\\s*'([^']+)'\\s*;\",contract_source)
if not marker_match: raise SystemExit('V255_HANDOFF_CONSUMER_CONTRACT_MISSING')
handoff_marker=marker_match.group(1)
repair_raw=repair.read_text(encoding='utf-8')
if handoff_marker not in repair_raw: raise SystemExit('V255_HANDOFF_MARKER_MISSING')
for required in ['OnlineUpdateHandoff::authorize','OnlineUpdateHandoff::recordRepairResult','vf_online_handoff']:
    if required not in repair_raw: raise SystemExit('V255_HANDOFF_BEHAVIOR_MISSING '+required)
manifest['online_handoff_marker']=handoff_marker
manifest['online_handoff_contract']='consumer-derived'
manifest['online_handoff_gate']='PASS'
"""
needle="manifest['update_and_atomic_bytes_identical']=atomic.read_bytes()==update.read_bytes()\nmanifest_path.write_text"
if needle not in base: raise SystemExit('V255_WRAPPER_MANIFEST_SENTINEL_DRIFT')
base=base.replace("manifest['update_and_atomic_bytes_identical']=atomic.read_bytes()==update.read_bytes()\nmanifest_path.write_text", "manifest['update_and_atomic_bytes_identical']=atomic.read_bytes()==update.read_bytes()\n"+insert+"manifest_path.write_text",1)
(root/'scripts/build-v255-update-release.py').write_text(base,encoding='utf-8')

# Package validator: consumer-derived marker, SHA, structure, PHP syntax, repair self-test.
validator=r'''#!/usr/bin/env python3
from pathlib import Path
import argparse, hashlib, re, subprocess, tempfile, zipfile
p=argparse.ArgumentParser();p.add_argument('--runtime',required=True);p.add_argument('--zip',required=True);p.add_argument('--version',required=True);p.add_argument('--sha256',default='');a=p.parse_args()
runtime=Path(a.runtime).resolve(); zpath=Path(a.zip).resolve()
contract=(runtime/'app/Core/Update/UpdateContract.php').read_text(encoding='utf-8')
m=re.search(r"public\s+const\s+HANDOFF_MARKER\s*=\s*'([^']+)'\s*;",contract)
if not m: raise SystemExit('HANDOFF_MARKER_AUTHORITY_MISSING')
marker=m.group(1)
raw=zpath.read_bytes(); actual=hashlib.sha256(raw).hexdigest()
if a.sha256 and actual.lower()!=a.sha256.lower(): raise SystemExit('PACKAGE_SHA_MISMATCH')
entry=f'repair-v{a.version}.php'
with zipfile.ZipFile(zpath) as z:
    names=[x for x in z.namelist() if not x.endswith('/')]
    if names!=[entry]: raise SystemExit('PACKAGE_STRUCTURE_INVALID')
    repair=z.read(entry)
if marker.encode() not in repair: raise SystemExit('HANDOFF_MARKER_MISSING_OR_WRONG')
if a.version.encode() not in repair: raise SystemExit('REPAIR_TARGET_VERSION_MISSING')
with tempfile.TemporaryDirectory(prefix='p04-v255-validate-') as td:
    f=Path(td)/entry;f.write_bytes(repair)
    lint=subprocess.run(['php','-l',str(f)],capture_output=True,text=True)
    if lint.returncode!=0: raise SystemExit('MALFORMED_REPAIR_PHP')
    st=subprocess.run(['php',str(f),'--self-test'],capture_output=True,text=True)
    if st.returncode!=0: raise SystemExit('REPAIR_SELF_TEST_FAILED')
print(f'ONLINE_HANDOFF_PACKAGE_CONTRACT_PASS marker={marker} sha256={actual}')
'''
(root/'scripts/validate-online-atomic-package.py').write_text(validator,encoding='utf-8')

print('P04_V255_HOTFIX_PATCH_APPLIED')
