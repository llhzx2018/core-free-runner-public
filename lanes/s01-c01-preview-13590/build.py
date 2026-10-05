import os, pathlib, zipfile, hashlib, json, re, subprocess
root=pathlib.Path('target/src'); out=pathlib.Path('proof'); out.mkdir(exist_ok=True)
version=os.environ['TARGET_VERSION']; sha=os.environ['TARGET_SHA']
assert pathlib.Path('target/VERSION').read_text().strip()==version
assert 'Version: '+version in (root/'style.css').read_text()
assert "VF_THEME_VERSION', '"+version+"'" in (root/'inc/runtime-constants.php').read_text()
changed=subprocess.check_output(['git','-C','target','diff','--name-only',os.environ['BASE_SHA'],sha],text=True).splitlines()
allowed={'VERSION','src/style.css','src/inc/runtime-constants.php','src/assets/js/admin/admin-preview.js','src/inc/services/preview-workbench-service.php','docs/authority/ACCEPTANCE_MATRIX.md','src/theme.json'}
assert set(changed)==allowed,changed
def original(p):return subprocess.check_output(['git','-C','target','show',os.environ['BASE_SHA']+':'+p],text=True)
assert (root/'style.css').read_text()==original('src/style.css').replace('Version: '+os.environ['SOURCE_VERSION'],'Version: '+version)
assert (root/'inc/runtime-constants.php').read_text()==original('src/inc/runtime-constants.php').replace('V1.35.59_BRAND_COMPACT_PAGEBAR','V'+version+'_PREVIEW_CONTROL_RECOVERY').replace('V1.35.59_BRAND_V8_SETTINGS','V'+version+'_PREVIEW_CONTROL_RECOVERY').replace("VF_THEME_VERSION', '"+os.environ['SOURCE_VERSION']+"'", "VF_THEME_VERSION', '"+version+"'")
assert (root/'theme.json').read_text()==original('src/theme.json').replace('\"vfThemeVersion\": \"1.35.53\"', '\"vfThemeVersion\": \"'+version+'\"')
for p in ['src/inc/admin/admin-seo-actions.php','src/inc/admin/controllers/seo.php','src/inc/bootstrap/manifests/admin-tabs/seo.php','src/inc/admin/admin-controller.php','src/assets/js/admin/admin-navigation.js','src/assets/css/admin/pages/navigation/admin-page-navigation-v8.css','src/inc/admin/views/render.php','src/assets/js/admin/admin-render.js','src/inc/services/renderer-config-service.php','src/inc/services/product-renderer-service.php','src/inc/services/url-resolver-service.php']:
 assert pathlib.Path('target',p).read_text()==original(p),p+' changed outside scope'
for p in ['src/inc/admin/admin-shell.php','src/inc/admin/admin-s01-uiux-polish.php']:
 assert pathlib.Path('target',p).read_text()==original(p),p+' frozen content changed'
# Update/auth, Descriptor validation and other pages remain outside the exact allowlist.
for p in ['src/inc/services/runtime-descriptor-service.php','src/inc/services/page-runtime-contract-service.php','src/inc/services/frontend-runtime-loader.php','src/inc/services/public-tool-runtime-contract.php']:
 assert pathlib.Path('target',p).read_text()==original(p),p+' security/frozen boundary changed'
assert hashlib.sha256((root/'assets/css/admin/admin-s01-shell-header-final-r12.css').read_bytes()).hexdigest()=='7dc6b2bd2126237e7e69d6ce2ef890c4e14362a68591f0a93896638acf5c6a12'
assert hashlib.sha256((root/'assets/js/admin/admin-console.js').read_bytes()).hexdigest()=='bb18bdac83c2189bddcdf616563d90ae2f830373834ab016d6411648c2056bfd'
asset='vf-tools-theme_V'+version+'.zip'
for name in [asset,'rebuild.zip']:
 with zipfile.ZipFile(out/name,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for p in sorted(root.rglob('*')):
   if not p.is_file(): continue
   rel=p.relative_to(root).as_posix()
   assert not p.is_symlink()
   if rel.lower() in ['readme.md','changelog.md']: continue
   assert not re.search(r'(^|/)(?:\.git|\.github|tests?|docs?|evidence|private|tmp|temp|cache|logs?)(/|$)',rel,re.I),rel
   assert not re.search(r'\.(?:sql|sqlite3?|db|log|zip|tar|gz|bak|tmp)$',rel,re.I),rel
   assert pathlib.Path(rel).name not in ['.env','wp-config.php']
   data=p.read_bytes()
   assert not re.search(rb'gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}',data),rel
   info=zipfile.ZipInfo('vf-tools-theme/'+rel,(1980,1,1,0,0,0)); info.create_system=3; info.external_attr=(0o100644)<<16
   z.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
assert (out/asset).read_bytes()==(out/'rebuild.zip').read_bytes()
(out/'rebuild.zip').unlink()
data=(out/asset).read_bytes()
meta={'source_sha':sha,'source_tree':os.environ['TARGET_TREE'],'version':version,'asset':asset,'asset_bytes':len(data),'asset_sha256':hashlib.sha256(data).hexdigest(),'frozen_shell_header_menu':'PASS','security_boundary':'PASS','owner_product_acceptance':'PENDING_OWNER_REAL_USE','owner_preview_runtime_applicability':'N_A','changed_files':changed}
(out/'identity.json').write_text(json.dumps(meta,indent=2)); print(json.dumps(meta))
