import os,json,pathlib,subprocess,hashlib,zipfile
def gh(*args): return subprocess.check_output(['gh',*args])
out=pathlib.Path('proof');readback=pathlib.Path('readback');readback.mkdir(exist_ok=True)
items=[('theme','llhzx2018/vf-tools-theme','identity.json','TARGET_MAIN_SHA','TARGET_TREE'),('m3u8','llhzx2018/vf-tools-m3u8','m3-identity.json','M3_MAIN_SHA','M3_TREE')]
# Preflight both products before creating either release.
for name,repo,file,main_key,tree_key in items:
    head=json.loads(gh('api','repos/'+repo+'/git/ref/heads/main'))['object']['sha']
    assert head==os.environ[main_key]
    tree=json.loads(gh('api','repos/'+repo+'/git/commits/'+head))['tree']['sha']
    assert tree==os.environ[tree_key]
for name,repo,file,main_key,tree_key in items:
    ident=json.loads((out/file).read_text())
    asset=ident.get('asset',ident.get('asset_name'));tag='v'+ident['version']
    note=(out/(name+'-notes.md'))
    note.write_text(('Theme：已有效呈现推荐工具时移除重复的默认下一步；推荐为空、关闭、失败、移动端隐藏或排序在后时保留回退，自定义标题与说明保留。' if name=='theme' else 'M3U8：三个工具保留内部步骤，流测试和嵌入页移除重复通用引导；中文页翻译登记默认工具名称，自定义名称及其他工具保留。')+'\n\n旧源码问题重现，中英文各100项真实PHP呈现、69项恢复回归、实际WordPress/Polylang/MariaDB/Chromium三工具播放、真实复制与导出、六宽度与键盘、清洁安装/登录、升级/回退/重用通过。Shell/Header/Menu、Schema与更新器不变。Production仅OWNER手工升级；OWNER真实使用待验收。\n\nExact source: '+ident['source_sha']+'; tree: '+ident['source_tree']+'; Candidate run: '+os.environ['CANDIDATE_RUN']+'.\n')
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
