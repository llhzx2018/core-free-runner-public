import os,json,subprocess,pathlib,hashlib,zipfile,stat,io
def api(p):return subprocess.check_output(['gh','api','repos/llhzx2018/core-free-runner-public/'+p])
run=json.loads(api('actions/runs/38545197983'));m=json.loads(api('actions/artifacts/11884907900'));data=api('actions/artifacts/11884907900/zip')
assert run['conclusion']=='failure' and run['head_sha']=='fa7212d95567850bfce349f55132bca716cdbdac'
assert m['workflow_run']['id']==run['id'] and m['size_in_bytes']==len(data)==9260829 and not m['expired']
assert m['digest']=='sha256:8d62fb2252af9a1ea1d4c5542cb629fadd41d6f272dda8740b35a2db1bc9468c'=='sha256:'+hashlib.sha256(data).hexdigest()
out=pathlib.Path('proof');out.mkdir(exist_ok=True)
with zipfile.ZipFile(io.BytesIO(data)) as z:
 assert z.testzip() is None
 for f in z.infolist():
  p=pathlib.PurePosixPath(f.filename);assert not p.is_absolute() and '..' not in p.parts and not stat.S_ISLNK(f.external_attr>>16) and p.suffix in ['.json','.png']
  if p.suffix=='.json':json.loads(z.read(f))
 identity=json.loads(z.read('identity.json'));assert identity['source_sha']==os.environ['TARGET_SHA'] and identity['source_tree']==os.environ['TARGET_TREE'] and identity['version']==os.environ['TARGET_VERSION']
 assert json.loads(z.read('native-functions.json'))['checks']==40
 before=z.read('reading-state-before.json')
 for phase in ['candidate','rollback','reapply','idempotent']:assert z.read('reading-state-'+phase+'.json')==before
 for phase in ['baseline','candidate','rollback','reapply']:
  r=json.loads(z.read('reading-'+phase+'.json'));assert r['status']=='PASS' and len(r['rows'])==48 and all(c['pass'] for c in r['checks'])
 for phase in ['candidate','reapply','clean']:
  r=json.loads(z.read('template-'+phase+'.json'));assert r['status']=='PASS' and r['registeredContexts']==20 and len(r['rows'])==(160 if phase=='candidate' else 40) and all(c['pass'] for c in r['checks'])
  r=json.loads(z.read('tools-'+phase+'.json'));assert r['status']=='PASS' and all(c['pass'] for c in r['checks']) and r['video']['width']>0 and r['video']['height']>0
 for name in ['state-upgrade','state-rollback','state-reapply','state-idempotent','desktop','public-template-baseline','public-detail-heading','public-template-css','next-route-en','next-route-zh','three-tool-recovery','browser-stream-i18n-php','embed-alias-php','attribute-php']:
  assert json.loads(z.read(name+'.json'))['status']=='PASS',name
 fail=json.loads(z.read('reading-clean-failure.json'));assert len(fail['rows'])==48 and len(fail['checks'])==600
 assert [c['label'] for c in fail['checks'] if not c['pass']]==['body text and module order retained across all configurations']
 baseline=json.loads(z.read('reading-baseline.json'))['rows']
 def module_keys(row):
  import re
  return [re.search(r'vf-theme-module-frame--([a-z_]+)',s)[1] for s in row['moduleOrder']]
 assert all(r['article']['text']==b['article']['text'] and module_keys(r)==module_keys(b) for r,b in zip(fail['rows'],baseline))
 for f in z.infolist():
  if f.filename.endswith('-failure.json') or f.filename=='lane-identity.json':continue
  (out/f.filename).write_bytes(z.read(f))
(out/'prior-identity.json').write_text(json.dumps(identity,indent=2))
receipt={'status':'PASS','prior_run':run['id'],'prior_conclusion':'FAILURE_HARNESS_FINAL_CLEAN_CLASS_ASSERTION','artifact':m['id'],'digest':m['digest'],'exact_source_sha':os.environ['TARGET_SHA'],'passed_independent_evidence':'RETAINED','clean_retest':'REQUIRED','correction':'Compare ordered module identities; fresh-install has-context-override configuration marker is not module identity/order; body text remains exact'}
(out/'prior-evidence-reverse.json').write_text(json.dumps(receipt,indent=2));print('PUBLIC_SAFE_RESUME',json.dumps(receipt))
