#!/usr/bin/env python3
"""One-case Mode AD, machine prepublication proof only. No release write or channel write.
Exact tested FULL byte parity only. No repeated native, browser, backup or business tests.
All product bytes and detailed logs remain in this disposable hosted runner.
"""
from __future__ import annotations
import hashlib, http.client, importlib.util, io, json, os, re, shutil, socket, ssl
import subprocess, sys, time, urllib.parse, zipfile
from pathlib import Path

SOURCE="b95ccd8062191193bc8971e50fab96c30045e6be"
TREE="cdb50315102fc5693665c52bbdd9aa80a89db21b"
BASE="797821db7679b28d459d5c39a34a8b5f990146c8"
GOV="f7e967fc6fa590942b7cecfb1407ec25f1eaf320"
OLD="4df14f88af6733039c561bde86a98f4b05c05a5c"
OLDTREE="7ebc94da7796824c1b1ba22c835a913c7a8dfbb8"
OLD_ZIP="8376db3fffa9c2874ab4a8bc0e8b359e1cc250669b6189a235d00ad5c6c1256d"
OLD_FULL="8dc3503e5449a7bf5a7fa5da454bc1196fd6515f2d21f05eeb5e736a629cb6d0"
OLD_UI="4ec0e3d9df1b3f99222f4b01cbd1f1f8f410413c7822e4bb936d7efc568b5ab3"
ENV=dict(os.environ)
TMP=Path(ENV["RUNNER_TEMP"]).resolve()
ROOT=Path(ENV["GITHUB_WORKSPACE"]).resolve()
P=ROOT/"p08"; G=ROOT/"gov"; D=TMP/"p08-v018-formal-proof"
PASS=[]
def need(ok,code):
    if not ok: raise RuntimeError(code)
def digest(data): return hashlib.sha256(data).hexdigest()
def filehash(p): return digest(p.read_bytes())
def note(code):
    PASS.append(code)
    print(code+"=PASS",flush=True)
def run(code,args,cwd=P,env=None,timeout=180,markers=()):
    cp=subprocess.run(args,cwd=cwd,env=env or ENV,capture_output=True,timeout=timeout)
    (D/(code+".log")).write_bytes(cp.stdout+b"\n"+cp.stderr)
    if cp.returncode or any(m.encode() not in cp.stdout.splitlines() for m in markers):
        print(code+"_EXIT="+str(cp.returncode),flush=True)
        # Only fixed, non-sensitive diagnostic code tokens from the owning scripts.
        for row in re.findall(rb"\b(?:R43_[A-Z0-9_]{5,100}|P08_[A-Z0-9_]{5,100}|RECOVERY_[A-Z0-9_]{5,100}|FULL_[A-Z0-9_]{5,100})\b",cp.stderr)[:6]:
            print("P08_SAFE_REASON="+row.decode(),flush=True)
        raise RuntimeError(code+"_NOT_PROVEN")
    note(code)
    return cp.stdout.decode(errors="replace").strip()
def git(root,*args):
    return subprocess.check_output(["git","-C",str(root),*args],text=True,stderr=subprocess.DEVNULL,timeout=30).strip()
def check_archive(path,source):
    with zipfile.ZipFile(path) as z:
        names=z.namelist()
        need(z.testzip() is None and len(names)==len(set(names)),"ZIP_INTEGRITY")
        m=json.loads(z.read("FULL_MANIFEST.json"))
        need(m["source_sha"]==source and m["target_version"]=="0.1.18" and m["type"]=="CLEAN_FULL_ONLY" and m["update_type"]=="NOT_ATOMIC" and m["data_included"] is False and m["owner_setup_completed"] is False,"ZIP_IDENTITY")
        index={x["path"]:x for x in m["files"]}
        need(len(index)==len(m["files"]) and set(names)==set(index)|{"FULL_MANIFEST.json"} and len(index)>6000,"ZIP_INDEX")
        for n,x in index.items():
            need(not n.startswith("/") and ".." not in n.split("/") and "\\" not in n and not n.startswith("storage/") and n!=".env","ZIP_PRIVATE_PATH")
            b=z.read(n)
            need(len(b)==x["bytes"] and digest(b)==x["sha256"],"ZIP_MEMBER_HASH")
        return index
