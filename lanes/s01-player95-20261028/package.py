from pathlib import Path, PurePosixPath
import hashlib, io, json, os, subprocess, zipfile

root=Path('target'); proof=Path('proof');proof.mkdir(exist_ok=True)
def git(*args):return subprocess.check_output(['git','-C',str(root),*args]).decode().strip()
assert git('rev-parse','HEAD')==os.environ['TARGET_SHA']
assert git('rev-parse','HEAD^{tree}')==os.environ['TARGET_TREE']
assert (root/'VERSION').read_text().strip()==os.environ['TARGET_VERSION']
old=Path('provider/vf-tools-m3u8_V1.25.94.zip');assert hashlib.sha256(old.read_bytes()).hexdigest()=='70b90d40da5d69fc7819bd7ada3f15fb0145e64822b788bd94956c7827b2df03'
changed=set(git('diff','--name-only',os.environ['BASE_SHA'],'HEAD').splitlines())
expected={'VERSION','CHANGELOG.md','src/vf-tool-m3u8.php','src/plugin-manifest.json','src/PACKAGE_PROFILE.json','src/includes/settings-engine.php','src/public/js/modules/player.js','src/public/dist/player.js','src/config/v6/third-party-supply-chain.json','src/public/vendor/hls.js/hls.min.js','src/public/vendor/hls.js/LICENSE'}
assert changed==expected,(changed-expected,expected-changed)
updated={x[4:]:root/x for x in expected if x.startswith('src/') and x!='src/PACKAGE_PROFILE.json'}
newpaths={'public/vendor/hls.js/hls.min.js','public/vendor/hls.js/LICENSE'}
assert hashlib.sha256(updated['public/vendor/hls.js/hls.min.js'].read_bytes()).hexdigest()=='a12e7ee1cd64a69dcdb314157e45dafcba705bfb0b1440b7935cb265d374423e'
def bundle():
 b=io.BytesIO();done=set()
 with zipfile.ZipFile(old) as zin,zipfile.ZipFile(b,'w') as zout:
  assert sum(not i.is_dir() for i in zin.infolist())==568
  for info in zin.infolist():
   assert info.filename.startswith('vf-tool-m3u8/') and '..' not in PurePosixPath(info.filename).parts
   rel=info.filename[len('vf-tool-m3u8/'):];payload=zin.read(info)
   if rel in updated:
    before=subprocess.check_output(['git','-C',str(root),'show',os.environ['BASE_SHA']+':src/'+rel]);assert before==payload,rel
    payload=updated[rel].read_bytes();done.add(rel)
   zout.writestr(info,payload)
  for rel in sorted(newpaths):
   info=zipfile.ZipInfo('vf-tool-m3u8/'+rel,date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;zout.writestr(info,updated[rel].read_bytes());done.add(rel)
  assert done==set(updated),(set(updated)-done,done-set(updated))
 return b.getvalue()
data=bundle();assert data==bundle();dest=Path('provider/vf-tools-m3u8_V1.25.95.zip');dest.write_bytes(data)
with zipfile.ZipFile(dest) as z:
 assert z.testzip() is None and sum(not i.is_dir() for i in z.infolist())==570
 assert b'Version: 1.25.95' in z.read('vf-tool-m3u8/vf-tool-m3u8.php')
receipt={'status':'PASS','version':'1.25.95','sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'files':570,'source':os.environ['TARGET_SHA'],'tree':os.environ['TARGET_TREE'],'production':'untouched'}
(proof/'package.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
