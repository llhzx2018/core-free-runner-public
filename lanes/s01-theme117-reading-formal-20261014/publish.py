import os,json,pathlib,subprocess,hashlib,zipfile
def gh(*args): return subprocess.check_output(['gh',*args])
out=pathlib.Path('proof');readback=pathlib.Path('readback');readback.mkdir(exist_ok=True)
items=[('theme','llhzx2018/vf-tools-theme','identity.json','TARGET_MAIN_SHA','TARGET_TREE')]
authority=json.loads(pathlib.Path('lane/release-authority.json').read_text())
assert authority['releaseInput']['publicAuthorityReleaseGate']=='PASS'
assert authority['releaseInput']['productionAutoApply'] is False
assert authority['releaseInput']['ownerRealUse']=='POST_PRODUCTION_REQUIRED'
assert authority['candidate']['sha']==os.environ['TESTED_SHA']
assert authority['candidate']['tree']==os.environ['TARGET_TREE']
assert authority['promoted']['theme']==os.environ['TARGET_MAIN_SHA']
for domain,entry in authority['publicAuthority'].items():
    assert entry['applicability'] in ['REQUIRED','N_A']
    if entry['applicability']=='REQUIRED':
        assert entry['evidence']['status']=='PASS'
        assert str(entry['evidence']['run'])==os.environ['CANDIDATE_RUN']
        assert entry['evidence']['themeSha']==os.environ['TESTED_SHA']
# Preflight the Theme source before creating its release.
for name,repo,file,main_key,tree_key in items:
    head=json.loads(gh('api','repos/'+repo+'/git/ref/heads/main'))['object']['sha']
    assert head==os.environ[main_key]
    tree=json.loads(gh('api','repos/'+repo+'/git/commits/'+head))['tree']['sha']
    assert tree==os.environ[tree_key]
for name,repo,file,main_key,tree_key in items:
    ident=json.loads((out/file).read_text())
    asset=ident.get('asset',ident.get('asset_name'));tag='v'+ident['version']
    note=(out/(name+'-notes.md'))
    note.write_text('桌面指南与文章短文增加紧凑章节索引和键盘焦点跳转，主入口直达正文；优化阅读字号、行距及辅助模块与已保存阅读宽度的对齐。保留全文目录门槛、关闭与旧目录状态、正文、模块顺序和工具配置。\n\n40 项实际 PHP 行为、双语四档桌面宽度三种阅读宽度、20 登记页型和三工具回归，以及 116→117 升级、回退116、重装、全新安装与状态保留验证通过。手机测试暂缓；Production 由 OWNER 手工升级，最终真实使用待验收。\n\nExact source: '+ident['source_sha']+'; tree: '+ident['source_tree']+'; Candidate run: '+os.environ['CANDIDATE_RUN']+'.\n')
    probe=subprocess.run(['gh','release','view',tag,'--repo',repo],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    if probe.returncode:
        subprocess.run(['gh','release','create',tag,str(out/asset),'--repo',repo,'--target',os.environ[main_key],'--title',('VF Tools Theme V' if name=='theme' else 'VF Tools M3U8 V')+ident['version'],'--notes-file',str(note)],check=True)
    assert json.loads(gh('api','repos/'+repo+'/git/ref/tags/'+tag))['object']['sha']==os.environ[main_key]
    release=json.loads(gh('api','repos/'+repo+'/releases/tags/'+tag))
    assert not release['draft'] and not release['prerelease'] and len(release['assets'])==1
    a=release['assets'][0]
    assert a['name']==asset and a['size']==ident['asset_bytes'] and a['digest']=='sha256:'+ident['asset_sha256']
    remote=readback/asset
    subprocess.run(['gh','release','download',tag,'--repo',repo,'--pattern',asset,'--output',str(remote)],check=True)
    assert remote.read_bytes()==(out/asset).read_bytes()
    assert hashlib.sha256(remote.read_bytes()).hexdigest()==ident['asset_sha256']
    with zipfile.ZipFile(remote) as z: assert z.testzip() is None
    result=dict(ident,status='PASS',repository=repo,main_sha=os.environ[main_key],release_id=release['id'],asset_id=a['id'],tag=tag,asset_name=asset,released_at=release['published_at'],production='NOT_EXECUTED',ownerRealUse='POST_PRODUCTION_REQUIRED')
    (out/(name+'-FINAL_RELEASE.json')).write_text(json.dumps(result,indent=2))
    print('PUBLIC_SAFE_RELEASE',json.dumps(dict(result,component=name)))
