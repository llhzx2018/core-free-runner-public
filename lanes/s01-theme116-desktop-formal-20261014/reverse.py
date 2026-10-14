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
    assert final['theme_source_sha']==os.environ['TESTED_SHA'] and final['theme_source_tree']==os.environ['TARGET_TREE']
    assert final['m3_source_sha']==os.environ['M3_SHA'] and final['m3_source_tree']==os.environ['M3_TREE']
    assert all(s=='PASS' for s in final['checks'].values())
    assert {'state-upgrade','state-rollback','state-reapply','state-idempotent','tools-candidate','tools-reapply','tools-clean','clean-installed'} <= set(final['checks'])
    for phase in ['candidate','reapply','clean']:
        p=json.loads(z.read('tools-'+phase+'.json'))
        assert p['status']=='PASS' and all(c['pass'] for c in p['checks'])
        assert p['video']['width']>0 and p['video']['height']>0
    for name in ['presentation-en.json','presentation-zh.json']:
        assert json.loads(z.read(name))['checks']=='PASS'
    for name in ['launchbar-en.json','launchbar-zh.json']:
        assert json.loads(z.read(name))['status']=='PASS'
    for name in ['public-template-baseline.json','browser-stream-i18n-php.json']:
        assert json.loads(z.read(name))['status']=='PASS'
    for locale in ['en','zh']:
        proof=json.loads(z.read('next-route-'+locale+'.json'))
        assert proof['status']=='PASS' and proof['checks']==100 and proof['locale']==locale
    recovery=json.loads(z.read('three-tool-recovery.json'))
    assert recovery['checks']==69 and recovery['passed']==69 and recovery['failed']==0
    heading=json.loads(z.read('public-detail-heading.json'))
    assert heading['status']=='PASS' and heading['checks']==160,heading
    assert json.loads(z.read('public-template-css.json'))['status']=='PASS'
    for phase in ['candidate','reapply','clean']:
        template=json.loads(z.read('template-'+phase+'.json'))
        assert template['status']=='PASS' and template['registeredContexts']==20
        assert len(template['rows'])==(160 if phase=='candidate' else 40)
        assert all(check['pass'] for check in template['checks'])
        assert len(template['nativeRows'])==4
        for native in template['nativeRows']:
            if native['path']=='/':
                assert native['outerPadding']==0 and native['outerRadius']==0 and native['outerShadow']=='none'
                assert native['taskBackground']=='none' and native['headingAlign']=='left' and native['sectionPadding']==0 and native['duplicates']==0
            else:
                assert native['path']=='/tools/' and native['y']<650 and native['height']>=44 and native['inputRatio']>.8 and native['centerDelta']<1
    desktop=json.loads(z.read('desktop.json'));assert desktop['status']=='PASS' and desktop['source_sha']==os.environ['TESTED_SHA'] and len(desktop['rows'])==32 and desktop['mobile']=='NOT_RUN_OWNER_DEFERRED'
    for name in ['identity.json']:
        ident=json.loads(z.read(name));assert ident['status']=='PASS'
        (out/('tested-'+name)).write_text(json.dumps(ident,indent=2))
    (out/'candidate-reverse.json').write_text(json.dumps({'status':'PASS','run':run['id'],'artifact':meta['id'],'digest':meta['digest'],'sourceTreesVerified':True,'ownerRealUse':'POST_PRODUCTION_REQUIRED','production':'NOT_EXECUTED'},indent=2))
print('PASS exact Theme candidate artifact reverse verification')
