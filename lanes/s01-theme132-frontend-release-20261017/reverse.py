import os,json,subprocess,pathlib,hashlib,zipfile,io
def api(path):
    return subprocess.check_output(['gh','api','repos/llhzx2018/core-free-runner-public/'+path])
def verified_zip(prefix):
    run=json.loads(api('actions/runs/'+os.environ[prefix+'_RUN']))
    meta=json.loads(api('actions/artifacts/'+os.environ[prefix+'_ARTIFACT']))
    binary=api('actions/artifacts/'+os.environ[prefix+'_ARTIFACT']+'/zip')
    assert run['conclusion']=='success' and run['head_sha']==os.environ[prefix+'_SHA']
    assert meta['workflow_run']['id']==run['id'] and not meta['expired']
    assert meta['size_in_bytes']==len(binary)
    assert meta['digest']==os.environ[prefix+'_DIGEST']=='sha256:'+hashlib.sha256(binary).hexdigest()
    z=zipfile.ZipFile(io.BytesIO(binary))
    assert z.testzip() is None
    for f in z.infolist():
        p=pathlib.PurePosixPath(f.filename)
        assert not p.is_absolute() and '..' not in p.parts and p.suffix in ('.json','.png','.sha256')
    return z,run,meta
def get(z,name): return json.loads(z.read(name))
out=pathlib.Path('proof');out.mkdir(exist_ok=True)
z,run,meta=verified_zip('CANDIDATE')
source=get(z,'source.json')
assert source['status']=='PASS' and source['sha']==os.environ['TESTED_SHA']
assert source['tree']==os.environ['TARGET_TREE'] and source['version']=='UNCHANGED_CANDIDATE'
for name,count in [('public-browser.json',1178),('wordpress.json',31)]:
    checks=get(z,name)
    assert checks['status']=='PASS' and len(checks['checks'])==count,name
    assert all(check['pass'] for check in checks['checks'])
    assert checks['production']=='NOT_EXECUTED'
out.joinpath('candidate-reverse.json').write_text(json.dumps({
    'status':'PASS','run':run['id'],'artifact':meta['id'],'digest':meta['digest'],
    'source_sha':source['sha'],'source_tree':source['tree'],
    'browser_checks':1178,'wordpress_checks':31,'production':'NOT_EXECUTED'},indent=2))
z,run,meta=verified_zip('PRESERVATION')
ident=get(z,'identity.json')
pres=get(z,'PRESERVATION_EVIDENCE.json')
assert ident['status']=='PASS' and ident['source_sha']==os.environ['TESTED_SHA']
assert ident['source_tree']==os.environ['TARGET_TREE'] and ident['version']==os.environ['TARGET_VERSION']
assert ident['asset']=='vf-tools-theme_V'+os.environ['TARGET_VERSION']+'.zip'
assert ident['version_only_delta_to_verified_design']=='PASS'
assert pres['status']=='PASS' and pres['source_sha']==ident['source_sha']
assert pres['source_tree']==ident['source_tree'] and pres['version']==ident['version']
assert all(x=='PASS' for x in pres['checks'].values())
assert pres['protected_state']=='BYTE_IDENTICAL' and pres['review_records']==3
assert pres['production']=='NOT_EXECUTED'
for name,count in [('smoke-upgrade',80),('wordpress',31),('wordpress-clean',31),
                   ('smoke-rollback',40),('smoke-reapply',80),('smoke-clean',80)]:
    item=get(z,name+'.json')
    assert item['status']=='PASS' and len(item['checks'])==count
    assert all(c['pass'] for c in item['checks']),name
assert z.read('state-before.json')==z.read('state-upgrade.json')
for phase in ['rollback','reapply','idempotent','recovered']:
    assert z.read('state-reviews.json')==z.read('state-'+phase+'.json'),phase
assert z.read('state-clean-before.json')==z.read('state-clean-after.json')
out.joinpath('tested-identity.json').write_text(json.dumps(ident,indent=2))
out.joinpath('preservation-reverse.json').write_text(json.dumps({
    'status':'PASS','run':run['id'],'artifact':meta['id'],'digest':meta['digest'],
    'source_sha':ident['source_sha'],'source_tree':ident['source_tree'],
    'checks':pres['checks'],'production':'NOT_EXECUTED'},indent=2))
print('EXACT_SOURCE_THEME_133_PROOF_PASS')
