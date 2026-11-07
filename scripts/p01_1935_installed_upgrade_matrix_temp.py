#!/usr/bin/env python3
"""Isolated 2.47.498/499 -> DERIVED 2.47.500 installed upgrade smoke.
Not a Formal Release artifact or exact target release-tree proof.
Only synthetic users/SQLite and temporary release extract paths are allowed.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import http.cookiejar
import zipfile

SRC_VERSIONS = ("2.47.498", "2.47.499")
TARGET_VERSION = "2.47.500"
SCHEMA = "2026102201"

def run(*args, cwd=None, env=None, expect=0, timeout=90):
    c = subprocess.run(args, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, timeout=timeout)
    if (expect is not None and c.returncode != expect):
        raise AssertionError("CMD FAILED: "+str(args[:2])+" rc="+str(c.returncode)+"\n"+c.stdout[-1400:]+"\n"+c.stderr[-1400:])
    return c

def require(ok, description):
    if not ok: raise AssertionError(description)

def load_python(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "missing trusted builder module")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

def source_manifest(repair_file, official_full):
    raw=repair_file.read_text(encoding="utf-8")
    m=re.search(r"private const TARGET_MANIFEST='([^']+)';", raw)
    require(bool(m), "prior official target manifest is missing")
    obj=json.loads(base64.b64decode(m.group(1)))
    require(isinstance(obj,dict) and len(obj)>10 and "VERSION.txt" in obj and "app/bootstrap.php" in obj, "prior official target manifest identity missing")
    source={}
    for rel,digest in obj.items():
        p=official_full/rel
        require(p.is_file() and not p.is_symlink(),"official FULL missing runtime file")
        blob=p.read_bytes()
        require(hashlib.sha256(blob).hexdigest()==digest,"official FULL differs from official Atomic target")
        source[rel]=blob
    return source

def make_repair(builder, m, source, target, srcver, dest):
    txt=builder.build_repair(source,target,"")
    for name,value in (("SOURCE_VERSION",srcver),("TARGET_VERSION",TARGET_VERSION),("TARGET_SCHEMA",SCHEMA)):
        txt=m.replace_public(txt,name,value)
    dest.write_text(txt, encoding="utf-8")
    run("php","-l",str(dest))
    result=run("php",str(dest),"--self-test")
    require(json.loads(result.stdout).get("ok") is True,"generated repair self-test false")
    return dest

def synthetic_setup(root, port):
    server = subprocess.Popen(["php","-S",f"127.0.0.1:{port}","-t",str(root)],
                              cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        jar=http.cookiejar.CookieJar()
        op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        url=f"http://127.0.0.1:{port}/setup.php"
        page=""
        for _ in range(60):
            try:
                with op.open(url, timeout=2) as res: page=res.read().decode("utf-8")
                break
            except Exception:
                time.sleep(0.15)
        require(bool(page),"synthetic setup web request failed")
        m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',page)
        require(bool(m),"synthetic setup csrf missing")
        payload=urllib.parse.urlencode({
            "setup_csrf":m.group(1), "site_title":"P01 upgrade isolated proof",
            "admin_password":"SyntheticOnly!Passw0rd", "admin_password_confirm":"SyntheticOnly!Passw0rd",
        }).encode()
        with op.open(urllib.request.Request(url,data=payload,method="POST"),timeout=25) as response:
            require(response.status in (200,302),"setup post failed")
    finally:
        server.terminate()
        try: server.wait(timeout=4)
        except subprocess.TimeoutExpired: server.kill(); server.wait(timeout=4)
    check=run("php",str(root/"cli/verify.php"),cwd=root,timeout=45)
    require("VERIFY_PASS=YES" in check.stdout, "installed CLI verify false "+check.stdout[-500:])

def sentinel(root,title):
    code=(
      'require $argv[1]."/app/bootstrap.php";'
      '$repo=new VfRepository(vf_db());'
      '$cat=$repo->createCategory(["name"=>"Upgrade synthetic","description"=>"","icon"=>"","is_private"=>1,"sort_order"=>0]);'
      '$v=$repo->saveLink(null,["surface"=>"start","category_id"=>$cat,'
      '"title"=>$argv[2],"url"=>"https://example.invalid/synthetic-upgrade",'
      '"description"=>"must survive","tags"=>["synthetic"],"is_private"=>1,"is_pending"=>0]);'
      'echo $v["id"];'
    )
    result=run("php","-r",code,str(root),title,cwd=root)
    return int(result.stdout.strip())

def check_sentinel(root,ident,title):
    code=(
      'require $argv[1]."/app/bootstrap.php";'
      '$s=vf_db()->prepare("SELECT title,is_private FROM links WHERE id=?");'
      '$s->execute([(int)$argv[2]]);$r=$s->fetch(PDO::FETCH_ASSOC);'
      'if(!$r||$r["title"]!==$argv[3]||(int)$r["is_private"]!==1)exit(7);'
      'echo "PRESERVED";'
    )
    result=run("php","-r",code,str(root),str(ident),title,cwd=root)
    require("PRESERVED" in result.stdout, "synthetic private identity lost")

def unpack_bundle(archive, path):
    path.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for item in z.namelist():
            require(not item.startswith("/") and ".." not in Path(item).parts, "unsafe archive path")
        z.extractall(path)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--workspace",required=True)
    ap.add_argument("--candidate",required=True)
    ap.add_argument("--source-release-dir",required=True)
    args=ap.parse_args()
    wk=Path(args.workspace).resolve(); cand=Path(args.candidate).resolve()
    rel=Path(args.source_release_dir).resolve()
    require(wk.is_dir() and cand.is_dir(),"test workspace not allocated")
    public=Path(__file__).resolve().parent
    base=load_python(public/"p01-build-release.py","p01_old_helpers")
    engine=load_python(public/"p01-build-release-v2.py","p01_atomic_builder")
    maintenance=load_python(public/"p01-maintenance-release.py","p01_maintenance_helper")
    target_files=base.collect(cand/"src")
    require(target_files["VERSION.txt"].strip()==b"2.47.499","candidate exact version shifted")
    target_files["VERSION.txt"]=(TARGET_VERSION+"\n").encode()
    old=target_files["app/bootstrap.php"]
    updated=old.replace(b"define('VF_VERSION', '2.47.499');",b"define('VF_VERSION', '2.47.500');")
    require(updated!=old,"bootstrap target-version binding missing")
    target_files["app/bootstrap.php"]=updated
    require(not any(x.endswith(".sqlite") or ".runtime.php" in x for x in target_files),"private data in target")
    # Isolated FULL is derived from exact product source, not an official signed asset.
    new_full=wk/"derived-target-full"
    new_full.mkdir()
    for relpath,blob in target_files.items():
        f=new_full/relpath;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(blob)
    manifest={"project_id":"P01","version":TARGET_VERSION,"source_version":"2.47.499",
              "schema_version":SCHEMA,"source_commit":os.environ.get("PRODUCT_SHA",""),
              "test_derivation_only":True,
              "runtime_files":{k:hashlib.sha256(v).hexdigest() for k,v in target_files.items()}}
    (new_full/"release-manifest.json").write_text(json.dumps(manifest),encoding="utf-8")
    target_install=wk/"clean-target"
    shutil.copytree(new_full,target_install)
    synthetic_setup(target_install,18750)
    require((target_install/"VERSION.txt").read_text().strip()==TARGET_VERSION,"clean FULL version mismatch")
    print("P01_1935_DERIVED_TARGET_CLEAN_FULL_INSTALL=PASS",flush=True)
    for index,srcver in enumerate(SRC_VERSIONS):
        srczip=rel/f"VF-Start-V{srcver}-FULL.zip"
        updatezip=rel/f"VF_Start_V{srcver}_UPDATE.zip"
        require(srczip.is_file() and updatezip.is_file(),"missing official source artifact")
        srcfull=wk/("official-source-"+srcver)
        srcupdate=wk/("official-update-"+srcver)
        unpack_bundle(srczip,srcfull);unpack_bundle(updatezip,srcupdate)
        source=source_manifest(srcupdate/f"repair-v{srcver}.php",srcfull)
        # Match official manifest scoped files, not release-only full package notes.
        repair=make_repair(engine,maintenance,source,target_files,srcver,
                           wk/f"derived-from-{srcver}-repair.php")
        oldsite=wk/("success-"+srcver)
        shutil.copytree(srcfull,oldsite)
        synthetic_setup(oldsite,18751+index)
        sent_id=sentinel(oldsite,"Synthetic success "+srcver)
        verf=run("php",str(repair),"--verify-source="+str(oldsite),expect=0,timeout=30)
        require(json.loads(verf.stdout).get("ok") is True,"source bytes not exact")
        # Repair from OUTSIDE site is okay in CLI; run(root) is explicit.
        result=run("php",str(repair),"--run="+str(oldsite),cwd=oldsite,timeout=150)
        require(json.loads(result.stdout).get("ok") is True,"atomic reported failure")
        require((oldsite/"VERSION.txt").read_text().strip()==TARGET_VERSION,"atomic target not installed")
        post=run("php",str(oldsite/"cli/verify.php"),cwd=oldsite,timeout=30)
        require("VERIFY_PASS=YES" in post.stdout,"post-upgrade verify failed")
        check_sentinel(oldsite,sent_id,"Synthetic success "+srcver)
        repeated=run("php",str(repair),"--run="+str(oldsite),cwd=oldsite,timeout=90)
        require(json.loads(repeated.stdout).get("already_current") is True,"repeat should be idempotent")
        print("P01_1935_ATOMIC_"+srcver.replace(".","_")+"_TO_DERIVED_TARGET=PASS",flush=True)
        print("P01_1935_PRIVATE_SENTINEL_"+srcver.replace(".","_")+"=PASS",flush=True)

        rollbacksite=wk/("rollback-"+srcver)
        shutil.copytree(srcfull,rollbacksite)
        synthetic_setup(rollbacksite,18753+index)
        rollback_id=sentinel(rollbacksite,"Synthetic rollback "+srcver)
        env=os.environ.copy();env["VF_ATOMIC_TEST_FAIL_AFTER_APPLY"]="1"
        failed=run("php",str(repair),"--run="+str(rollbacksite),cwd=rollbacksite,env=env,expect=None,timeout=150)
        require(failed.returncode!=0,"injected failure must fail")
        require((rollbacksite/"VERSION.txt").read_text().strip()==srcver,"rollback version not preserved")
        back=run("php",str(rollbacksite/"cli/verify.php"),cwd=rollbacksite,timeout=30)
        require("VERIFY_PASS=YES" in back.stdout,"post-rollback site verify failed")
        check_sentinel(rollbacksite,rollback_id,"Synthetic rollback "+srcver)
        print("P01_1935_ROLLBACK_"+srcver.replace(".","_")+"_FROM_DERIVED_TARGET=PASS",flush=True)
    print("P01_1935_FORMAL_RELEASE_PROOF=NOT_PROVEN_DERIVED_TARGET",flush=True)
    print("P01_1935_PRODUCTION_WRITE=NONE",flush=True)

if __name__=="__main__":
    main()
