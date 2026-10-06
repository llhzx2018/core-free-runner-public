import os,pathlib,zipfile,hashlib,json,re,subprocess
root=pathlib.Path('target/src');out=pathlib.Path('proof');out.mkdir(exist_ok=True)
version=os.environ['TARGET_VERSION'];sha=os.environ['TARGET_SHA']
assert pathlib.Path('target/VERSION').read_text().strip()==version
assert 'Version: '+version in (root/'style.css').read_text()
assert "VF_THEME_VERSION', '"+version+"'" in (root/'inc/runtime-constants.php').read_text()
assert subprocess.check_output(['git','-C','target','rev-parse','HEAD'],text=True).strip()==sha
assert subprocess.check_output(['git','-C','target','rev-parse','HEAD^{tree}'],text=True).strip()==os.environ['TARGET_TREE']
assert not subprocess.check_output(['git','-C','target','diff','--name-only','53d17861d096cac55110746bba0556280738ed7d',sha,'--','src'],text=True).strip()
asset='vf-tools-theme_V'+version+'.zip'
with zipfile.ZipFile(out/asset,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for p in sorted(root.rglob('*')):
  if not p.is_file():continue
  rel=p.relative_to(root).as_posix();assert not p.is_symlink()
  if rel.lower() in ['readme.md','changelog.md']:continue
  assert not re.search(r'(^|/)(?:\.git|\.github|tests?|docs?|evidence|private|tmp|temp|cache|logs?)(/|$)',rel,re.I)
  assert not re.search(r'\.(?:sql|sqlite3?|db|log|zip|tar|gz|bak|tmp)$',rel,re.I)
  data=p.read_bytes();assert not re.search(rb'gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}',data)
  info=zipfile.ZipInfo('vf-tools-theme/'+rel,(1980,1,1,0,0,0));info.create_system=3;info.external_attr=0o100644<<16
  z.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
data=(out/asset).read_bytes();digest=hashlib.sha256(data).hexdigest()
assert len(data)==1784408 and digest=='47e12ef95993da8dcf271b9ab93bd3ac2e8b147a4e336e78d301ea414d6824a7'
(out/'identity.json').write_text(json.dumps({'source_sha':sha,'source_tree':os.environ['TARGET_TREE'],'version':version,'asset':asset,'asset_bytes':len(data),'asset_sha256':digest,'runtime_matches_formal_release':'PASS','source_changes':'NONE','production':'NOT_EXECUTED'},indent=2))
