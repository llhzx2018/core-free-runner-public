import os,json,hashlib,zipfile,pathlib,subprocess,stat
def api(path): return subprocess.check_output(['gh','api',path])
run=json.loads(api('repos/llhzx2018/core-free-runner-public/actions/runs/'+os.environ['CANDIDATE_RUN']))
meta=json.loads(api('repos/llhzx2018/core-free-runner-public/actions/artifacts/'+os.environ['CANDIDATE_ARTIFACT']))
data=api('repos/llhzx2018/core-free-runner-public/actions/artifacts/'+os.environ['CANDIDATE_ARTIFACT']+'/zip')
assert run['conclusion']=='success' and run['head_sha']==os.environ['CANDIDATE_SHA']
assert meta['workflow_run']['id']==run['id'] and not meta['expired']
assert meta['digest']==os.environ['CANDIDATE_DIGEST']=='sha256:'+hashlib.sha256(data).hexdigest()
assert meta['size_in_bytes']==len(data)
pathlib.Path('/tmp/checker-candidate-proof.zip').write_bytes(data)
out=pathlib.Path('proof');out.mkdir(exist_ok=True)
with zipfile.ZipFile('/tmp/checker-candidate-proof.zip') as z:
    assert z.testzip() is None
    for item in z.infolist():
        p=pathlib.PurePosixPath(item.filename)
        assert not p.is_absolute() and '..' not in p.parts and not stat.S_ISLNK(item.external_attr>>16)
        assert p.suffix in ['.json','.png']
    final=json.loads(z.read('FINAL_EVIDENCE.json'))
    assert final['status']=='PASS' and final['production']=='NOT_EXECUTED'
    assert final['theme_source_sha']==os.environ['TARGET_SHA'] and final['theme_source_tree']==os.environ['TARGET_TREE']
    assert final['m3_source_sha']==os.environ['M3_SHA'] and final['m3_source_tree']==os.environ['M3_TREE']
    assert all(s=='PASS' for s in final['checks'].values())
    assert {'state-upgrade','state-rollback','state-reapply','state-idempotent','tools-candidate','tools-reapply','tools-clean','clean-installed'} <= set(final['checks'])
    for phase in ['candidate','reapply','clean']:
        p=json.loads(z.read('tools-'+phase+'.json'))
        assert p['status']=='PASS' and all(c['pass'] for c in p['checks'])
        assert p['video']['width']>0 and p['video']['height']>0
    copy=json.loads(z.read('result-copy-browser.json'))
    assert len(copy['cases'])==12 and all(c['state']=='PASS' for c in copy['cases'])
    clipboard=json.loads(z.read('clipboard-browser.json'))
    assert clipboard['status']=='PASS' and len(clipboard['cases'])==8
    assert all(all(value=='PASS' for key,value in case.items() if key not in ['asset','locale','width']) for case in clipboard['cases'])
    for name in ['presentation-en.json','presentation-zh.json']:
        assert json.loads(z.read(name))['checks']=='PASS'
    for name in ['launchbar-en.json','launchbar-zh.json']:
        assert json.loads(z.read(name))['status']=='PASS'
    for name in ['identity.json','m3-identity.json']:
        ident=json.loads(z.read(name));assert ident['status']=='PASS'
        (out/('tested-'+name)).write_text(json.dumps(ident,indent=2))
    (out/'candidate-reverse.json').write_text(json.dumps({'status':'PASS','run':run['id'],'artifact':meta['id'],'digest':meta['digest'],'sourceTreesVerified':True,'ownerRealUse':'POST_PRODUCTION_REQUIRED','production':'NOT_EXECUTED'},indent=2))
print('PASS exact dual candidate artifact reverse verification')
