import json,hashlib,zipfile,pathlib,os,stat
run=json.loads(pathlib.Path('/tmp/candidate-run.json').read_text());m=json.loads(pathlib.Path('/tmp/candidate-meta.json').read_text());data=pathlib.Path('/tmp/candidate-proof.zip').read_bytes()
assert run['id']==int(os.environ['CANDIDATE_RUN']) and run['conclusion']=='success' and run['head_sha']==os.environ['CANDIDATE_RUNNER_SHA']
assert m['id']==int(os.environ['CANDIDATE_ARTIFACT_ID']) and m['workflow_run']['id']==run['id'] and m['workflow_run']['head_sha']==run['head_sha'] and not m['expired']
assert m['size_in_bytes']==len(data) and m['digest']=='sha256:'+hashlib.sha256(data).hexdigest()
with zipfile.ZipFile('/tmp/candidate-proof.zip') as z:
 assert z.testzip() is None
 names=z.namelist();assert len(names)==len(set(names))
 for i in z.infolist():
  p=pathlib.PurePosixPath(i.filename);assert not p.is_absolute() and '..' not in p.parts and '\\' not in i.filename and not stat.S_ISLNK(i.external_attr>>16) and p.suffix in ['.json','.png']
  if p.suffix=='.json':json.loads(z.read(i))
 z.extractall('candidate')
f=json.loads(pathlib.Path('candidate/proof/FINAL_EVIDENCE.json').read_text())
assert f['status']=='PASS' and f['source_sha']==os.environ['TARGET_SHA'] and f['source_tree']==os.environ['TARGET_TREE'] and f['version']==os.environ['TARGET_VERSION']
assert f['candidate_engine_issues']==0 and f['baseline_engine_issues']==4 and f['cross_page_cases']==16 and f['canonical_pages']==8 and f['production']=='NOT_EXECUTED'
for k in ['native_upgrade','source_state_recovery','native_reapply','clean_install','corrupt_asset_guard']:assert f[k]=='PASS',k
pathlib.Path('proof/reverse.json').write_text(json.dumps({'status':'PASS','candidate_run':run['id'],'candidate_runner_sha':run['head_sha'],'artifact_id':m['id'],'bytes':len(data),'digest':m['digest'],'source_sha':f['source_sha'],'source_tree':f['source_tree'],'native_evidence':f},indent=2))
