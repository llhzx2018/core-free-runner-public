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
    assert final['theme_source_sha']==os.environ['FIXTURE_THEME_SHA'] and final['theme_source_tree']==os.environ['FIXTURE_THEME_TREE']
    assert final['m3_source_sha']==os.environ['TESTED_SOURCE_SHA'] and final['m3_source_tree']==os.environ['TESTED_SOURCE_TREE']
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
    recovery=json.loads(z.read('three-tool-recovery-node.json'))
    assert recovery['checks']==69 and recovery['failed']==0 and all(c['pass'] for c in recovery['records'])
    recovery_browser=json.loads(z.read('three-tool-recovery-browser.json'))
    assert recovery_browser['status']=='PASS' and len(recovery_browser['cases'])==12
    assert all(all(v=='PASS' for k,v in case.items() if k not in ['locale','width','tool']) for case in recovery_browser['cases'])
    for name in ['presentation-en.json','presentation-zh.json']:
        assert json.loads(z.read(name))['checks']=='PASS'
    for name in ['launchbar-en.json','launchbar-zh.json']:
        assert json.loads(z.read(name))['status']=='PASS'
    for name in ['m3-identity.json']:
        ident=json.loads(z.read(name));assert ident['status']=='PASS'
        (out/('tested-'+name)).write_text(json.dumps(ident,indent=2))
    (out/'candidate-reverse.json').write_text(json.dumps({'status':'PASS','run':run['id'],'artifact':meta['id'],'digest':meta['digest'],'sourceTreesVerified':True,'ownerRealUse':'POST_PRODUCTION_REQUIRED','production':'NOT_EXECUTED'},indent=2))
print('PASS exact M3U8 candidate artifact reverse verification')

# A parallel metadata-only main commit must survive promotion. Prove every tested
# material file unchanged instead of treating old VF_PROJECT metadata as current.
tested=os.environ['TESTED_SOURCE_SHA']
changes=subprocess.check_output(['git','-C','target','diff','--name-only',tested,'HEAD'],text=True).splitlines()
assert set(changes)<= {'VF_PROJECT.json'},changes
runtime=lambda ref:subprocess.check_output(['git','-C','target','rev-parse',ref+':src'],text=True).strip()
assert runtime(tested)==runtime('HEAD')
subprocess.run(['node','target/tests/three-tool-recovery.node.cjs'],check=True,stdout=subprocess.DEVNULL)
(out/'promotion-source-identity.json').write_text(json.dumps({'status':'PASS','tested_sha':tested,'formal_sha':os.environ['TARGET_SHA'],'runtime_src_tree':runtime('HEAD'),'metadata_only_delta':changes,'exact_runtime_bytes':'PASS','actual_module_cases':69},indent=2))

