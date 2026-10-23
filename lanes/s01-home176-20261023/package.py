from pathlib import Path, PurePosixPath
import hashlib, io, json, os, subprocess, zipfile

root = Path('target')
def git(*args):
    return subprocess.check_output(['git', '-C', str(root), *args]).decode().strip()
assert git('rev-parse', 'HEAD') == os.environ['TARGET_SHA']
assert git('rev-parse', 'HEAD^{tree}') == os.environ['TARGET_TREE']
version = os.environ['TARGET_VERSION']
assert (root / 'VERSION').read_text().strip() == version
expected={'VERSION', 'docs/evidence/2026-10-23-home-content-hierarchy.md', 'tests/home-composition-browser-check.cjs', 'src/assets/css/public/vf-theme-public-runtime.css', 'src/assets/css/public/pages/families/public-family-01-shell-home-operations-closure.css', 'src/style.css', 'src/inc/public-css-owner-registry.php', 'src/inc/services/frontend-page-progress-service.php', 'src/inc/runtime-constants.php', 'CHANGELOG.md'}
assert set(git('diff','--name-only',os.environ['BASE_SHA'],'HEAD').splitlines())==expected
print('BOUNDED_HOME_COMPOSITION_NO_CONTENT_OR_DATA_CHANGE_PASS')

owner='src/assets/css/public/pages/families/public-family-01-shell-home-operations-closure.css'
old=subprocess.check_output(['git','-C',str(root),'show',os.environ['BASE_SHA']+':'+owner]).decode()
new=(root/owner).read_text()
old_bundle=subprocess.check_output(['git','-C',str(root),'show',os.environ['BASE_SHA']+':src/assets/css/public/vf-theme-public-runtime.css']).decode()
new_bundle=(root/'src/assets/css/public/vf-theme-public-runtime.css').read_text()
assert old_bundle.count(old)==1 and new_bundle.count(new)==1
assert new_bundle.replace(new,old,1)==old_bundle,'unrelated public CSS changed'
assert hashlib.sha256(new_bundle.encode()).hexdigest() in (root/'src/inc/public-css-owner-registry.php').read_text()
print('EXACT_CANONICAL_CSS_BUNDLE_AND_CHECKSUM_PASS')

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
