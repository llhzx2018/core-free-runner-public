import os, pathlib, zipfile, hashlib, json, re, subprocess
root=pathlib.Path('target/src'); out=pathlib.Path('proof'); out.mkdir(exist_ok=True)
version=os.environ['TARGET_VERSION']; sha=os.environ['TARGET_SHA']
assert pathlib.Path('target/VERSION').read_text().strip()==version
assert 'Version: '+version in (root/'style.css').read_text()
assert "VF_THEME_VERSION', '"+version+"'" in (root/'inc/runtime-constants.php').read_text()
changed=subprocess.check_output(['git','-C','target','diff','--name-only',os.environ['BASE_SHA'],sha],text=True).splitlines()
allowed={'VERSION','src/style.css','src/inc/runtime-constants.php','src/inc/admin/views/preview.php','src/assets/js/admin/admin-preview.js','src/assets/css/admin/pages/preview/admin-page-preview.css','src/inc/admin/admin-s01-uiux-polish.php','tests/preview-workflow-v4-contract.php','tests/preview-controls-browser-check.js','src/inc/services/renderer-config-service.php','tests/renderer-revision-bootstrap-contract.php','src/inc/bootstrap/manifests/theme-action.php'}
assert set(changed)==allowed,changed
def original(p):return subprocess.check_output(['git','-C','target','show',os.environ['BASE_SHA']+':'+p],text=True)
assert (root/'style.css').read_text()==original('src/style.css').replace('Version: '+os.environ['SOURCE_VERSION'],'Version: '+version)
assert (root/'inc/runtime-constants.php').read_text()==original('src/inc/runtime-constants.php').replace("VF_THEME_VERSION', '"+os.environ['SOURCE_VERSION']+"'", "VF_THEME_VERSION', '"+version+"'")
page='src/inc/admin/views/preview.php';new=pathlib.Path('target',page).read_text();old=original(page)
original_preamble=old.split('?>\n<section class="vf-preview-v510"')[0]
new_preamble=new.split('?>\n<section class="vf-preview-v510"')[0]
new_preamble=re.sub(r'\$preview_language_locales = \[\];.*?(?=\$signed_target_paths =)', '',new_preamble,flags=re.S)
new_preamble=new_preamble.replace(', $preview_language_locales, $preview_site_locale','').replace("'locale'=>(string)($preview_language_locales[(string)$language] ?? $preview_site_locale)","'locale'=>(string)$language")
assert new_preamble==original_preamble,'unrelated preview state calculation changed'
from collections import Counter
def fields(s):return Counter(re.findall(r'<(?:form|input|select|option|textarea)\b(?:<\?php[\s\S]*?\?>|[^<>])*>',s,re.S))
assert fields(new)==fields(old),'submitted form fields/options changed'
for p in ['src/inc/admin/admin-preview-actions.php','src/inc/admin/controllers/preview.php','src/inc/services/preview-workbench-service.php','src/inc/services/signed-preview-service.php','src/inc/services/acceptance-state-service.php','src/inc/bootstrap/manifests/admin-tabs/preview.php','src/inc/admin/admin-controller.php','src/inc/admin/admin-shell.php','src/inc/admin/views/seo.php','src/assets/js/admin/admin-seo.js','src/assets/css/admin/pages/seo/admin-page-seo-reference-v3.css','src/inc/admin/views/render.php','src/assets/js/admin/admin-render.js','src/assets/css/admin/pages/render/admin-page-render-v8.css','src/assets/js/admin/admin-navigation.js','src/assets/css/admin/pages/navigation/admin-page-navigation-v8.css']:
 assert pathlib.Path('target',p).read_text()==original(p),p+' frozen or backend changed'
action_manifest='src/inc/bootstrap/manifests/theme-action.php'
action_source=pathlib.Path('target',action_manifest).read_text()
action_source=re.sub(r"    'vf_theme_preview_revoke_all' => \[\n        'services/signed-preview-service.php','admin/admin-preview-actions.php',\n    \],\n\n",'',action_source)
assert action_source==original(action_manifest),'unrelated action bootstrap changed'
loader='src/inc/admin/admin-s01-uiux-polish.php'
def without_preview(s):return re.sub(r"    if \(\$tab === 'preview'\) \{.*?(?=    \$preview_language_relative)",'',s,flags=re.S).strip()
assert without_preview(pathlib.Path('target',loader).read_text())==without_preview(original(loader)),'non-preview loader changed'
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
