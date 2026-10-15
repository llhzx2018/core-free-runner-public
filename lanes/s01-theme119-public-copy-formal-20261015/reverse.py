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
 assert final['theme_source_sha']==os.environ['TESTED_SHA'] and final['theme_source_tree']==os.environ['TARGET_TREE'] and final['m3_source_sha']==os.environ['M3_SHA'] and final['m3_source_tree']==os.environ['M3_TREE']
 assert all(s=='PASS' for s in final['checks'].values()) and final['canonical_content_and_layout']=='PRESERVED'
 for name in ['copy-zh','copy-en','directory-provider','heading','reading-functions','clean-installed','frozen-source']:assert json.loads(z.read(name+'.json'))['status']=='PASS'
 assert json.loads(z.read('reading-functions.json'))['checks']==40 and json.loads(z.read('heading.json'))['checks']==160
 before=z.read('state-before.json')
 for phase in ['candidate','rollback','reapply','idempotent']:assert z.read('state-'+phase+'.json')==before
 for phase in ['baseline','candidate','rollback','reapply','clean']:
  p=json.loads(z.read('catalogue-'+phase+'.json'));assert p['status']=='PASS' and len(p['rows'])==8 and len(p['reading'])==6 and all(c['pass'] for c in p['checks'])
  assert sum(c['label']=='custom footer note retains exact authored wording' and c['pass'] for c in p['checks'])==2
  assert sum(c['label']=='custom footer copyright retained' and c['pass'] for c in p['checks'])==2
  for r in p['rows']:
   assert len(r['cards'])==11 and not r['overflow']
   if phase not in ['baseline','rollback']:assert all(c['tag']=='ARTICLE' and c['details']==1 and c['open'] is False and c['action']=='A' and c['nested'] is False and c['actionHeight']>=44 for c in r['cards'])
 identity=json.loads(z.read('identity.json'));assert identity['source_sha']==os.environ['TESTED_SHA'] and identity['source_tree']==os.environ['TARGET_TREE']
 (out/'tested-identity.json').write_text(json.dumps(identity,indent=2))
 (out/'candidate-reverse.json').write_text(json.dumps({'status':'PASS','run':run['id'],'artifact':meta['id'],'digest':meta['digest'],'sourceTreesVerified':True,'ownerRealUse':'POST_PRODUCTION_REQUIRED','production':'NOT_EXECUTED'},indent=2))
print('PASS exact Theme119 public copy and lifecycle artifact reverse verification')
