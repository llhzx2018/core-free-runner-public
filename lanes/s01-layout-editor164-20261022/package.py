from pathlib import Path, PurePosixPath
import hashlib, io, json, os, subprocess, zipfile

root = Path('target')
def git(*args):
    return subprocess.check_output(['git', '-C', str(root), *args]).decode().strip()
assert git('rev-parse', 'HEAD') == os.environ['TARGET_SHA']
assert git('rev-parse', 'HEAD^{tree}') == os.environ['TARGET_TREE']
version = os.environ['TARGET_VERSION']
assert (root / 'VERSION').read_text().strip() == version
expected = {'src/assets/js/admin/admin-layout-page-refinement-v1.js', 'src/assets/js/admin/admin-layout.js', 'src/inc/admin/views/partials/layout-system-static-workspaces.php', 'src/inc/admin/admin-shell.php', 'src/inc/runtime-constants.php', 'src/inc/admin/views/partials/layout-glossary-archive-faq-workspaces.php', 'src/inc/admin/views/layout.php', 'src/inc/admin/views/partials/layout-home-tool-workspaces.php', 'VERSION', 'CHANGELOG.md', 'src/style.css'}
assert set(git('diff', '--name-only', os.environ['BASE_SHA'], 'HEAD').splitlines()) == expected
import re
for view in [p for p in expected if '/views/' in p]:
    old = subprocess.check_output(['git','-C',str(root),'show',os.environ['BASE_SHA']+':'+view]).decode()
    new = (root/view).read_text()
    assert re.findall(r'\bname="[^"]*"',old) == re.findall(r'\bname="[^"]*"',new),view
old_js = subprocess.check_output(['git','-C',str(root),'show',os.environ['BASE_SHA']+':src/assets/js/admin/admin-layout.js']).decode()
new_js = (root/'src/assets/js/admin/admin-layout.js').read_text()
for name in ['verifiedReceipt','applyCanonicalReadback','setBusyControls']:
    pattern = r'  function '+name+r'\(.*?(?=\n  function |\Z)'
    assert re.search(pattern,old_js,re.S).group() == re.search(pattern,new_js,re.S).group(),name
print('ALL_FORM_IDENTITIES_AND_CANONICAL_VALIDATION_UNCHANGED_PASS')
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