def main():
    need(ENV.get("GITHUB_ACTIONS")=="true" and ENV.get("GITHUB_ACTOR")=="llhzx2018" and ENV.get("GITHUB_REPOSITORY")=="llhzx2018/core-free-runner-public" and os.geteuid()!=0,"RUN_SCOPE")
    need(D.is_dir() and not D.is_symlink() and git(P,"rev-parse","HEAD")==SOURCE and git(P,"rev-parse","HEAD^{tree}")==TREE and git(P,"rev-parse","refs/remotes/origin/main")==SOURCE and git(G,"rev-parse","HEAD")==GOV,"EXACT_SOURCE")
    need((P/"VERSION").read_text().strip()=="0.1.18" and "## RP-07AD" in (P/"docs/authority/ACCEPTANCE_MATRIX.md").read_text() and "| skill-release | V3.30 |" in (G/"CURRENT.md").read_text(),"MODE_AD_AUTHORITY")
    need(set(git(P,"diff","--name-only",BASE,SOURCE).splitlines())=={"CLOUDPANEL_INSTALL.txt","public/p08-install-build.txt","docs/authority/ACCEPTANCE_MATRIX.md"},"FINAL_DIFF")
    note("P08_MODE_AD_FINAL_SOURCE")
    run("PHP84_FLOOR",["php","-r",'exit(PHP_VERSION_ID>=80428 && PHP_VERSION_ID<80500 && extension_loaded("pdo_mysql") && extension_loaded("pdo_sqlite") && extension_loaded("pcntl") && extension_loaded("zip")?0:2);'])
    need(run("NODE_VERSION",["node","--version"])=="v24.22.3","NODE_PIN")
    need("Composer version 2.11.3" in run("COMPOSER_VERSION",["composer","--no-plugins","--no-scripts","--no-ansi","--version"]),"COMPOSER_PIN")
    prefix=D/"pnpm";prefix.mkdir(mode=0o700)
    run("PNPM_TOOL",["npm","install","--prefix",str(prefix),"--ignore-scripts","--no-fund","--no-audit","pnpm@11.29.0"],cwd=D,timeout=240)
    ENV["PATH"]=str(prefix/"node_modules/.bin")+":"+ENV["PATH"]
    need(run("PNPM_VERSION",["pnpm","--version"])=="11.29.0","PNPM_PIN")
    run("COMPOSER_LOCK",["composer","install","--no-dev","--no-scripts","--no-plugins","--prefer-dist","--no-interaction","--no-progress"],timeout=600)
    run("COMPOSER_PLATFORM",["composer","check-platform-reqs","--no-dev"],timeout=90)
    run("PNPM_LOCK",["pnpm","install","--frozen-lockfile"],timeout=600)
    run("VITE_BUILD",["pnpm","run","build"],timeout=240)
    need(not git(P,"status","--porcelain","--untracked-files=all"),"TRACKED_OR_UNIGNORED_DRIFT")
    run("STACK_FULL",["python3","-B","scripts/check_stack_contract.py","--phase","full"],timeout=90)
    sys.path.insert(0,str(P/"scripts"))
    import build_full as builder
    a=D/"VF_AdOps_V0.1.18_FULL.zip"
    # Prepublication construction only, delivery checker runs after actual install and B byte parity.
    builder.verify_canonical_full_contract(P,a,SOURCE,G,"resolve")
    builder.write_full(P,a,"0.1.18",SOURCE)
    index=check_archive(a,SOURCE)
    print("P08_MODE_AD_FULL_SHA256="+filehash(a),flush=True)
    print("P08_MODE_AD_FULL_BYTES="+str(a.stat().st_size),flush=True)
    print("P08_MODE_AD_FULL_PAYLOAD_FILES="+str(len(index)),flush=True)
    need(filehash(a)=="31273d8f2ca41b485d40cb50e094efd3f9eeb72eefb9d2b62abd5e4dfba11fab","EXACT_PRIOR_TESTED_FULL_BYTES")
    note("EXACT_PRIOR_TESTED_FULL_BYTES")
    # Compare only aggregate byte fingerprints derived independently from the original
    # accepted private artifact in the connected review environment. No private
    # artifact retrieval, no screenshots or payload disclosure in this public job.
    exclude={"CLOUDPANEL_INSTALL.txt","public/p08-install-build.txt","vendor/composer/installed.php"}
    rows={k:v["sha256"] for k,v in index.items() if k not in exclude}
    def fp(x): return digest(json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode())
    groups={
        "VENDOR":{k:v for k,v in rows.items() if k.startswith("vendor/")},
        "ASSETS":{k:v for k,v in rows.items() if k.startswith("public/build/")},
        "APP":{k:v for k,v in rows.items() if not k.startswith(("vendor/","public/build/"))}}
    expected={"VENDOR":"3941ed92c198216523a49c9536cd954202a734926f69286ac7cf2693f476c0e8","ASSETS":"7b291026a0ae2b4799eec14158341d58acc04f7e899c45f31fa8ce053529cb3e","APP":"a2ca4d4b2bcd63f5773cae1d17fb9fbfa4a148fba00a1c8d9541550f113b18e9"}
    for k,v in groups.items():
        print("P08_PARITY_"+k+"_COUNT="+str(len(v)),flush=True)
        print("P08_PARITY_"+k+"_SHA256="+fp(v),flush=True)
        print("P08_PARITY_"+k+"="+("PASS" if fp(v)==expected[k] else "DIFFERENT"),flush=True)
    with zipfile.ZipFile(a) as z:
        php=z.read("vendor/composer/installed.php")
        normalized=php.replace(SOURCE.encode(),b"0"*40)
        print("P08_COMPOSER_ROOT_IDENTITY_NORMALIZED_SHA256="+digest(normalized),flush=True)
        print("P08_COMPOSER_SOURCE_REFERENCE_COUNT="+str(php.count(SOURCE.encode())),flush=True)
        # Only the two project root version strings are disclosed, never dependency or application bytes.
        head=php.split(b"'versions' =>",1)[0]
        for field in ("pretty_version","version","reference"):
            m=re.search(rb"'"+field.encode()+rb"' => '([A-Za-z0-9._-]{1,100})'",head)
            if m: print("P08_COMPOSER_ROOT_"+field.upper()+"="+m.group(1).decode(),flush=True)
        print("P08_FINAL_MANIFEST_SHA256="+digest(z.read("FULL_MANIFEST.json")),flush=True)
    import zlib
    print("P08_ARCHIVE_ZLIB="+zlib.ZLIB_RUNTIME_VERSION,flush=True)
    print("P08_ARCHIVE_PYTHON="+sys.version.split()[0],flush=True)
    print("P08_NORMALIZED_RUNTIME_SHA256="+fp(rows),flush=True)
    need(len(rows)==6312 and fp(rows)=="aae519e76f6071e290d199ab21739f7643566f0908d9749097640a48bf3b79cf" and digest(normalized)=="d30b606f6d062d8bad96ae60fa227e05cd1e342abe3669812f8049e1f7042bd3","B_RUNTIME_PARITY_NOT_PROVEN")
    note("P08_B_ORIGINAL_RUNTIME_BYTE_PARITY")
    print("P08_FINAL_UX_GATE=INDEPENDENT_DECISION_NOT_APPLIED",flush=True)
    print("P08_FORMAL_RELEASE=NOT_ISSUED",flush=True)
if __name__=="__main__":
    try: main()
    except Exception as e:
        reason=str(e)
        print("P08_MODE_AD_PARITY_STOP="+(reason if re.fullmatch(r"[A-Z0-9_a-z]{3,120}",reason) else "UNCLASSIFIED_SAFE"),flush=True)
        sys.exit(1)
