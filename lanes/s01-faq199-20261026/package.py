from pathlib import Path, PurePosixPath
import hashlib, io, json, os, subprocess, zipfile

root = Path('target')
def git(*args):
    return subprocess.check_output(['git', '-C', str(root), *args]).decode().strip()
assert git('rev-parse', 'HEAD') == os.environ['TARGET_SHA']
assert git('rev-parse', 'HEAD^{tree}') == os.environ['TARGET_TREE']
version = os.environ['TARGET_VERSION']
assert (root / 'VERSION').read_text().strip() == version
expected={'src/assets/css/public/vf-theme-public-runtime.css','src/inc/public-css-owner-registry.php','VERSION', 'src/style.css', 'src/inc/runtime-constants.php', 'src/assets/css/public/pages/families/public-layer-04-page-families-support-faq.css', 'CHANGELOG.md', 'tests/faq-desktop-browser-check.cjs'}
assert set(git('diff','--name-only',os.environ['BASE_SHA'],'HEAD').splitlines())==expected
print('APPROVED_FAQ_PRESENTATION_ONLY_SCOPE_PASS')

# Keep the shared CSS bundle, URL/SEO owners, layout persistence and Provider contracts intact.
for p in ['src/assets/js/admin/admin-layout.js','src/inc/admin/admin-ads-actions.php','src/inc/services/ads-service.php','src/assets/js/main.js','src/inc/modules/module-faq.php','src/inc/modules/module-support-pages.php','src/inc/module-system/module-system-render.php','src/inc/services/layout-service.php','src/inc/theme-ad-contract.php','src/inc/theme-ad-runtime.php','src/inc/theme-native-toc.php','src/inc/services/seo-owner-service.php','src/inc/services/seo-head-service.php','src/inc/services/technical-seo-service.php','src/inc/services/url/public-url-post-permalinks.php']:
    old=subprocess.check_output(['git','-C',str(root),'show',os.environ['BASE_SHA']+':'+p])
    assert (root/p).read_bytes()==old
print('EXISTING_OWNER_AND_PERSISTENCE_BYTE_IDENTICAL_PASS')

old_bundle=subprocess.check_output(['git','-C',str(root),'show',os.environ['BASE_SHA']+':src/assets/css/public/vf-theme-public-runtime.css'])
old_owner=subprocess.check_output(['git','-C',str(root),'show',os.environ['BASE_SHA']+':src/assets/css/public/pages/families/public-layer-04-page-families-support-faq.css'])
new_owner=(root/'src/assets/css/public/pages/families/public-layer-04-page-families-support-faq.css').read_bytes()
assert old_bundle.count(old_owner)==1
new_bundle=(root/'src/assets/css/public/vf-theme-public-runtime.css').read_bytes()
assert new_bundle==old_bundle.replace(old_owner,new_owner)
old_registry=subprocess.check_output(['git','-C',str(root),'show',os.environ['BASE_SHA']+':src/inc/public-css-owner-registry.php']).decode()
import re
new_registry=(root/'src/inc/public-css-owner-registry.php').read_text()
assert new_registry==re.sub(r"('sha256' => ')[a-f0-9]{64}(')",lambda m:m[1]+hashlib.sha256(new_bundle).hexdigest()+m[2],old_registry,count=1)
print('BUNDLE_IS_EXACTLY_ONE_OWNER_SEGMENT_REPLACEMENT_PASS')


for p,limit in [('src/assets/css/public/pages/families/public-layer-04-page-families-support-faq.css',6500),('src/assets/js/main.js',0)]:
    old=subprocess.check_output(['git','-C',str(root),'show',os.environ['BASE_SHA']+':'+p])
    assert len((root/p).read_bytes())-len(old)<=limit
print('BOUNDED_READING_ASSET_BUDGET_PASS')
old_css=subprocess.check_output(['git','-C',str(root),'show',os.environ['BASE_SHA']+':src/assets/css/public/pages/families/public-layer-04-page-families-support-faq.css'])
assert (root/'src/assets/css/public/pages/families/public-layer-04-page-families-support-faq.css').read_bytes().split(b'/* FAQ reference:')[0]==old_css.split(b'/* FAQ reference:')[0]
print('PRIOR_OWNER_PREFIX_UNCHANGED_REPLACED_FAQ_BLOCK_ONLY_PASS')

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
