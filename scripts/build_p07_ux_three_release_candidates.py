#!/usr/bin/env python3
"""Assemble exact immutable P07 M01/M02/M04 UX release *candidates*.

A complete ZIP is NOT a released GitHub asset until independent machine
install/upgrade/rollback and dual remote-asset verification have passed.
Do not install on an Owner VPS or modify the public Toolbox from this builder.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import zipfile
from datetime import datetime

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("p07_dev",ROOT/"scripts/build_p07_ux_prepublication_candidates.py")
dev=importlib.util.module_from_spec(spec);spec.loader.exec_module(dev)
MODULES=[
 ("P07-M01","网络代理节点（V2Ray）","0.1.0-ux3","vf-node.sh",dev.make_m01),
 ("P07-M02","服务器性能检测（VPS 验机）","2.1.1-ux3","vps-audit.sh",dev.make_m02),
 ("P07-M04","服务器维护与安全","0.1.0-ux5","vf-system-care.sh",dev.make_m04),
]
STAMP=(2026,11,18,0,0,0)

def sha(b):return hashlib.sha256(b).hexdigest()

def build_payload(module,name,version,entry,maker):
    files=maker()
    assert files.pop("PREPUBLISH_METADATA.json",None)
    if module=="P07-M01":
        identity=files["SOURCE_IDENTITY"].decode()
        identity=identity.replace("FORMAL_RELEASE=NO\n","")
        identity=identity.replace("CANDIDATE_SOURCE_ONLY=YES\n","")
        identity+="RELEASE_GATE=REMOTE_SHA256_AND_MACHINE_REQUIRED\n"
        files["SOURCE_IDENTITY"]=identity.encode()
        files["MANIFEST.sha256"]="".join(f"{sha(data)}  {n}\n" for n,data in sorted(files.items()) if n!="MANIFEST.sha256").encode()
    if module=="P07-M04":
        files["MANIFEST.gitblob"]="".join(
            f"{dev.blob(data)}  {n}\n" for n,data in sorted(files.items()) if n!="MANIFEST.gitblob").encode()
    files["VERSION"]=(version+"\n").encode()
    meta={
        "schema":"vf.p07.ux.module-bundle.v1",
        "module_id":module,"module_name":name,"module_build_id":version,
        "entrypoint":entry,"installation_isolation":module+"_ONLY",
        "files":{n:sha(data) for n,data in sorted(files.items())}
    }
    files["MODULE_MANIFEST.json"]=(json.dumps(meta,sort_keys=True,ensure_ascii=False,separators=(",",":"))+"\n").encode()
    return files

def output_zip(path,module,files):
    prefix="p07-"+module.split("-")[-1].lower()+"/"
    with zipfile.ZipFile(path,"x",compression=zipfile.ZIP_DEFLATED,compresslevel=9,allowZip64=False) as z:
        for name,data in sorted(files.items()):
            if not re.fullmatch(r"[A-Za-z0-9_./-]+",name) or ".." in name.split("/") or name.startswith("/"):
                raise ValueError("invalid candidate member")
            info=zipfile.ZipInfo(prefix+name,STAMP)
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=((0o100755 if name.endswith(".sh") else 0o100644)<<16)
            z.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    return sha(path.read_bytes())

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output-dir",type=Path,required=True)
    opts=p.parse_args()
    dest=opts.output_dir.resolve()
    if dest==ROOT or ROOT in dest.parents:
        raise ValueError("do not create candidates inside source tree")
    dest.mkdir(parents=True,exist_ok=True)
    if any(dest.iterdir()):raise ValueError("output must be empty")
    sums=[]
    for module,name,version,entry,make in MODULES:
        files=build_payload(module,name,version,entry,make)
        filename=f"{module}-{version}-RELEASE-CANDIDATE.zip"
        artifact=dest/filename
        digest=output_zip(artifact,module,files)
        sums.append((digest,filename))
        print(f"{module} {name}: {len(files)} verified members; SHA256={digest}")
    (dest/"SHA256SUMS").write_text("".join(f"{digest}  {name}\n" for digest,name in sums))
    print("P07_UX_THREE_INSTALLABLE_EXACT_SOURCE_CANDIDATES=STAGED_ONLY")
    print("P07_FORMAL_RELEASE_GITHUB_ASSETS=NOT_RUN")

if __name__=="__main__":
    try:main()
    except (OSError,ValueError,AssertionError,KeyError,zipfile.BadZipFile) as exc:
        sys.exit("P07_UX_THREE_INSTALLABLE_BLOCKED: "+str(exc))
