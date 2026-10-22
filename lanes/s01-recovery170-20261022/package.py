from pathlib import Path, PurePosixPath
import hashlib, io, json, os, subprocess, zipfile

root = Path('target')
def git(*args):
    return subprocess.check_output(['git', '-C', str(root), *args]).decode().strip()
assert git('rev-parse', 'HEAD') == os.environ['TARGET_SHA']
assert git('rev-parse', 'HEAD^{tree}') == os.environ['TARGET_TREE']
version = os.environ['TARGET_VERSION']
assert (root / 'VERSION').read_text().strip() == version
expected={'VERSION','src/style.css','src/inc/runtime-constants.php','CHANGELOG.md','src/assets/js/admin/admin-recovery-v510.js','tests/recovery-fresh-confirmation-browser-check.js'}
assert set(git('diff','--name-only',os.environ['BASE_SHA'],'HEAD').splitlines())==expected
js='src/assets/js/admin/admin-recovery-v510.js'
old=subprocess.check_output(['git','-C',str(root),'show',os.environ['BASE_SHA']+':'+js]).decode()
new=(root/js).read_text()
start=new.index("  qs('[data-vf-recovery-default-open]')?.addEventListener")
end=new.index("  defaultConfirm?.addEventListener",start)
old_start=old.index("  qs('[data-vf-recovery-default-open]')?.addEventListener")
old_end=old.index("  defaultConfirm?.addEventListener",old_start)
assert new[:start]+new[end:]==old[:old_start]+old[old_end:],'All request, transaction, status and history code must be byte unchanged'
print('RECOVERY_REQUEST_VALIDATION_TRANSACTION_HISTORY_BYTE_UNCHANGED_PASS')
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
