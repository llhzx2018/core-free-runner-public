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

# Only metadata, existing navigation view and bounded404 presentation change.
for p in ['src/assets/js/main.js','src/assets/js/modules/public-static-search.js','src/inc/module-system/module-system-render.php','src/inc/services/layout-service.php','src/inc/services/seo-owner-service.php','src/inc/services/seo-head-service.php','src/inc/services/technical-seo-service.php','src/inc/services/url/public-url-post-permalinks.php','src/search.php','src/inc/theme-navigation.php','src/inc/theme-navigation-render.php','src/inc/theme-public-route-404-guard.php']:
    old=subprocess.check_output(['git','-C',str(root),'show',os.environ['BASE_SHA']+':'+p]);assert(root/p).read_bytes()==old,p
old_owner=subprocess.check_output(['git','-C',str(root),'show',os.environ['BASE_SHA']+':src/assets/css/public/pages/families/public-family-05-system-search-recovery-closure.css'])
new_owner=(root/'src/assets/css/public/pages/families/public-family-05-system-search-recovery-closure.css').read_bytes()
old_bundle=subprocess.check_output(['git','-C',str(root),'show',os.environ['BASE_SHA']+':src/assets/css/public/vf-theme-public-runtime.css'])
new_bundle=(root/'src/assets/css/public/vf-theme-public-runtime.css').read_bytes()
assert old_bundle.count(old_owner)==1 and old_bundle.replace(old_owner,new_owner)==new_bundle
assert len(new_bundle)<=len(old_bundle)+8192
assert hashlib.sha256(new_bundle).hexdigest() in (root/'src/inc/public-css-owner-registry.php').read_text()
assert git('diff','--check',os.environ['BASE_SHA'],'HEAD')==''
print('BOUNDED_CSS_REBUILD_UNCHANGED_JS_HEAD_AUTH_UPDATER_CONTRACTS_PASS')

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
