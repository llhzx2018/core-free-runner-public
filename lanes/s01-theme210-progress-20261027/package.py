from pathlib import Path, PurePosixPath
import hashlib, io, json, os, subprocess, zipfile

root = Path('target')
def git(*args):
    return subprocess.check_output(['git', '-C', str(root), *args]).decode().strip()
assert git('rev-parse', 'HEAD') == os.environ['TARGET_SHA']
assert git('rev-parse', 'HEAD^{tree}') == os.environ['TARGET_TREE']
version = os.environ['TARGET_VERSION']
assert (root / 'VERSION').read_text().strip() == version
expected=set(json.loads(Path('control/lanes/'+os.environ['LANE_ID']+'/changed.json').read_text()))
assert set(git('diff','--name-only',os.environ['BASE_SHA'],'HEAD').splitlines())==expected
print('APPROVED_INTEGRATED_THEME_SCOPE_PASS')

# Progress projection only; native persistence, frontend and all assets byte-identical.
p='src/inc/services/frontend-page-progress-service.php'
old=subprocess.check_output(['git','-C',str(root),'show',os.environ['BASE_SHA']+':'+p]).decode();new=(root/p).read_text()
a='function vf_theme_frontend_progress_save';b='function vf_theme_frontend_progress_model'
assert old[old.index(a):old.index(b)]==new[new.index(a):new.index(b)]
for p in ['src/inc/admin/views/frontend-page-progress-record.php','src/inc/modules/module-post-list.php','src/inc/frontend-seo-context.php','src/inc/theme-public-route-renderer.php','src/inc/theme-system-recovery.php','src/assets/js/admin/admin-frontend-pages.js','src/assets/css/public/vf-theme-public-runtime.css','src/inc/public-css-owner-registry.php']:
    old=subprocess.check_output(['git','-C',str(root),'show',os.environ['BASE_SHA']+':'+p]);assert (root/p).read_bytes()==old,p
assert git('diff','--check',os.environ['BASE_SHA'],'HEAD')==''
print('NATIVE_SAVE_BYTES_FRONTEND_AND_ASSETS_UNCHANGED_PASS')

files = sorted(p for p in (root / 'src').rglob('*') if p.is_file())
assert len(files) == 476
def bundle():
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in files:
            assert not p.is_symlink()
            info = zipfile.ZipInfo(str(PurePosixPath('vf-tools-theme') / p.relative_to(root / 'src')), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (p.stat().st_mode & 0o777) << 16
            z.writestr(info, p.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return out.getvalue()
data = bundle()
assert data == bundle()
path = Path('provider') / ('vf-tools-theme_V' + version + '.zip')
path.write_bytes(data)
with zipfile.ZipFile(path) as z:
    assert z.testzip() is None
    assert ('Version: ' + version) in z.read('vf-tools-theme/style.css').decode()
    assert all('..' not in PurePosixPath(n).parts for n in z.namelist())
receipt = dict(status='PASS', version=version, source=os.environ['TARGET_SHA'], tree=os.environ['TARGET_TREE'], bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), files=476, production='UNTOUCHED')
Path('proof/package.json').write_text(json.dumps(receipt, indent=2))
print('EXACT_PACKAGE_PASS ' + json.dumps(receipt))
