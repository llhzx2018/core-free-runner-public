#!/usr/bin/env python3
"""Read-only packaged-runtime proof for the exact S01 main heads, no release/upload."""
from pathlib import Path, PurePosixPath
import hashlib, json, re, sys, zipfile, subprocess
ROOT=Path.cwd()
PROOF=ROOT/"proof"
PROOF.mkdir(exist_ok=True)
SHA={"ops":"5e3c331b20ec72e82c91c8cd3cd0b5a9d0d5e89e","m3u8":"72cc556ec2480562850cf064e2b5fa559aa23775","theme":"0bbb9b0fcc05e7d912de15fe5edb8e7dccd12181"}
def sha(data): return hashlib.sha256(data).hexdigest()
def ident(name):
    value=subprocess.check_output(["git","-C",name,"rev-parse","HEAD"],text=True).strip()
    assert value==SHA[name], (name, value, SHA[name])
def files_runtime(root, include):
    a={}
    for p in sorted(root.rglob("*")):
        if not p.is_file(): continue
        assert not p.is_symlink(),p
        relative=p.relative_to(root).as_posix()
        if include(relative):
            assert not re.search(r"\.(sql|sqlite|sqlite3|db|log|zip|tar|gz|bak|tmp)$",relative,re.I),relative
            assert not re.search(r"(^|/)(\.git|\.github|tests?|docs?|evidence|private|tmp|temp|cache|logs?)(/|$)",relative,re.I),relative
            content=p.read_bytes()
            assert not re.search(rb"gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}",content),relative
            a[relative]=content
    assert a,root
    return a
def package(name,slug,files):
    path=PROOF/f"vf-tools-{name}-preflight.zip"
    for attempt in (1,2):
        dest=path if attempt==1 else PROOF/f"{name}-rebuild.zip"
        with zipfile.ZipFile(dest,"w") as archive:
            for rel,content in sorted(files.items()):
                info=zipfile.ZipInfo(f"{slug}/{rel}",(1980,1,1,0,0,0))
                info.create_system=3
                info.external_attr=0o100644<<16
                info.compress_type=zipfile.ZIP_DEFLATED
                archive.writestr(info,content,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    assert path.read_bytes()==(PROOF/f"{name}-rebuild.zip").read_bytes(),f"nondeterministic {name}"
    (PROOF/f"{name}-rebuild.zip").unlink()
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        names=z.namelist()
        assert names and len(names)==len(files)
        assert all(PurePosixPath(n).parts[0]==slug and ".." not in PurePosixPath(n).parts for n in names)
        assert f"{slug}/"+("style.css" if name=="theme" else "vf-ops.php" if name=="ops" else "vf-tool-m3u8.php") in names
    payload=path.read_bytes()
    fingerprint=sha("".join(f"{p}\0{sha(b)}\n" for p,b in sorted(files.items())).encode())
    return {"status":"PASS","component":name,"source_sha":SHA[name],
            "package_root":slug,"asset":path.name,"bytes":len(payload),
            "asset_sha256":sha(payload),"files":len(files),"runtime_fingerprint":fingerprint}
for name in SHA: ident(name)
ops_version=(ROOT/"ops/VERSION").read_text().strip()
m3_version=(ROOT/"m3u8/VERSION").read_text().strip()
theme_version=(ROOT/"theme/VERSION").read_text().strip()
assert (ops_version,m3_version,theme_version)==("1.21.1109","1.25.89","1.35.111")
opsfiles=files_runtime(ROOT/"ops",lambda p:p in {"vf-ops.php","uninstall.php"} or p.split("/")[0] in ("includes","assets","languages","config"))
assert re.search(r"(?m)^\s*\*\s*Version:\s*"+re.escape(ops_version)+r"\s*$",opsfiles["vf-ops.php"].decode())
# Match current Provider packaged runtime allowlist; never ship tests/internal receipts.
def m3allow(p):
    parts=p.split("/")
    if any(x.lower() in {".git",".github","test","tests","doc","docs","evidence","private","tmp","temp","cache","log","logs"} for x in parts): return False
    if p.lower().endswith(("readme.md","changelog.md","license","license.txt","package_profile.json")):return False
    if len(parts)==1:return p in {"vf-tool-m3u8.php","uninstall.php","plugin-manifest.json","tool-settings.schema.json"}
    return parts[0] in {"admin","config","includes","public","templates","tools"}
m3files=files_runtime(ROOT/"m3u8/src",m3allow)
assert f"Version: {m3_version}" in m3files["vf-tool-m3u8.php"].decode()
assert ("src/public/js/modules/browser-stream-test.js" not in m3files)
browser_source=(ROOT/"m3u8/src/public/js/modules/browser-stream-test.js").read_text()
bundle=(ROOT/"m3u8/src/public/dist/browser-stream-test.js").read_text()
assert bundle.count(browser_source)==1,"shipped M3U8 JS differs from source"
themefiles=files_runtime(ROOT/"theme/src",lambda p: p.lower() not in {"readme.md","changelog.md"})
assert f"Version: {theme_version}" in themefiles["style.css"].decode()
metadata=json.loads(themefiles["theme.json"])
assert metadata["settings"]["custom"]["vfThemeVersion"]==theme_version
css=themefiles["assets/css/public/vf-theme-public-runtime.css"]
assert sha(css) in themefiles["inc/public-css-owner-registry.php"].decode(),"Theme CSS authority mismatch"
for fragment in ("assets/css/vf-theme-vars.css","assets/css/public/responsive/header-footer/public-responsive-footer.css"):
    assert themefiles[fragment] in css,f"built CSS missing canonical owner {fragment}"
assert f"VF_THEME_VERSION', '{theme_version}'" in themefiles["inc/runtime-constants.php"].decode()
summaries=[
    package("ops","vf-ops",opsfiles),
    package("m3u8","vf-tool-m3u8",m3files),
    package("theme","vf-tools-theme",themefiles),
]
report={"gate":"S01_R9_RUNTIME_ZIP_PREFLIGHT","status":"PASS","scope":"build/readback only","formal_release":"NOT_EXECUTED",
        "channel_distribution":"NOT_EXECUTED","production":"NOT_EXECUTED",
        "owner_final_acceptance":"PENDING","settings_POST_security":"NOT_EXECUTED",
        "recovery_restore":"NOT_EXECUTED","versions":{"ops":ops_version,"m3u8":m3_version,"theme":theme_version},
        "packages":summaries}
(PROOF/"S01_R9_PREFLIGHT_RECEIPT.json").write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
print("S01_R9_RUNTIME_PACKAGE_PREFLIGHT_PASS")
print(json.dumps({"versions":report["versions"],"packages":summaries},sort_keys=True))
