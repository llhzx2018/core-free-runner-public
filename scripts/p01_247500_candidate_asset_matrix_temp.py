#!/usr/bin/env python3
"""Unpublished exact P01 2.47.500 FULL/Atomic ZIP verification on synthetic installs."""
from __future__ import annotations
import argparse, base64, hashlib, importlib.util, json, os
from pathlib import Path
import re, shutil, zipfile
from collections.abc import Mapping

SCRIPT_DIR=Path(__file__).resolve().parent
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    assert spec and spec.loader
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
t=load(SCRIPT_DIR/"p01_247500_candidate_synthetic_helpers_temp.py","p01_verified_disposable_helpers")
m=load(SCRIPT_DIR/"p01-maintenance-release.py","p01_candidate_bundler_helpers")
TARGET="2.47.500"
SOURCE="2.47.499"
def require(ok,what):
    if not ok: raise AssertionError(what)
def digest(b):return hashlib.sha256(b).hexdigest()
def read_asset(path, expected):
    blob=path.read_bytes()
    require(digest(blob)==expected,"asset digest mismatch: "+path.name)
    return blob
def parse_private(text,name):
    key=re.search("private const "+name+r"='([^']+)';",text)
    require(bool(key),name+" missing")
    return json.loads(base64.b64decode(key.group(1)))
