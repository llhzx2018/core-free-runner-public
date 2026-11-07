#!/usr/bin/env python3
"""Owner-approved P01 v501: isolated installed v500 end-to-end real GitHub online discovery.
All files and SQLite are synthetic in disposable Public Runner. No Production traffic/writes.
Token is injected in the child PHP process only, never printed or copied into Public Artifact.
"""
from __future__ import annotations
import argparse
import importlib.util
import os
from pathlib import Path
import subprocess

def must(x,s):
    if not x:raise AssertionError(s)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source-full",required=True)
    p.add_argument("--work",required=True)
    a=p.parse_args()
    work=Path(a.work).resolve()
    spec=importlib.util.spec_from_file_location("synthetic",Path(__file__).with_name("p01-v247501-channel-live-synthetic-helper-temp.py"))
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    site=work/"actual-online-v500"
    helper.unpack_bundle(Path(a.source_full).resolve(),site)
    helper.synthetic_setup(site,18963)
    ident=helper.sentinel(site,"Public Runner real remote discovery synthetic private record")
    must((site/"VERSION.txt").read_text().strip()=="2.47.500","not official 500 installed")
    token=os.environ.get("VF_PRIVATE_READ_TOKEN","")
    must(len(token)>20,"read-only token capability unavailable")
    # Use PRODUCT INSTALLED 500 update manager, not a mocked adapter or preloaded JSON.
    # It makes an actual GitHub REST GET of core-updates/main/projects/P01.json,
    # retrieves the live official 501 Release asset via GitHubClient, verifies
    # the bytes & SHA, makes a synthetic backup and applies Atomic.
    php=(
        'require $argv[1]."/app/bootstrap.php";'
        'require_once $argv[1]."/app/UpdateManager.php";'
        '$m=new VfUpdateManager(vf_db(),["root"=>$argv[1],"private_root"=>VF_PRIVATE_ROOT,"current_version"=>"2.47.500"]);'
        '$check=$m->check(true);'
        'if(empty($check["ok"])||empty($check["available"])||empty($check["can_update"])'
        '||$check["current_version"]!=="2.47.500"||$check["latest_version"]!=="2.47.501")'
        '{fwrite(STDERR,"DISCOVERY_CHECK_FAILED\\n");exit(73);}'
        'echo "P01_V501_LIVE_GITHUB_CHANNEL_DISCOVERY_500_TO_501=PASS\\n";'
        '$prepared=$m->prepare();'
        'if(empty($prepared["ok"])||empty($prepared["operation_id"])'
        '||$prepared["to_version"]!=="2.47.501"'
        '||$prepared["update_package_sha256"]!=="658faa9c1e30b10ae7932f04a68f50a777e23a2115e0fd3d602c66ad64e02fa8"'
        '||$prepared["update_package_bytes"]!==3788274)'
        '{fwrite(STDERR,"PREPARE_CHECK_FAILED\\n");exit(74);}'
        'echo "P01_V501_REAL_RELEASE_DOWNLOAD_HASH_BACKUP_PREPARE=PASS\\n";'
        '$done=$m->install($prepared["operation_id"]);'
        'if(empty($done["ok"])||empty($done["updated"])'
        '||$done["from_version"]!=="2.47.500"||$done["to_version"]!=="2.47.501")'
        '{fwrite(STDERR,"ACTUAL_ONLINE_ATOMIC_FAILED\\n");exit(75);}'
        'echo "P01_V501_REAL_EXISTING_500_ONLINE_ATOMIC_INSTALL=PASS\\n";'
    )
    env=os.environ.copy()
    proc=subprocess.run(["php","-r",php,str(site)],cwd=site,env=env,
                        stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=160)
    if proc.returncode:
        print("P01_V501_LIVE_MANAGER_RESULT=FAIL:"+str(proc.returncode),flush=True)
        print("P01_V501_LIVE_MANAGER_PUBLIC_DIAGNOSTIC="+proc.stderr[-250:].replace(token,"[redacted]"),flush=True)
        raise SystemExit(40)
    for marker in ["P01_V501_LIVE_GITHUB_CHANNEL_DISCOVERY_500_TO_501=PASS",
                   "P01_V501_REAL_RELEASE_DOWNLOAD_HASH_BACKUP_PREPARE=PASS",
                   "P01_V501_REAL_EXISTING_500_ONLINE_ATOMIC_INSTALL=PASS"]:
        must(marker in proc.stdout,"missing manager proof "+marker)
        print(marker,flush=True)
    must((site/"VERSION.txt").read_text().strip()=="2.47.501","actual channel install did not install 501")
    verify=subprocess.run(["php",str(site/"cli/verify.php")],cwd=site,env=env,
                          stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=40)
    must(verify.returncode==0 and "VERIFY_PASS=YES" in verify.stdout,
         "post-online-update SQLite verification failed")
    helper.check_sentinel(site,ident,"Public Runner real remote discovery synthetic private record")
    print("P01_V501_REAL_GITHUB_ONLINE_500_TO_501_PRIVATE_DATA_PRESERVED=PASS",flush=True)
    print("P01_V501_PRODUCTION=UNCHANGED",flush=True)

if __name__=="__main__":main()
