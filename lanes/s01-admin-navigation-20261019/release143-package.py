import hashlib,json,os,subprocess,zipfile
from pathlib import Path,PurePosixPath
root=Path('target');sha=os.environ['TARGET_SHA'];version=os.environ['TARGET_VERSION']
base='630fc22b7afb710cce8bde59a4936b75546e0e73'
assert subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()==sha
changed=subprocess.check_output(['git','-C',str(root),'diff','--name-only',base,'HEAD'],text=True).splitlines()
assert set(changed)=={'VERSION','src/style.css','src/inc/runtime-constants.php'},changed
assert (root/'VERSION').read_text()==version+'\n'
for path,old,new in [('src/style.css','Version: 1.35.141','Version: '+version),('src/inc/runtime-constants.php',"'VF_THEME_VERSION', '1.35.133'","'VF_THEME_VERSION', '"+version+"'")]:
    before=subprocess.check_output(['git','-C',str(root),'show',base+':'+path],text=True)
    expected=before.replace(old,new)
    if 'runtime-constants' in path:expected=expected.replace("'VF_THEME_ROUND', 'V1.35.133_DESKTOP_HOME_FOOTER_CLOSURE'","'VF_THEME_ROUND', 'V"+version+"_ADMIN_LAYOUT_SIMPLIFICATION'")
    assert (root/path).read_text()==expected,path
dest=Path(f'vf-tools-theme_V{version}.zip');src=root/'src';files=sorted(p for p in src.rglob('*') if p.is_file())
assert len(files)==476
with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in files:
        assert not p.is_symlink()
        info=zipfile.ZipInfo(str(PurePosixPath('vf-tools-theme')/p.relative_to(src)),date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=(p.stat().st_mode&0o777)<<16
        z.writestr(info,p.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
with zipfile.ZipFile(dest) as z:
    assert z.testzip() is None
    assert all(n.startswith('vf-tools-theme/') and '..' not in PurePosixPath(n).parts for n in z.namelist())
    assert ('Version: '+version) in z.read('vf-tools-theme/style.css').decode()
r={'status':'PASS','source':sha,'tree':subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD^{tree}'],text=True).strip(),'version':version,'files':len(files),'bytes':dest.stat().st_size,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'reused_ux_source':base,'continuity':'Only exact version/header/runtime identity replacement; tested functional source unchanged','ux_run':39350731799,'editor_run':39349141976,'production':'UNTOUCHED'}
Path('proof/candidate-zip-receipt.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
