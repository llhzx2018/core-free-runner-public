import json,pathlib,hashlib,zipfile,stat,os
p=pathlib.Path('proof');i=json.loads((p/'identity.json').read_text());rel=json.loads((p/'release-meta.json').read_text());tag=json.loads(pathlib.Path('/tmp/tag-readback.json').read_text())
assert tag['object']['sha']==os.environ['PROMOTED_MAIN_SHA'] and rel['tag_name']=='v'+os.environ['TARGET_VERSION'] and rel['draft'] is False and rel['prerelease'] is False
assert len(rel['assets'])==1
a=rel['assets'][0];data=(pathlib.Path('delivered')/i['asset_name']).read_bytes()
assert a['name']==i['asset_name'] and a['size']==i['asset_bytes']==len(data) and hashlib.sha256(data).hexdigest()==i['asset_sha256']
assert data==(p/i['asset_name']).read_bytes()
with zipfile.ZipFile(pathlib.Path('delivered')/i['asset_name']) as z:
 assert z.testzip() is None and len(z.namelist())==568
 fp=hashlib.sha256()
 for info in sorted(z.infolist(),key=lambda n:n.filename):
  x=pathlib.PurePosixPath(info.filename);assert x.parts[0]=='vf-tool-m3u8' and not x.is_absolute() and '..' not in x.parts and not stat.S_ISLNK(info.external_attr>>16)
  relpath='/'.join(x.parts[1:]);fp.update((relpath+'\0'+hashlib.sha256(z.read(info)).hexdigest()+'\n').encode())
 assert fp.hexdigest()==i['runtime_fingerprint']
r={**i,'status':'PASS','promoted_main_sha':os.environ['PROMOTED_MAIN_SHA'],'tag_target':tag['object']['sha'],'release_id':rel['id'],'asset_id':a['id'],'published_at':rel['published_at'],'download_url':a['browser_download_url'],'candidate_run':os.environ['CANDIDATE_RUN'],'formal_run':os.environ['GITHUB_RUN_ID'],'formal_runner_sha':os.environ['GITHUB_SHA'],'production':'NOT_EXECUTED','owner_acceptance':'NOT_CLAIMED','exact_delivered_bytes':'PASS'}
(p/'FINAL_RELEASE.json').write_text(json.dumps(r,indent=2));print('VF_RELEASE_FINAL_BEGIN');print(json.dumps(r));print('VF_RELEASE_FINAL_END')

