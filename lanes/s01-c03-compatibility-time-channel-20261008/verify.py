import json,pathlib,os,hashlib,zipfile,stat
m=json.loads(pathlib.Path('target/projects/S01-C03.json').read_text());f=json.loads(pathlib.Path('proof/formal-reverse.json').read_text())['final'];r=json.loads(pathlib.Path('/tmp/real-release.json').read_text());data=(pathlib.Path('delivered')/m['asset_name']).read_bytes()
assert m['target_version']==os.environ['TARGET_VERSION'] and len(m['from_versions'])==41 and os.environ['SOURCE_VERSION'] in m['from_versions'] and '1.25.58' not in m['from_versions']
assert m['package_slug']=='vf-tool-m3u8' and m['plugin_file']=='vf-tool-m3u8/vf-tool-m3u8.php' and m['locator_cutover'] is False and m['schema_from']==m['schema_to']=='1.3.0'
assert m['asset_bytes']==f['asset_bytes']==len(data) and m['asset_sha256']==f['asset_sha256']==hashlib.sha256(data).hexdigest()
assert r['id']==f['release_id'] and r['tag_name']==m['release_tag'] and not r['draft'] and not r['prerelease']
a=next(n for n in r['assets'] if n['name']==m['asset_name']);assert a['id']==f['asset_id'] and a['size']==len(data)
with zipfile.ZipFile(pathlib.Path('delivered')/m['asset_name']) as z:
 assert z.testzip() is None and len(z.namelist())==568
 fp=hashlib.sha256()
 for i in sorted(z.infolist(),key=lambda x:x.filename):
  p=pathlib.PurePosixPath(i.filename);assert not p.is_absolute() and '..' not in p.parts and p.parts[0]=='vf-tool-m3u8' and not stat.S_ISLNK(i.external_attr>>16)
  rel='/'.join(p.parts[1:]);fp.update((rel+'\0'+hashlib.sha256(z.read(i)).hexdigest()+'\n').encode())
 assert fp.hexdigest()==m['runtime_fingerprint']==m['runtime_fingerprint_sha256']==f['runtime_fingerprint']
result={'status':'PASS','source_sha':os.environ['TARGET_SHA'],'source_tree':os.environ['TARGET_TREE'],'component_source_sha':os.environ['COMPONENT_SOURCE_SHA'],'version':m['target_version'],'original_core_ci':'PASS','manifest':m,'release_id':r['id'],'asset_id':a['id'],'exact_remote_asset':'PASS','from_count':len(m['from_versions']),'only_changed_file':'projects/S01-C03.json','production':'NOT_EXECUTED','owner_acceptance':'NOT_CLAIMED','run_id':os.environ['GITHUB_RUN_ID'],'runner_sha':os.environ['GITHUB_SHA']}
pathlib.Path('proof/FINAL_CHANNEL.json').write_text(json.dumps(result,indent=2));print('VF_CHANNEL_FINAL_BEGIN');print(json.dumps(result));print('VF_CHANNEL_FINAL_END')

