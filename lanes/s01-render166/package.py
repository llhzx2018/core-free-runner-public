from pathlib import Path, PurePosixPath
import hashlib,io,json,os,subprocess,zipfile
root=Path('target')
def git(*a):return subprocess.check_output(['git','-C','target',*a]).decode().strip()
assert git('rev-parse','HEAD')==os.environ['TARGET_SHA']
assert git('rev-parse','HEAD^{tree}')==os.environ['TARGET_TREE']
version=os.environ['TARGET_VERSION']
assert (root/'VERSION').read_text().strip()==version
files=sorted(p for p in (root/'src').rglob('*') if p.is_file())
assert len(files)==476,len(files)
def bundle():
 out=io.BytesIO()
 with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for p in files:
   assert not p.is_symlink()
   info=zipfile.ZipInfo(str(PurePosixPath('vf-tools-theme')/p.relative_to(root/'src')),date_time=(1980,1,1,0,0,0))
   info.compress_type=zipfile.ZIP_DEFLATED
   info.external_attr=(p.stat().st_mode & 0o777)<<16
   z.writestr(info,p.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
 return out.getvalue()
data=bundle()
assert data==bundle()
p=Path('provider')/('vf-tools-theme_V'+version+'.zip');p.write_bytes(data)
with zipfile.ZipFile(p) as z:
 assert z.testzip() is None
 assert ('Version: '+version) in z.read('vf-tools-theme/style.css').decode()
 assert all('..' not in PurePosixPath(n).parts for n in z.namelist())
receipt=dict(status='PASS',version=version,source=os.environ['TARGET_SHA'],tree=os.environ['TARGET_TREE'],bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),files=len(files),production='UNTOUCHED')
Path('proof/package.json').write_text(json.dumps(receipt,indent=2))
print('EXACT_CANDIDATE_PACKAGE_PASS',json.dumps(receipt))
