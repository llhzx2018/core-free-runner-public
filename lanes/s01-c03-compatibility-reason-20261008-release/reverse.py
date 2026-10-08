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
assert f['overview_browser_cases']==17 and f['overview_unit_cases']==21 and f['diagnostic_unit_cases']==5 and f['compatibility_browser_cases']==22 and f['compatibility_unit_cases']==52 and f['production']=='NOT_EXECUTED'
b=json.loads(pathlib.Path('candidate/proof/overview-browser.json').read_text());u=json.loads(pathlib.Path('candidate/proof/overview-unit.json').read_text())
assert b['status']==u['status']=='PASS' and not b['errors']
assert len({n['width'] for n in b['cases'] if 'width' in n})==6
for k in ['native_upgrade','source_state_recovery','native_reapply','clean_install','corrupt_asset_guard']:assert f[k]=='PASS',k
pathlib.Path('proof/reverse.json').write_text(json.dumps({'status':'PASS','candidate_run':run['id'],'candidate_runner_sha':run['head_sha'],'artifact_id':m['id'],'bytes':len(data),'digest':m['digest'],'source_sha':f['source_sha'],'source_tree':f['source_tree'],'native_evidence':f},indent=2))


c=json.loads(pathlib.Path('candidate/proof/compatibility-browser.json').read_text());v=json.loads(pathlib.Path('candidate/proof/compatibility-unit.json').read_text());assert c['status']==v['status']=='PASS' and not c['errors'] and len(c['cases'])==22 and len(v['cases'])==52
assert len({n['width'] for n in c['cases'] if 'width' in n})==6

d=json.loads(pathlib.Path('candidate/proof/compatibility-dependency-native.json').read_text());assert d['status']=='PASS' and len(d['cases'])==8 and f['compatibility_dependency_native_cases']==8 and d['meaning']=='CONTROLLED_DISPOSABLE_OPS_DB_INPUT_ACTUAL_OWNER_READER'
