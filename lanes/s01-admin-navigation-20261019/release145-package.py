import hashlib,json,os,subprocess,zipfile,re
from pathlib import Path,PurePosixPath
root=Path('target');sha=os.environ['TARGET_SHA'];v=os.environ['TARGET_VERSION']
base='93f4b2608a4b54610a534232768d8fd9921f5bd9'
assert subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()==sha
changed=subprocess.check_output(['git','-C',str(root),'diff','--name-only',base,'HEAD'],text=True).splitlines()
assert set(changed)=={'VERSION','src/style.css','src/inc/runtime-constants.php','src/assets/css/public/public-reading-final-owner.css'},changed
assert (root/'VERSION').read_text()==v+'\n'
for path in ['src/style.css','src/inc/runtime-constants.php']:
 before=subprocess.check_output(['git','-C',str(root),'show',base+':'+path],text=True)
 expected=before.replace('1.35.146',v).replace('V'+v+'_PROBLEMS_CHECKLIST_LABELS','V'+v+'_PROBLEM_DETAIL_ALIGNMENT')
 assert (root/path).read_text()==expected,path
dest=Path('vf-tools-theme_V'+v+'.zip');src=root/'src';files=sorted(p for p in src.rglob('*') if p.is_file())
assert len(files)==476
with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for p in files:
  assert not p.is_symlink()
  info=zipfile.ZipInfo(str(PurePosixPath('vf-tools-theme')/p.relative_to(src)),date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=(p.stat().st_mode&0o777)<<16
  z.writestr(info,p.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
with zipfile.ZipFile(dest) as z:
 assert z.testzip() is None
 assert all(n.startswith('vf-tools-theme/') and '..' not in PurePosixPath(n).parts for n in z.namelist())
 assert ('Version: '+v) in z.read('vf-tools-theme/style.css').decode()
r={'status':'PASS','source':sha,'tree':subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD^{tree}'],text=True).strip(),'version':v,'files':len(files),'bytes':dest.stat().st_size,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'changed_files':changed,'production':'UNTOUCHED'}
Path('proof/candidate-zip-receipt.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
