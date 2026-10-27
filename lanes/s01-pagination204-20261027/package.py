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
print('APPROVED_SHARED_PAGINATION_SCOPE_PASS')

# Keep the shared CSS bundle, URL/SEO owners, layout persistence and Provider contracts intact.
for p in ['src/assets/js/main.js','src/inc/modules/module-post-list.php','src/inc/modules/module-directory-ui.php','src/inc/modules/module-hero.php','src/inc/modules/module-cta.php','src/inc/module-system/module-system-render.php','src/assets/js/admin/admin-layout.js','src/inc/admin/admin-ads-actions.php','src/inc/services/ads-service.php','tests/faq-desktop-browser-check.cjs','src/inc/modules/module-faq.php','src/inc/modules/module-support-pages.php','src/inc/services/layout-service.php','src/inc/theme-ad-contract.php','src/inc/theme-ad-runtime.php','src/inc/theme-native-toc.php','src/inc/services/seo-owner-service.php','src/inc/services/seo-head-service.php','src/inc/services/technical-seo-service.php','src/inc/services/url/public-url-post-permalinks.php']:
    old=subprocess.check_output(['git','-C',str(root),'show',os.environ['BASE_SHA']+':'+p])
    assert (root/p).read_bytes()==old
print('EXISTING_OWNER_AND_PERSISTENCE_BYTE_IDENTICAL_PASS')

scope=json.loads(Path('control/lanes/'+os.environ['LANE_ID']+'/css-scope.json').read_text())
old_bundle=subprocess.check_output(['git','-C',str(root),'show',os.environ['BASE_SHA']+':src/assets/css/public/vf-theme-public-runtime.css'])
expected_bundle=old_bundle
for p in scope['owners']:
    old=subprocess.check_output(['git','-C',str(root),'show',os.environ['BASE_SHA']+':'+p]);new=(root/p).read_bytes()
    assert expected_bundle.count(old)==1,p
    expected_bundle=expected_bundle.replace(old,new)
new_bundle=(root/'src/assets/css/public/vf-theme-public-runtime.css').read_bytes()
assert new_bundle==expected_bundle
assert len(new_bundle)<len(old_bundle)
assert new_bundle.count(b'/* Shared native pagination:')==1
old_registry=subprocess.check_output(['git','-C',str(root),'show',os.environ['BASE_SHA']+':src/inc/public-css-owner-registry.php']).decode()
import re
assert (root/'src/inc/public-css-owner-registry.php').read_text()==re.sub(r"('sha256' => ')[a-f0-9]{64}(')",lambda m:m[1]+hashlib.sha256(new_bundle).hexdigest()+m[2],old_registry,count=1)
# Reconstruct each edited owner by deleting pagination-only rules and adding
# exactly the shared primitive. All unrelated selectors/declarations stay exact.
import runpy
helpers=runpy.run_path('control/lanes/'+os.environ['LANE_ID']+'/css-scope-check.py')
for p in scope['owners']:
    old=subprocess.check_output(['git','-C',str(root),'show',os.environ['BASE_SHA']+':'+p]).decode()
    expected=helpers['strip_pagination'](old)
    if p==scope['shared']:expected+='\n'+scope['common']
    assert (root/p).read_text()==expected,p
print('FIVE_OWNERS_ONE_SHARED_PRIMITIVE_NONPAGINATION_RULES_BYTE_IDENTICAL_PASS')

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
