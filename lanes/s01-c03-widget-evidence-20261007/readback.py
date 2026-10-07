import json,hashlib,pathlib,zipfile,os,stat
r=json.loads(pathlib.Path('/tmp/native-run.json').read_text());m=json.loads(pathlib.Path('/tmp/native-meta.json').read_text());data=pathlib.Path('/tmp/native-proof.zip').read_bytes()
assert r['id']==int(os.environ['NATIVE_RUN']) and r['conclusion']=='success' and r['head_sha']==os.environ['NATIVE_RUNNER_SHA']
assert m['id']==int(os.environ['NATIVE_ARTIFACT_ID']) and m['workflow_run']['id']==r['id'] and m['workflow_run']['head_sha']==r['head_sha'] and not m['expired'] and m['size_in_bytes']==len(data) and m['digest']=='sha256:'+hashlib.sha256(data).hexdigest()
selected=['proof/FINAL_EVIDENCE.json','proof/identity.json','proof/native-baseline.json','proof/native-corrupt-negative.json','proof/native-upgrade.json','proof/native-candidate.json','proof/native-source-recovery.json','proof/native-rollback.json','proof/native-reapply.json','proof/native-reapply-readback.json','proof/clean-install.json','proof/widget-quick-rollback.json','proof/widget-quick-reapply.json','proof/widget-quick-clean.json','proof/integration/integration.json','checks/baseline/proof/dependency-engine-full.json','checks/baseline/proof/widget-result.json','checks/baseline/proof/provider-only-geometry.json','checks/candidate/proof/dependency-engine-full.json','checks/candidate/proof/widget-result.json','checks/candidate/proof/provider-only-geometry.json','checks/candidate/proof/dependency-head-proof.json']
files={};receipts={}
with zipfile.ZipFile('/tmp/native-proof.zip') as z:
 assert z.testzip() is None
 for name in selected:
  p=pathlib.PurePosixPath(name);assert not p.is_absolute() and '..' not in p.parts and p.suffix=='.json'
  data=z.read(name);content=data.decode('utf8');json.loads(content);files[name]=content;receipts[name]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
f=json.loads(files['proof/FINAL_EVIDENCE.json']);assert f['source_sha']==os.environ['TARGET_SHA'] and f['source_tree']==os.environ['TARGET_TREE'] and f['version']==os.environ['TARGET_VERSION'] and f['status']=='PASS'
assert json.loads(files['checks/baseline/proof/widget-result.json'])['issue_count']==4
assert json.loads(files['checks/candidate/proof/widget-result.json'])['issue_count']==0
assert len(json.loads(files['proof/integration/integration.json'])['cases'])==16
print('VF_NATIVE_ARCHIVE_BEGIN');print(json.dumps({'status':'PASS','artifact_id':m['id'],'run_id':r['id'],'source_sha':f['source_sha'],'source_tree':f['source_tree'],'artifact_bytes':m['size_in_bytes'],'artifact_digest':m['digest'],'receipts':receipts,'files':files}));print('VF_NATIVE_ARCHIVE_END')
