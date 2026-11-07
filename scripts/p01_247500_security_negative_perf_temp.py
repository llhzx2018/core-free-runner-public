#!/usr/bin/env python3
"""One-off V500 fail-closed asset/source/path and real HTTP contention proof.

Only synthetic SQLite, official v499 bytes and transient v500 candidate.
No public artifacts, no owner data, no production network.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import zipfile

def require(ok, reason):
    if not ok: raise AssertionError(reason)

def cmd(*args, cwd=None, allowed=(0,), timeout=30):
    p=subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE, timeout=timeout)
    if allowed is not None:require(p.returncode in allowed,"command rc="+str(p.returncode)+" "+p.stderr[-300:])
    return p

def apply(repair, site, ok):
    p=cmd("php",str(repair),"--run="+str(site),cwd=site,allowed=None,timeout=65)
    require((p.returncode==0)==ok,"Atomic fail-closed result mismatch rc="+str(p.returncode))
    return p

def expect_version(site,version):
    require((site/"VERSION.txt").read_text().strip()==version,"version identity mismatch")

def external_core_contract(site, update, work):
    file=work/"origin.update.php"
    good_bytes=update.read_bytes()
    bad=work/"corrupt-update.zip"
    corrupted=bytearray(good_bytes)
    corrupted[min(len(corrupted)-80,max(30,len(corrupted)//2))]^=1
    bad.write_bytes(corrupted)
    sym=work/"update-link.zip"
    sym.symlink_to(update)
    schema="2026102201"
    manifest={
        "schema_version":"1.0","project_id":"P01","component_id":"APP","enabled":True,
        "current_version":"2.47.499","target_version":"2.47.500",
        "update_type":"ATOMIC","from_versions":["2.47.499"],"schema_from":schema,"schema_to":schema,
        "repository":"llhzx2018/vf-start","release_tag":"v2.47.500",
        "asset_name":"VF_Start_V2.47.500_UPDATE.zip","asset_bytes":len(good_bytes),
        "asset_sha256":hashlib.sha256(good_bytes).hexdigest(),
        "backup_required":True,"rollback_supported":True,"released_at":"2026-11-07T00:00:00Z"}
    file.write_text(json.dumps(manifest))
    php=(
        'require $argv[1]."/app/bootstrap.php";'
        '$m=json_decode(file_get_contents($argv[2]),true);'
        '$c=new \\CoreUpdates\\UpdateCore("P01","APP");'
        'echo json_encode(["good"=>$c->verifyPackage($argv[3],$m),'
        '"tampered"=>$c->verifyPackage($argv[4],$m),'
        '"symlink"=>$c->verifyPackage($argv[5],$m),'
        '"allowed"=>$c->check("2.47.499","2026102201",$m),'
        '"old"=>$c->check("2.47.498","2026102201",$m)],JSON_UNESCAPED_SLASHES);'
    )
    p=cmd("php","-r",php,str(site),str(file),str(update),str(bad),str(sym),cwd=site)
    d=json.loads(p.stdout)
    require(d["good"]["status"]=="VERIFIED","valid sealed bytes not accepted")
    require(d["tampered"]["status"] in ("ASSET_HASH_MISMATCH","ASSET_SIZE_MISMATCH"),
            "modified package wrongly accepted")
    require(d["symlink"]["status"]=="PACKAGE_NOT_FOUND","symlink package wrongly accepted")
    require(d["allowed"]["status"]=="AVAILABLE","official 499 compatibility lost")
    require(d["old"]["status"]=="BLOCKED_SOURCE_VERSION","unproven 498 direct source accepted")
    print("P01_247500_REAL_UPDATE_CORE_TAMPER_SYMLINK_SOURCE_VERSION_NEGATIVES=PASS",flush=True)

def source_negative_tests(site, repair, helper, ident, title):
    original=site/"index.php"
    b=original.read_bytes()
    require(b and not original.is_symlink(),"source not normal")
    original.write_bytes(b+b"\n<!-- synthetic-source-tamper -->\n")
    try:
        p=cmd("php",str(repair),"--verify-source="+str(site),cwd=site,allowed=None)
        require(p.returncode!=0,"corrupted source manifest was accepted")
        apply(repair,site,False)
        expect_version(site,"2.47.499")
        helper.check_sentinel(site,ident,title)
        print("P01_247500_TAMPERED_SOURCE_DENY_WITH_PRIVATE_DATA_PRESERVED=PASS",flush=True)
    finally:original.write_bytes(b)

    original.rename(site/"index.php.safe-test")
    try:
        original.symlink_to("index.php.safe-test")
        p=cmd("php",str(repair),"--verify-source="+str(site),cwd=site,allowed=None)
        require(p.returncode!=0,"source symlink accepted")
        apply(repair,site,False)
        expect_version(site,"2.47.499")
        helper.check_sentinel(site,ident,title)
        print("P01_247500_SOURCE_SYMLINK_DENY_WITH_PRIVATE_DATA_PRESERVED=PASS",flush=True)
    finally:
        original.unlink(missing_ok=True)
        (site/"index.php.safe-test").rename(original)

    p=cmd("php",str(repair),"--verify-source="+str(site),cwd=site)
    require('"ok":true' in p.stdout.replace(" ",""),"source not restored")
    print("P01_247500_RECOVERABLE_SOURCE_RESTORE_AND_VERIFY=PASS",flush=True)

def real_http_bound(site, port):
    root="http://127.0.0.1:"+str(port)
    held='require $argv[1]."/app/bootstrap.php";$l=VfMaintenanceBarrier::globalExclusive();echo "HELD\\n";fflush(STDOUT);sleep(9);'
    ex=subprocess.Popen(["php","-r",held,str(site)],cwd=site,
                        text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=1)
    srv=None
    try:
        r,_,_=select.select([ex.stdout],[],[],4)
        require(r and ex.stdout.readline().strip()=="HELD","cannot hold EX lease")
        env=os.environ.copy()
        env["PHP_CLI_SERVER_WORKERS"]="6"
        srv=subprocess.Popen(["php","-S",f"127.0.0.1:{port}","-t",str(site)],cwd=site,
                            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=env)
        # Static requests must remain immediately usable, even under global EX.
        for _ in range(45):
            try:
                with urllib.request.urlopen(root+"/VERSION.txt",timeout=1) as x:
                    if x.status==200:break
            except Exception:time.sleep(.1)
        else: raise AssertionError("PHP test HTTP origin unavailable")
        def get_one(_):
            start=time.monotonic()
            try:
                with urllib.request.urlopen(root+"/index.php",timeout=4) as response:
                    status=response.status
                    body=response.read(2500).decode(errors="replace")
            except urllib.error.HTTPError as e:
                status=e.code
                body=e.read(2500).decode(errors="replace")
            return status,time.monotonic()-start,body
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(get_one,range(4)))
        for status,duration,body in results:
            require(status in (429,500,503),"HTTP lock handler not fail closed "+str(status))
            require(duration < 3.5,"HTTP origin reached 524-class long lock wait "+str(duration))
            require("/tmp/" not in body and "Traceback" not in body,"private path/trace leaked")
        print("P01_247500_FOUR_CONCURRENT_HTTP_ORIGIN_GLOBAL_LOCK_BOUNDED_DENIAL=PASS",flush=True)
    finally:
        if srv:
            srv.terminate()
            try:srv.wait(timeout=5)
            except subprocess.TimeoutExpired:srv.kill();srv.wait(timeout=4)
        ex.terminate()
        try:ex.wait(timeout=5)
        except subprocess.TimeoutExpired:ex.kill();ex.wait(timeout=4)

    post=cmd("php",str(site/"cli/verify.php"),cwd=site,timeout=30)
    require("VERIFY_PASS=YES" in post.stdout,"CLI recover failed")
    print("P01_247500_LOCK_RELEASE_POST_RECOVERY_CLI_VERIFY=PASS",flush=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--work",required=True)
    ap.add_argument("--full499",required=True)
    ap.add_argument("--atomic500",required=True)
    args=ap.parse_args()
    from importlib.util import spec_from_file_location,module_from_spec
    path=Path(__file__).with_name("p01_247500_candidate_synthetic_helpers_temp.py")
    spec=spec_from_file_location("p01_synthetic",path)
    helper=module_from_spec(spec);spec.loader.exec_module(helper)
    work=Path(args.work)
    full=Path(args.full499)
    update=Path(args.atomic500)
    root=work/"negatives-installed-499"
    helper.unpack_bundle(full,root)
    helper.synthetic_setup(root,18951)
    title="private synthetic update negative"
    ident=helper.sentinel(root,title)
    with zipfile.ZipFile(update) as z:
        names=z.namelist()
        require(names==["repair-v2.47.500.php"],"Atomic archive unexpected files")
        repair=root/names[0]
        repair.write_bytes(z.read(names[0]))
    external_core_contract(root,update,work)
    source_negative_tests(root,repair,helper,ident,title)
    apply(repair,root,True)
    expect_version(root,"2.47.500")
    helper.check_sentinel(root,ident,title)
    real_http_bound(root,18952)
    helper.check_sentinel(root,ident,title)
    print("P01_247500_FINAL_UPDATER_NEGATIVE_AND_HTTP_PERF_GATE=PASS",flush=True)
    print("P01_247500_OWNER_PREVIEW=POST_RELEASE_REQUIRED_NOT_PASS",flush=True)
    print("P01_247500_PRODUCTION=UNCHANGED",flush=True)
if __name__=="__main__":main()
