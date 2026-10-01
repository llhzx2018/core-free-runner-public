import os, pathlib, zipfile, hashlib, json, re, subprocess
root=pathlib.Path('target/src'); out=pathlib.Path('proof'); out.mkdir(exist_ok=True)
version=os.environ['TARGET_VERSION']; sha=os.environ['TARGET_SHA']
assert pathlib.Path('target/VERSION').read_text().strip()==version
assert 'Version: '+version in (root/'style.css').read_text()
assert "VF_THEME_VERSION', '"+version+"'" in (root/'inc/runtime-constants.php').read_text()
changed=subprocess.check_output(['git','-C','target','diff','--name-only',os.environ['BASE_SHA'],sha],text=True).splitlines()
allowed={'src/inc/admin/views/layout.php', 'src/inc/admin/admin-s01-uiux-polish.php', 'src/inc/runtime-constants.php', 'src/assets/css/admin/pages/page-structure/admin-page-layout-v8.css', 'src/assets/js/admin/admin-layout-page-refinement-v1.js', 'tests/layout-v8-browser-check.js', 'VERSION', 'tests/layout-page-workflow-contract.php', 'src/style.css'}
assert set(changed)==allowed,changed
def original(p): return subprocess.check_output(['git','-C','target','show',os.environ['BASE_SHA']+':'+p],text=True)
shell=(root/'inc/admin/admin-shell.php').read_text()
assert shell==original('src/inc/admin/admin-shell.php'),'frozen shell changed'
before=original('src/inc/admin/views/layout.php');after=(root/'inc/admin/views/layout.php').read_text()
def form_contract(s):
 return (re.findall(r'<form[^>]*method="post"[^>]*action="[^"\n]+"',s),re.findall(r'<input[^>]*name="action"[^>]*>',s),re.findall(r"wp_nonce_field\([^;]+",s))
assert form_contract(before)==form_contract(after),'form action/nonce/method changed'
assert (root/'assets/js/admin/admin-layout.js').read_text()==original('src/assets/js/admin/admin-layout.js'),'layout canonical/save handlers changed'
assert re.findall(r'name=\"([^\"]+)\"',before)==re.findall(r'name=\"([^\"]+)\"',after),'submitted field names changed'
# Runtime/service/update/auth files cannot change under the above exact allowlist.
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
