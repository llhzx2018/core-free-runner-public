import os,json,subprocess,pathlib,hashlib,zipfile,stat,io
def api(p):return subprocess.check_output(['gh','api','repos/llhzx2018/core-free-runner-public/'+p])
run=json.loads(api('actions/runs/'+os.environ['CANDIDATE_RUN']));meta=json.loads(api('actions/artifacts/'+os.environ['CANDIDATE_ARTIFACT']));data=api('actions/artifacts/'+os.environ['CANDIDATE_ARTIFACT']+'/zip')
assert run['conclusion']=='success'and run['head_sha']==os.environ['CANDIDATE_SHA']
assert meta['workflow_run']['id']==run['id']and not meta['expired']and meta['size_in_bytes']==len(data)
assert meta['digest']==os.environ['CANDIDATE_DIGEST']=='sha256:'+hashlib.sha256(data).hexdigest()
out=pathlib.Path('proof');out.mkdir(exist_ok=True)
with zipfile.ZipFile(io.BytesIO(data))as z:
 assert z.testzip()is None
 for f in z.infolist():
  p=pathlib.PurePosixPath(f.filename);assert not p.is_absolute()and'..'not in p.parts and not stat.S_ISLNK(f.external_attr>>16)and p.suffix in ['.json','.png']
 final=json.loads(z.read('FINAL_EVIDENCE.json'));assert final['status']=='PASS'and all(v=='PASS'for v in final['checks'].values())
 assert final['source_sha']==os.environ['TESTED_SHA']and final['source_tree']==os.environ['TARGET_TREE']and final['version']==os.environ['TARGET_VERSION']
 assert final['protected_state']=='BYTE_IDENTICAL'and final['production']=='NOT_EXECUTED'and final['review_records']==3
 for name,count in [('public-browser',1160),('shell-result',88),('wordpress',31),('wordpress-clean',31),('smoke-rollback',40),('smoke-reapply',80),('smoke-clean',80)]:
  d=json.loads(z.read(name+'.json'));assert d['status']=='PASS'and len(d['checks'])==count and all(c['pass']for c in d['checks'])
 assert z.read('state-before.json')==z.read('state-upgrade.json')
 for phase in ['rollback','reapply','idempotent','recovered']:assert z.read('state-reviews.json')==z.read('state-'+phase+'.json')
 assert z.read('state-clean-before.json')==z.read('state-clean-after.json')
 identity=json.loads(z.read('identity.json'));assert identity['source_sha']==os.environ['TESTED_SHA']and identity['source_tree']==os.environ['TARGET_TREE']
 (out/'tested-identity.json').write_text(json.dumps(identity,indent=2))
 (out/'candidate-reverse.json').write_text(json.dumps({'status':'PASS','run':run['id'],'artifact':meta['id'],'digest':meta['digest'],'source_sha':final['source_sha'],'source_tree':final['source_tree'],'review_records':3,'complete_lifecycle':'PASS','ownerRealUse':'POST_PRODUCTION_REQUIRED','production':'NOT_EXECUTED'},indent=2))

# A focused same-package lifecycle extends preservation to all seven Theme profiles,
# provider mounts and real bilingual taxonomy relationships without repeating the UI matrix.
srun=json.loads(api('actions/runs/'+os.environ['PRESERVATION_RUN']));sm=json.loads(api('actions/artifacts/'+os.environ['PRESERVATION_ARTIFACT']));sd=api('actions/artifacts/'+os.environ['PRESERVATION_ARTIFACT']+'/zip')
assert srun['conclusion']=='success' and srun['head_sha']==os.environ['PRESERVATION_SHA']
assert sm['workflow_run']['id']==srun['id'] and not sm['expired'] and sm['size_in_bytes']==len(sd)
assert sm['digest']==os.environ['PRESERVATION_DIGEST']=='sha256:'+hashlib.sha256(sd).hexdigest()
with zipfile.ZipFile(io.BytesIO(sd)) as z:
 assert z.testzip() is None
 for f in z.infolist():
  p=pathlib.PurePosixPath(f.filename);assert not p.is_absolute() and '..' not in p.parts and not stat.S_ISLNK(f.external_attr>>16) and p.suffix in ['.json','.png']
 sf=json.loads(z.read('PRESERVATION_EVIDENCE.json'));assert sf['status']=='PASS' and all(v=='PASS' for v in sf['checks'].values())
 assert sf['source_sha']==os.environ['TESTED_SHA'] and sf['source_tree']==os.environ['TARGET_TREE'] and sf['version']==os.environ['TARGET_VERSION']
 assert sf['protected_state']=='BYTE_IDENTICAL' and sf['production']=='NOT_EXECUTED' and sf['review_records']==3
 for name,count in [('smoke-upgrade',80),('wordpress',31),('wordpress-clean',31),('smoke-rollback',40),('smoke-reapply',80),('smoke-clean',80)]:
  d=json.loads(z.read(name+'.json'));assert d['status']=='PASS' and len(d['checks'])==count and all(c['pass'] for c in d['checks'])
 assert z.read('state-before.json')==z.read('state-upgrade.json')
 for phase in ['rollback','reapply','idempotent','recovered']:assert z.read('state-reviews.json')==z.read('state-'+phase+'.json')
 assert z.read('state-clean-before.json')==z.read('state-clean-after.json')
 snap=json.loads(z.read('state-before.json'));assert all(k in snap['sections'] for k in ['vf_theme_ads','vf_theme_seo','provider_mounts','translations','terms','term_taxonomy'])
 si=json.loads(z.read('identity.json'));assert si==identity
 (out/'preservation-reverse.json').write_text(json.dumps({'status':'PASS','run':srun['id'],'artifact':sm['id'],'digest':sm['digest'],'source_sha':sf['source_sha'],'source_tree':sf['source_tree'],'package_identity_equal':True,'complete_lifecycle':'PASS','covered_additionally':['ads','seo','provider_mounts','translation_relationships','term_identity'],'production':'NOT_EXECUTED'},indent=2))