def main():
    ap=argparse.ArgumentParser()
    for key in ("work","source-full","source-update","candidate-full","candidate-update","candidate-receipt","source-commit","source-tree"):
        ap.add_argument("--"+key,required=True)
    args=ap.parse_args()
    work=Path(args.work).resolve()
    sf,su,cf,cu,cr=map(lambda x:Path(x).resolve(),(args.source_full,args.source_update,args.candidate_full,args.candidate_update,args.candidate_receipt))
    receipt=json.loads(cr.read_text())
    require(receipt["source_version"]==SOURCE and receipt["version"]==TARGET,"single-source release direction")
    require(receipt["target_sha"]==args.source_commit and receipt["target_tree"]==args.source_tree,"exact product identity")
    require(receipt["mode"]=="updater-safety-fix-candidate","never mark preview bundle as formal")
    require(cf.name=="VF-Start-V2.47.500-FULL.zip" and cu.name=="VF_Start_V2.47.500_UPDATE.zip","asset names")
    require(cf.stat().st_size==receipt["full_bytes"] and cu.stat().st_size==receipt["update_bytes"],"byte counts")
    read_asset(cf,receipt["full_sha256"]);read_asset(cu,receipt["update_sha256"])
    print("P01_247500_PRE_RELEASE_ASSET_SHA_AND_BYTES=PASS",flush=True)
    source=work/"official-499"
    target=work/"candidate-500"
    source_update=work/"official-499-update"
    candidate_update=work/"candidate-500-update"
    for archive,folder in ((sf,source),(su,source_update),(cf,target),(cu,candidate_update)):
        t.unpack_bundle(archive,folder)
    full_manifest=json.loads((target/"release-manifest.json").read_text())
    require(full_manifest["version"]==TARGET and full_manifest["source_version"]==SOURCE,"FULL release identity")
    require(full_manifest["stage"]=="PRE_RELEASE_CANDIDATE_NOT_PUBLISHED","must remain candidate")
    update=full_manifest["update"]
    require(update["from_versions"]==[SOURCE] and update["target_version"]==TARGET
            and update["asset_name"]==cu.name and update["backup_required"] is True
            and update["rollback_supported"] is True,
            "from_versions must be exactly [2.47.499] with safe Atomic")
    for rel,sha in full_manifest["runtime_files"].items():
        require((target/rel).is_file() and digest((target/rel).read_bytes())==sha,"FULL runtime bytes mismatch: "+rel)
    require(full_manifest["source_commit"]==args.source_commit and full_manifest["source_tree"]==args.source_tree,"FULL source hash mismatch")
    disallowed={"private","private_data","backups","sessions","tokens","staging"}
    for rel in full_manifest["runtime_files"]:
        require(not disallowed.intersection(Path(rel).parts),"private file in FULL manifest")
        require(not rel.endswith((".sqlite",".sqlite3",".db",".log",".env")),"data file in FULL manifest")
    print("P01_247500_CANDIDATE_FULL_MANIFEST_AND_SINGLE_SOURCE=PASS",flush=True)

    # Compare bytes of official 499 source FULL against official 499 Atomic target.
    prior=(source_update/f"repair-v{SOURCE}.php")
    baseline=t.source_manifest(prior,source)
    repairfiles=list(candidate_update.glob("*"))
    require(len(repairfiles)==1 and repairfiles[0].name==f"repair-v{TARGET}.php","single file Atomic ZIP")
    repair=repairfiles[0]
    data=repair.read_text()
    require(re.search(r"public const SOURCE_VERSION='"+re.escape(SOURCE)+"'",data),"Atomic source ID")
    require(re.search(r"public const TARGET_VERSION='"+re.escape(TARGET)+"'",data),"Atomic target ID")
    source_hashes=parse_private(data,"SOURCE_MANIFEST")
    target_hashes=parse_private(data,"TARGET_MANIFEST")
    require(source_hashes=={k:digest(v) for k,v in baseline.items()},"source SHA inventory official exact")
    require(target_hashes=={k:digest((target/k).read_bytes()) for k in target_hashes},"target FULL bytes don't equal Atomic payload")
    result=t.run("php",str(repair),"--self-test")
    require(json.loads(result.stdout)["ok"] is True,"real candidate repair self-test")
    assert "maintenanceLease" in data and "recoverInterrupted" in data
    print("P01_247500_EXACT_OFFICIAL499_TO_CANDIDATE500_ATOMIC_MANIFEST=PASS",flush=True)

    # Browser first request / setup / CLI health using the candidate FULL archive.
    clean=work/"clean-full-install"
    shutil.copytree(target,clean)
    t.synthetic_setup(clean,18910)
    require((clean/"VERSION.txt").read_text().strip()==TARGET,"first install version")
    print("P01_247500_CANDIDATE_FULL_FIRST_RUN_AND_ADMIN_SETUP=PASS",flush=True)

    # Site created from immutable official prior FULL, then tested as an existing
    # owner environment. A private SQLite resource is the non-loss sentinel.
    site=work/"atomic-success"
    shutil.copytree(source,site)
    t.synthetic_setup(site,18911)
    sid=t.sentinel(site,"Official 499 owner private success")
    valid=json.loads(t.run("php",str(repair),"--verify-source="+str(site)).stdout)
    require(valid["ok"] is True,"unmodified official source not accepted")
    installed=json.loads(t.run("php",str(repair),"--run="+str(site),cwd=site,timeout=150).stdout)
    require(installed["ok"] is True and not installed.get("already_current",False),"not upgraded")
    require((site/"VERSION.txt").read_text().strip()==TARGET,"target version not installed")
    t.check_sentinel(site,sid,"Official 499 owner private success")
    t.run("php",str(site/"cli/verify.php"),cwd=site)
    repeated=json.loads(t.run("php",str(repair),"--run="+str(site),cwd=site).stdout)
    require(repeated["ok"] is True and repeated.get("already_current",False),"Atomic not idempotent")
    print("P01_247500_OFFICIAL499_UPGRADE_PRIVATE_SENTINEL_AND_IDEMPOTENCY=PASS",flush=True)

    # Fault after source apply -> restore old source/config/db in isolation.
    rollback=work/"atomic-rollback"
    shutil.copytree(source,rollback)
    t.synthetic_setup(rollback,18912)
    rid=t.sentinel(rollback,"Official 499 owner private rollback")
    env=os.environ.copy();env["VF_ATOMIC_TEST_FAIL_AFTER_APPLY"]="1"
    failed=t.run("php",str(repair),"--run="+str(rollback),cwd=rollback,env=env,expect=None,timeout=150)
    require(failed.returncode!=0,"failure-injection path did not fail")
    require((rollback/"VERSION.txt").read_text().strip()==SOURCE,"rollback failed to restore old version")
    t.check_sentinel(rollback,rid,"Official 499 owner private rollback")
    t.run("php",str(rollback/"cli/verify.php"),cwd=rollback)
    print("P01_247500_OFFICIAL499_INJECTED_ROLLBACK=PASS",flush=True)

    # Hard PHP process exit occurs after file apply; next operation must
    # detect and recover transaction, then correctly apply update.
    interrupted=work/"atomic-hard-interrupt"
    shutil.copytree(source,interrupted)
    t.synthetic_setup(interrupted,18913)
    iid=t.sentinel(interrupted,"Official 499 owner private hard interrupt")
    env=os.environ.copy();env["VF_ATOMIC_TEST_HARD_EXIT_AFTER_APPLY"]="1"
    hard=t.run("php",str(repair),"--run="+str(interrupted),cwd=interrupted,env=env,expect=None,timeout=150)
    require(hard.returncode!=0,"hard exit injection not reached")
    retry=json.loads(t.run("php",str(repair),"--run="+str(interrupted),cwd=interrupted,timeout=150).stdout)
    require(retry["ok"] is True,"post hard-exit recovery+reapply failed")
    require((interrupted/"VERSION.txt").read_text().strip()==TARGET,"after recovery version mismatch")
    t.check_sentinel(interrupted,iid,"Official 499 owner private hard interrupt")
    t.run("php",str(interrupted/"cli/verify.php"),cwd=interrupted)
    print("P01_247500_OFFICIAL499_HARD_INTERRUPT_RECOVERY=PASS",flush=True)
    print("P01_247500_RELEASE_AND_DISTRIBUTION=NOT_EXECUTED",flush=True)
    print("P01_247500_PRODUCTION=UNCHANGED",flush=True)
if __name__=="__main__":main()
