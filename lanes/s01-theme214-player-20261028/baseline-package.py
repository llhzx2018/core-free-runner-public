from pathlib import Path,PurePosixPath
import zipfile,hashlib,json,subprocess,os
r=Path('baseline/src');files=sorted(p for p in r.rglob('*')if p.is_file());assert len(files)==476
assert (Path('baseline/VERSION')).read_text().strip()=='1.35.214'
p=Path('provider/theme-main214-baseline.zip')
with zipfile.ZipFile(p,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9)as z:
 for f in files:
  assert not f.is_symlink();n=zipfile.ZipInfo(str(PurePosixPath('vf-tools-theme')/f.relative_to(r)),date_time=(1980,1,1,0,0,0));n.compress_type=zipfile.ZIP_DEFLATED;n.external_attr=(f.stat().st_mode&0o777)<<16;z.writestr(n,f.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
Path('proof/public-baseline.json').write_text(json.dumps({'source':os.environ['BASE_SHA'],'version':'1.35.214','files':476,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'purpose':'current-main presentation parity only; not a new Release'}))
print('CURRENT_MAIN214_EXACT_PUBLIC_BASELINE_READY')
