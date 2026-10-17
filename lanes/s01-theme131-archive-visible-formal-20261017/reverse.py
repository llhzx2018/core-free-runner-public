import os,json,subprocess,pathlib,hashlib,zipfile,stat,io
def api(p):return subprocess.check_output(['gh','api','repos/llhzx2018/core-free-runner-public/'+p])
run=json.loads(api('actions/runs/'+os.environ['CANDIDATE_RUN']));meta=json.loads(api('actions/artifacts/'+os.environ['CANDIDATE_ARTIFACT']));data=api('actions/artifacts/'+os.environ['CANDIDATE_ARTIFACT']+'/zip')
assert run['conclusion']=='success' and run['head_sha']==os.environ['CANDIDATE_SHA']
assert meta['workflow_run']['id']==run['id'] and not meta['expired'] and meta['size_in_bytes']==len(data)
assert meta['digest']==os.environ['CANDIDATE_DIGEST']=='sha256:'+hashlib.sha256(data).hexdigest()
out=pathlib.Path('proof');out.mkdir(exist_ok=True)
with zipfile.ZipFile(io.BytesIO(data)) as z:
 assert z.testzip() is None
 for f in z.infolist():
  p=pathlib.PurePosixPath(f.filename);assert not p.is_absolute() and '..' not in p.parts and not stat.S_ISLNK(f.external_attr>>16) and p.suffix in ['.json','.png']
  if p.suffix=='.json':json.loads(z.read(f))
 final=json.loads(z.read('FINAL_EVIDENCE.json'));assert final['status']=='PASS' and final['production']=='NOT_EXECUTED' and final['mobile']=='NOT_RUN_OWNER_DEFERRED'
 assert final['source_sha']==os.environ['TESTED_SHA'] and final['source_tree']==os.environ['TARGET_TREE'] and final['version']==os.environ['TARGET_VERSION']
 assert all(v=='PASS' for v in final['checks'].values()) and final['protected_configuration_content_translations']=='UNCHANGED'
 for name in ['wordpress','wordpress-clean','browser-candidate','browser-reapply','browser-clean']:
  f=json.loads(z.read(name+'.json'));assert f['status']=='PASS' and len(f['checks'])>=20 and all(c['pass'] for c in f['checks'])
 assert json.loads(z.read('css-owner-equality.json'))['status']=='PASS'
 assert json.loads(z.read('directory-regression.json'))['status']=='PASS'
 assert json.loads(z.read('mount-contract.json'))['status']=='PASS'
 assert json.loads(z.read('css-owner-equality.json'))['status']=='PASS'
 assert json.loads(z.read('directory-regression.json'))['status']=='PASS'
 assert json.loads(z.read('mount-contract.json'))['status']=='PASS'
 before=z.read('state-before.json')
 for phase in ['candidate','rollback','reapply','idempotent']:assert z.read('state-'+phase+'.json')==before
 assert z.read('state-clean-before.json')==z.read('state-clean-after.json')
 identity=json.loads(z.read('identity.json'));assert identity['source_sha']==os.environ['TESTED_SHA'] and identity['source_tree']==os.environ['TARGET_TREE']
 perf=json.loads(z.read('performance-candidate.json'));assert perf['status']=='PASS' and len(perf['checks'])==14 and all(c['pass'] for c in perf['checks'])
 assert json.loads(z.read('css-owner-equality.json'))['changed_css_owners']==0
 login=json.loads(pathlib.Path('lane/login-proof.json').read_text())
 lr=json.loads(api('actions/runs/'+str(login['run'])));lm=json.loads(api('actions/artifacts/'+str(login['artifact']['id'])));lb=api('actions/artifacts/'+str(login['artifact']['id'])+'/zip')
 assert lr['conclusion']=='success' and lr['head_sha']==login['runner_sha']
 assert lm['workflow_run']['id']==lr['id'] and lm['size_in_bytes']==len(lb)==login['artifact']['size_in_bytes'] and not lm['expired']
 assert lm['digest']==login['artifact']['digest']=='sha256:'+hashlib.sha256(lb).hexdigest()
 with zipfile.ZipFile(io.BytesIO(lb)) as lz:
  assert lz.testzip() is None
  for f in lz.infolist():
   path=pathlib.PurePosixPath(f.filename);assert not path.is_absolute() and '..' not in path.parts and not stat.S_ISLNK(f.external_attr>>16) and path.suffix in ['.json','.png']
  lf=json.loads(lz.read('login-FINAL_EVIDENCE.json'));assert lf['status']=='PASS' and lf['source_sha']==os.environ['TESTED_SHA'] and lf['source_tree']==os.environ['TARGET_TREE'] and lf['version']==os.environ['TARGET_VERSION'] and lf['protected_state']=='BYTE_IDENTICAL'
  assert lz.read('state-before.json')==lz.read('state-after.json')
  for phase in ['baseline','candidate']:
   checks=json.loads(lz.read('login-browser-'+phase+'.json'));assert checks['status']=='PASS' and all(c['pass'] for c in checks['checks']) and len(checks['checks'])>=(11 if phase=='baseline' else 15)
  li=json.loads(lz.read('identity.json'))
  for key in ['source_sha','source_tree','version','asset_bytes','asset_sha256','runtime_files','runtime_fingerprint']:assert li[key]==identity[key],key
 (out/'login-proof-reverse.json').write_text(json.dumps({'status':'PASS','run':lr['id'],'head':lr['head_sha'],'artifact':lm['id'],'digest':lm['digest'],'source':lf['source_sha'],'protected_state':'BYTE_IDENTICAL'}))
 (out/'tested-identity.json').write_text(json.dumps(identity,indent=2))
 (out/'candidate-reverse.json').write_text(json.dumps({'status':'PASS','run':run['id'],'artifact':meta['id'],'digest':meta['digest'],'sourceTreesVerified':True,'ownerRealUse':'POST_PRODUCTION_REQUIRED','production':'NOT_EXECUTED'},indent=2))
print('PASS exact Theme131 public archive visibility lifecycle reverse verification')
