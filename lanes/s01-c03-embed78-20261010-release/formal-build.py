import pathlib,hashlib,zipfile,os,json,subprocess
p=pathlib.Path('proof');p.mkdir(exist_ok=True);root=pathlib.Path('target/src')
assert subprocess.check_output(['git','-C','target','rev-parse','HEAD'],text=True).strip()==os.environ['TARGET_SHA']
assert subprocess.check_output(['git','-C','target','rev-parse','HEAD^{tree}'],text=True).strip()==os.environ['TARGET_TREE']
assert pathlib.Path('target/VERSION').read_text().strip()==os.environ['TARGET_VERSION']
paths=sorted((x for x in root.rglob('*') if x.is_file() and x.name not in ['README.md','PACKAGE_PROFILE.json']),key=lambda x:x.relative_to(root).as_posix())
assert len(paths)==568,len(paths)
fp=hashlib.sha256()
for x in paths:
 assert not x.is_symlink()
 rel=x.relative_to(root).as_posix();fp.update((rel+'\0'+hashlib.sha256(x.read_bytes()).hexdigest()+'\n').encode())
def build(dest):
 with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for x in paths:
   rel=x.relative_to(root).as_posix()
   assert not any(t in pathlib.PurePosixPath(rel).parts for t in ['tests','docs','evidence','private','.git','.github'])
   assert x.suffix.lower() not in ['.sql','.sqlite','.db','.zip','.log','.tmp']
   i=zipfile.ZipInfo('vf-tool-m3u8/'+rel,date_time=(2026,10,10,0,0,0));i.create_system=3;i.external_attr=0o100644<<16;i.compress_type=zipfile.ZIP_DEFLATED;z.writestr(i,x.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
asset=p/('vf-tools-m3u8_V'+os.environ['TARGET_VERSION']+'.zip');build(asset);build('/tmp/repeated-m3u8.zip')
assert asset.read_bytes()==pathlib.Path('/tmp/repeated-m3u8.zip').read_bytes()
with zipfile.ZipFile(asset) as z:assert z.testzip() is None and len(z.namelist())==568
r={'status':'PASS','source_sha':os.environ['TARGET_SHA'],'source_tree':os.environ['TARGET_TREE'],'version':os.environ['TARGET_VERSION'],'asset_name':asset.name,'asset_bytes':asset.stat().st_size,'asset_sha256':hashlib.sha256(asset.read_bytes()).hexdigest(),'runtime_files':len(paths),'runtime_fingerprint':fp.hexdigest(),'deterministic_build':'PASS','physical_root':'vf-tool-m3u8'}
(p/'identity.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
m=json.loads(pathlib.Path('lane/base-channel.json').read_text());m.update(target_version=r['version'],from_versions=list(dict.fromkeys(m['from_versions']+[os.environ['SOURCE_VERSION']])),release_tag='v'+r['version'],asset_name=r['asset_name'],asset_bytes=r['asset_bytes'],asset_sha256=r['asset_sha256'],runtime_files=568,runtime_file_count=568,runtime_fingerprint=r['runtime_fingerprint'],runtime_fingerprint_sha256=r['runtime_fingerprint'],released_at='2026-10-10T00:00:00Z')
(p/'synthetic-channel.json').write_text(json.dumps(m))

