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
    note.write_text(('Theme：检查器相关工具区使用中英文专用标题与说明，识别旧通用默认值并保留明确的自定义文案。' if name=='theme' else 'M3U8：清空/编辑输入时专业区旧报告失效；中文结论与布尔值、完成进度准确显示；复制等待真实成功，失败时回退并明确提示，报告与导出保留。')+'\n\n实际剪贴板读回、脱敏、拒绝/回退/重试和双语 source/dist 用例通过；真实 WordPress/Polylang/Chromium 三工具、响应式、清洁安装/登录、升级/回退/再应用/重复安装通过。Shell/Header/Menu、Schema 与更新器不变。Production 仅 OWNER 手工升级；OWNER 实际使用验收待完成。\n\nExact source: '+ident['source_sha']+'; tree: '+ident['source_tree']+'; Candidate run: '+os.environ['CANDIDATE_RUN']+'.\n')
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
    print('PASS exact formal release and authenticated remote ZIP readback',name,result['version'])
