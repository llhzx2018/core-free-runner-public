#!/usr/bin/env python3
"""One-shot pre-release P01 v2.47.502 FULL/Atomic proof; synthetic data only.

Real official 2.47.501 FULL and UPDATE bytes are supplied externally by the
registered runner. No GitHub Tag/Release/channel/Production write.
"""
from __future__ import annotations
import argparse
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import time
import urllib.parse
import urllib.request
import zipfile

PASSWORD="SyntheticOnly!Passw0rd"

def require(ok,reason):
    if not ok: raise AssertionError(reason)

def run(*cmd,cwd=None,env=None,success=True,timeout=180):
    p=subprocess.run(list(cmd),cwd=cwd,env=env,capture_output=True,text=True,timeout=timeout)
    if success: require(p.returncode==0,"step returned nonzero "+str(p.returncode)+" "+p.stderr[-250:])
    return p

def digest(file):
    return hashlib.sha256(Path(file).read_bytes()).hexdigest()

def safe_unpack(archive,target):
    target.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            require(name and not name.startswith("/") and ".." not in Path(name).parts,
                    "unsafe archive path")
        z.extractall(target)

def http_install(site):
    sock=socket.socket()
    sock.bind(("127.0.0.1",0));port=sock.getsockname()[1];sock.close()
    server=subprocess.Popen(["php","-S",f"127.0.0.1:{port}","-t",str(site)],
                            cwd=site,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        jar=http.cookiejar.CookieJar()
        opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        url=f"http://127.0.0.1:{port}/setup.php"
        body=""
        for _ in range(60):
            try:
                with opener.open(url,timeout=3) as r:body=r.read().decode()
                break
            except Exception:time.sleep(.15)
        require(bool(body),"synthetic PHP installer could not open")
        csrf=re.search(r'name="setup_csrf"\s+value="([^"]+)"',body)
        require(csrf is not None,"installer CSRF missing")
        payload=urllib.parse.urlencode({
            "setup_csrf":csrf.group(1),"site_title":"P01 502 synthetic candidate",
            "admin_password":PASSWORD,"admin_password_confirm":PASSWORD,
        }).encode()
        with opener.open(urllib.request.Request(url,data=payload,method="POST"),timeout=30) as response:
            require(response.status in (200,302),"setup post status")
    finally:
        server.terminate()
        try:server.wait(timeout=5)
        except subprocess.TimeoutExpired:server.kill();server.wait(timeout=5)
    r=run("php",str(site/"cli/verify.php"),cwd=site,timeout=40)
    require("VERIFY_PASS=YES" in r.stdout,"installed database verify failed")

def sentinel(site,name):
    code=(
      'require $argv[1]."/app/bootstrap.php";'
      '$repo=new VfRepository(vf_db());'
      '$cat=$repo->createCategory(["name"=>"Synthetic private recovery","is_private"=>true]);'
      '$v=$repo->saveLink(null,["surface"=>"start","category_id"=>$cat,'
      '"title"=>$argv[2],"url"=>"https://example.invalid/p01-502-sentinel",'
      '"description"=>"synthetic private owner record","is_private"=>true]);'
      'echo $v["id"];'
    )
    result=run("php","-r",code,str(site),name,cwd=site)
    return int(result.stdout.strip())

def check_sentinel(site,item,name):
    code=(
      'require $argv[1]."/app/bootstrap.php";'
      '$q=vf_db()->prepare("SELECT title,is_private,lifecycle_state FROM links WHERE id=?");'
      '$q->execute([(int)$argv[2]]);$a=$q->fetch(PDO::FETCH_ASSOC);'
      'if(!$a||$a["title"]!==$argv[3]||(int)$a["is_private"]!==1'
      '||$a["lifecycle_state"]!=="active")exit(7);echo "PRESERVED";'
    )
    result=run("php","-r",code,str(site),str(item),name,cwd=site)
    require("PRESERVED" in result.stdout,"synthetic Owner record lost")

def installed(site,version):
    require((site/"VERSION.txt").read_text().strip()==version,"runtime version mismatch")
    r=run("php",str(site/"cli/verify.php"),cwd=site,timeout=50)
    require("VERIFY_PASS=YES" in r.stdout,"SQLite integrity/fk/source verify failed")

def main():
    a=argparse.ArgumentParser()
    for name in ("work","candidate","old-full","old-update","candidate-sha","candidate-tree"):
        a.add_argument("--"+name,required=True)
    z=a.parse_args()
    work=Path(z.work).resolve()
    cand=Path(z.candidate).resolve()
    old_full=Path(z.old_full).resolve()
    old_update=Path(z.old_update).resolve()
    require(cand.is_dir() and old_full.is_file() and old_update.is_file(),"missing exact inputs")
    source=work/"official-501-full";updates=work/"official-501-update"
    safe_unpack(old_full,source);safe_unpack(old_update,updates)
    old_repair=updates/"repair-v2.47.501.php"
    require(old_repair.is_file(),"official 501 repair missing")
    require((source/"VERSION.txt").read_text().strip()=="2.47.501","not 501 source")
    require((cand/"VERSION").read_text().strip()=="2.47.502","candidate root version mismatch")
    require((cand/"src/VERSION.txt").read_text().strip()=="2.47.502","candidate runtime version mismatch")
    require("define('VF_VERSION', '2.47.502');" in
            (cand/"src/app/bootstrap.php").read_text(),"candidate bootstrap mismatch")
    print("P01_502_THREE_VERSION_IDENTITIES=PASS",flush=True)

    builder=Path(__file__).resolve().parent/"p01-maintenance-release.py"
    hashes=[]
    for index in (1,2):
        dest=work/f"test-only-502-build-{index}"
        result=run("python3",str(builder),"--candidate",str(cand/"src"),
                   "--baseline-full",str(source),
                   "--baseline-repair",str(old_repair),
                   "--out",str(dest),"--version","2.47.502",
                   "--source-version","2.47.501",
                   "--target-sha",z.candidate_sha,
                   "--target-tree",z.candidate_tree,timeout=150)
        receipt=json.loads(result.stdout)
        require(receipt.get("version")=="2.47.502" and
                receipt.get("source_version")=="2.47.501",
                "candidate receipt source and target mismatch")
        full=dest/"VF-Start-V2.47.502-FULL.zip"
        patch=dest/"VF_Start_V2.47.502_UPDATE.zip"
        require(receipt["full_sha256"]==digest(full) and
                receipt["update_sha256"]==digest(patch),
                "candidate receipt digest not match byte content")
        hashes.append((digest(full),digest(patch)))
    require(hashes[0]==hashes[1],"non-deterministic 502 candidate archives")
    print("P01_502_ISOLATED_FULL_UPDATE_DETERMINISTIC_TWICE=PASS",flush=True)
    print("P01_502_TEST_ONLY_FULL_SHA256="+hashes[0][0],flush=True)
    print("P01_502_TEST_ONLY_UPDATE_SHA256="+hashes[0][1],flush=True)
    dest=work/"test-only-502-build-1"
    candidate_full=dest/"VF-Start-V2.47.502-FULL.zip"
    repair_dest=work/"candidate-repair"
    safe_unpack(dest/"VF_Start_V2.47.502_UPDATE.zip",repair_dest)
    repair=repair_dest/"repair-v2.47.502.php"
    test=run("php",str(repair),"--self-test")
    require(json.loads(test.stdout).get("ok") is True,"atomic self-test missing")
    print("P01_502_ATOMIC_MANIFEST_SELF_TEST=PASS",flush=True)

    fresh=work/"fresh-502"
    safe_unpack(candidate_full,fresh)
    http_install(fresh)
    installed(fresh,"2.47.502")
    print("P01_502_CLEAN_FULL_REAL_HTTP_SETUP_AND_SQLITE_VERIFY=PASS",flush=True)

    success=work/"upgrade-501"
    safe_unpack(old_full,success)
    http_install(success)
    item=sentinel(success,"preserve success 501 to 502")
    test=run("php",str(repair),"--verify-source="+str(success),timeout=50)
    require(json.loads(test.stdout).get("ok") is True,"official 501 source not accepted")
    r=run("php",str(repair),"--run="+str(success),cwd=success,timeout=180)
    j=json.loads(r.stdout)
    require(j.get("ok") is True and j.get("already_current") is False,
            "501 to 502 Atomic apply failed")
    installed(success,"2.47.502")
    check_sentinel(success,item,"preserve success 501 to 502")
    r=run("php",str(repair),"--run="+str(success),cwd=success)
    require(json.loads(r.stdout).get("already_current") is True,
            "Atomic idempotent retry changed database")
    check_sentinel(success,item,"preserve success 501 to 502")
    print("P01_502_OFFICIAL_501_TO_502_ATOMIC_DATA_PRESERVED_IDEMPOTENT=PASS",flush=True)

    revert=work/"rollback-501"
    safe_unpack(old_full,revert)
    http_install(revert)
    item=sentinel(revert,"preserve injected rollback")
    env=os.environ.copy()
    env["VF_ATOMIC_TEST_FAIL_AFTER_APPLY"]="1"
    failure=run("php",str(repair),"--run="+str(revert),cwd=revert,env=env,
                success=False,timeout=180)
    require(failure.returncode!=0,"injected Atomic failure unexpectedly succeeded")
    installed(revert,"2.47.501")
    check_sentinel(revert,item,"preserve injected rollback")
    print("P01_502_INJECTED_FAILURE_501_ROLLBACK_DATA_PRESERVED=PASS",flush=True)

    interrupted=work/"hard-interrupted-501"
    safe_unpack(old_full,interrupted)
    http_install(interrupted)
    item=sentinel(interrupted,"preserve hard recovery")
    env=os.environ.copy()
    env["VF_ATOMIC_TEST_HARD_EXIT_AFTER_APPLY"]="1"
    crash=run("php",str(repair),"--run="+str(interrupted),cwd=interrupted,
              env=env,success=False,timeout=180)
    require(crash.returncode!=0,"hard-exit test unexpectedly succeeded")
    restored=run("php",str(repair),"--run="+str(interrupted),
                 cwd=interrupted,timeout=180)
    data=json.loads(restored.stdout)
    require(data.get("ok") is True and
            data.get("interrupted_recovered") is True,
            "hard exit not recovered using original 501 snapshot")
    installed(interrupted,"2.47.502")
    check_sentinel(interrupted,item,"preserve hard recovery")
    print("P01_502_HARD_INTERRUPT_RECOVERY_AND_REAPPLY=PASS",flush=True)
    print("P01_502_PRODUCTION_WRITE=NONE",flush=True)
    print("P01_502_FORMAL_RELEASE_CREATED=NO",flush=True)
    print("P01_502_EXACT_CANDIDATE_TEST_ONLY_BUILD=PASS",flush=True)

if __name__=="__main__":
    main()
