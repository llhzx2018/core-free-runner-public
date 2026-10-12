import os,subprocess,json,pathlib,zipfile,hashlib,time
def gh(*args): return subprocess.check_output(['gh',*args])
def api(path):
    for attempt in range(4):
        try: return gh('api',path)
        except subprocess.CalledProcessError:
            if attempt==3: raise
            time.sleep(2)
run=json.loads(api('repos/llhzx2018/core-free-runner-public/actions/runs/'+os.environ['FORMAL_RUN']))
jobs=json.loads(api('repos/llhzx2018/core-free-runner-public/actions/runs/'+os.environ['FORMAL_RUN']+'/jobs'))['jobs']
assert run['head_sha']==os.environ['FORMAL_SHA']
failed=[s['name'] for j in jobs for s in j['steps'] if s['conclusion']=='failure']
assert failed==['Artifact reverse readback'],failed
assert all(next(s for s in j['steps'] if s['name']=='Publish authorized private formal releases and authenticated remote readback')['conclusion']=='success' for j in jobs)
meta=json.loads(api('repos/llhzx2018/core-free-runner-public/actions/artifacts/'+os.environ['FORMAL_ARTIFACT']))
b=api('repos/llhzx2018/core-free-runner-public/actions/artifacts/'+os.environ['FORMAL_ARTIFACT']+'/zip')
assert meta['workflow_run']['id']==run['id'] and not meta['expired']
assert meta['digest']==os.environ['FORMAL_DIGEST']=='sha256:'+hashlib.sha256(b).hexdigest() and len(b)==meta['size_in_bytes']
pathlib.Path('/tmp/formal-proof.zip').write_bytes(b)
out=pathlib.Path('proof');out.mkdir(exist_ok=True)
results={}
with zipfile.ZipFile('/tmp/formal-proof.zip') as z:
    assert z.testzip() is None
    assert all(pathlib.PurePosixPath(n).suffix=='.json' and '..' not in pathlib.PurePosixPath(n).parts for n in z.namelist())
    for name,repo,main,tree,version in [('theme','llhzx2018/vf-tools-theme','THEME_MAIN','TARGET_TREE','TARGET_VERSION'),('m3u8','llhzx2018/vf-tools-m3u8','M3_MAIN','M3_TREE','M3_VERSION')]:
        ident=json.loads(z.read(name+'-FINAL_RELEASE.json'))
        assert ident['status']=='PASS' and ident['main_sha']==os.environ[main] and ident['source_tree']==os.environ[tree] and ident['version']==os.environ[version]
        tag=json.loads(api('repos/'+repo+'/git/ref/tags/'+ident['tag']))['object']['sha']
        assert tag==ident['main_sha']
        assert json.loads(api('repos/'+repo+'/git/commits/'+tag))['tree']['sha']==ident['source_tree']
        release=json.loads(api('repos/'+repo+'/releases/tags/'+ident['tag']))
        assert not release['draft'] and not release['prerelease'] and len(release['assets'])==1
        a=release['assets'][0]
        assert a['name']==ident['asset_name'] and a['size']==ident['asset_bytes'] and a['digest']=='sha256:'+ident['asset_sha256']
        dest=pathlib.Path('/tmp')/ident['asset_name']
        gh('release','download',ident['tag'],'--repo',repo,'--pattern',a['name'],'--output',str(dest))
        data=dest.read_bytes()
        assert len(data)==ident['asset_bytes'] and hashlib.sha256(data).hexdigest()==ident['asset_sha256']
        with zipfile.ZipFile(dest) as package: assert package.testzip() is None
        dest.unlink()
        results[name]=ident
    receipt={'status':'PASS','formalRun':run['id'],'formalArtifact':meta['id'],'digest':meta['digest'],'priorFailure':'Artifact reverse readback HTTP404; publication and remote asset gates succeeded','receiptRecovery':'PASS','components':results,'production':'NOT_EXECUTED'}
    (out/'FORMAL_RECEIPT_RECOVERY.json').write_text(json.dumps(receipt,indent=2))
print('PASS independent immutable release and receipt recovery')
