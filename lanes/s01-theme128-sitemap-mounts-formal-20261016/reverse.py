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
 (out/'tested-identity.json').write_text(json.dumps(identity,indent=2))
 (out/'candidate-reverse.json').write_text(json.dumps({'status':'PASS','run':run['id'],'artifact':meta['id'],'digest':meta['digest'],'sourceTreesVerified':True,'ownerRealUse':'POST_PRODUCTION_REQUIRED','production':'NOT_EXECUTED'},indent=2))
print('PASS exact Theme128 mount-only sitemap lifecycle reverse verification')
