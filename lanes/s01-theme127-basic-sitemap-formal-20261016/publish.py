import os,json,pathlib,subprocess,hashlib,zipfile,time
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
    note.write_text('优化普通内容页与HTML站点地图。修复目录跨列导致的首屏留白，按既有公开路由类型分组并跨组去除重复URL；桌面隐藏无效展开按钮。默认开发文案按语言替换，完整跨语言路径改为原生可展开区，保留全部发现链接。普通页摘要被动去除已注册短代码，空正文显示访客文案，默认正文保留已配置继续入口；正文按钮定位实际内容，无正文时进入工具目录，并本地化默认支持文案。\n\n真实双语WordPress/Polylang/M3U8、JS与无脚本、四种桌面宽度、正文/摘要/空态/目录、126→127、回退126、重装及全新安装验证通过。正文、元数据、配置、翻译及工具挂载保持；仅两个既有CSS owner变化。手机暂缓，Production由OWNER手工升级，真实使用待验收。\n\nExact source: '+ident['source_sha']+'; tree: '+ident['source_tree']+'; Candidate run: '+os.environ['CANDIDATE_RUN']+'.\n')
    probe=subprocess.run(['gh','release','view',tag,'--repo',repo],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    if probe.returncode:
        subprocess.run(['gh','release','create',tag,str(out/asset),'--repo',repo,'--target',os.environ[main_key],'--title',('VF Tools Theme V' if name=='theme' else 'VF Tools M3U8 V')+ident['version'],'--notes-file',str(note)],check=True)
    for read_attempt in range(6):
        try:
            live_tag=json.loads(gh('api','repos/'+repo+'/git/ref/tags/'+tag));break
        except subprocess.CalledProcessError:
            if read_attempt==5:raise
            time.sleep(2)
    assert live_tag['object']['sha']==os.environ[main_key]
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
