import os, pathlib, zipfile, hashlib, json, re, subprocess
root=pathlib.Path('target/src'); out=pathlib.Path('proof'); out.mkdir(exist_ok=True)
version=os.environ['TARGET_VERSION']; sha=os.environ['TARGET_SHA']
assert pathlib.Path('target/VERSION').read_text().strip()==version
assert 'Version: '+version in (root/'style.css').read_text()
assert "VF_THEME_VERSION', '"+version+"'" in (root/'inc/runtime-constants.php').read_text()
changed=subprocess.check_output(['git','-C','target','diff','--name-only',os.environ['BASE_SHA'],sha],text=True).splitlines()
allowed={'VERSION','src/style.css','src/theme.json','src/inc/runtime-constants.php','src/assets/js/admin/admin-preview.js','src/inc/services/preview-workbench-service.php','tests/preview-workflow-browser-check.js','tests/preview-state-wordpress-check.php','tests/browser-probe-version-browser-check.js','src/assets/js/modules/browser-behavior-probe.js','docs/authority/ACCEPTANCE_MATRIX.md'}
assert set(changed)==allowed,changed
def original(p):return subprocess.check_output(['git','-C','target','show',os.environ['BASE_SHA']+':'+p],text=True)
assert (root/'style.css').read_text()==original('src/style.css').replace('Version: '+os.environ['SOURCE_VERSION'],'Version: '+version)
assert (root/'theme.json').read_text()==original('src/theme.json').replace('"vfThemeVersion": "'+os.environ['SOURCE_VERSION']+'"','"vfThemeVersion": "'+version+'"')
assert (root/'inc/runtime-constants.php').read_text()==original('src/inc/runtime-constants.php').replace(os.environ['SOURCE_VERSION'],version).replace('SEO_RESPONSIVE_CLOSURE','PREVIEW_FUNCTIONAL_RECHECK')
for p in ['src/inc/admin/views/preview.php','src/assets/css/admin/pages/preview/admin-page-preview.css','src/inc/admin/admin-preview-actions.php','src/inc/admin/controllers/preview.php','src/inc/services/signed-preview-service.php','src/inc/services/acceptance-state-service.php','src/inc/bootstrap/manifests/admin-tabs/preview.php','src/inc/admin/admin-shell.php','src/inc/admin/admin-s01-uiux-polish.php','src/assets/css/admin/admin-s01-shell-header-final-r12.css','src/assets/js/admin/admin-console.js','src/inc/services/live-integration-acceptance-service.php']:
 assert pathlib.Path('target',p).read_text()==original(p),p+' frozen or out of scope'
assert (root/'assets/js/modules/browser-behavior-probe.js').read_text().rstrip()==original('src/assets/js/modules/browser-behavior-probe.js').replace('/^VF_ToolSite_V/', '/^VF_(?:Tools_Theme|ToolSite)_V/').rstrip()
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
