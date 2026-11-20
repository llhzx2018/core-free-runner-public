#!/usr/bin/env python3
"""ONE-SHOT formal P08 v0.1.13 GitHub Release. NO core-updates/Production write.

Owner-authorized Mode U only. This script acts solely in a disposable
same-repo GitHub Actions job after all final 3DB & old-PHP machine gates pass.
It NEVER replaces past tags, releases, assets or changes an Owner installation.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

PRODUCT="llhzx2018/vf-adops"
GOV="llhzx2018/gov-doc"
CHANNEL="llhzx2018/core-updates"
TARGET="8b385fecd132a02ac79f5b67e670783e98997c3e"
TREE="32b8722fbfaff3e988e69693510be0c1e6df8bba"
GOV_SHA="74c4090c93cea7ef6a55c7b17d39515e7ca8710c"
OLD="dac7bc1d5410c077f32e522eb5740537f618ef9d"
OLD_MANIFEST="607b3a02a20021c0747d42440497b7e9e3e0fe39040869f475ba22f9f19437e9"
OLD_CHANNEL_BLOB="a61e3e9dc2fb27c0ebd467d21634fc07fa0963ec"
FULL_SHA="f8075f065d1413c984f80ef7531242cfc894bf272e90f6d89282074f6617c1ec"
UPDATE_SHA="6982a7b44873ac825e6c252b309d8f11a9ade67e67f5b8b6467538a46ef71b2a"
TAG="v0.1.13"
FULL="VF_AdOps_V0.1.13_FULL.zip"
UPDATE="VF_AdOps_V0.1.13_UPDATE.zip"
ASSETS=(FULL,UPDATE,"RELEASE_PROVENANCE.json","RELEASE_NOTES.md","SHA256SUMS")
RUN_ID=44666251399
RUN_HEAD="22b795261fe496f32ce6d653f21e98532d19ce9f"
RUN_JOBS={136056159352,136056159745,136056159813}
PREV_ASSETS={"VF_AdOps_V0.1.12_UPDATE.zip":766931637,
             "VF_AdOps_V0.1.12_FULL.zip":766931640}

def stop(code:str):
    raise RuntimeError("P08_V013_"+code)
def require(ok:bool,code:str):
    if not ok:stop(code)
def cmd(*args:str)->str:
    try:
        p=subprocess.run(list(args),stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                         text=True,timeout=200,check=False)
    except (subprocess.TimeoutExpired,OSError):
        stop("PROCESS_TIMEOUT_OR_UNAVAILABLE")
    if p.returncode:
        # Never print token, remote JSON, private code or GitHub CLI stderr.
        stop("COMMAND_FAILED_"+str(args[0]).upper().replace("-","_"))
    return p.stdout.strip()
def api(path:str)->dict:
    try:
        obj=json.loads(cmd("gh","api",path))
    except (json.JSONDecodeError,ValueError):
        stop("REMOTE_JSON_INVALID")
    require(isinstance(obj,dict),"REMOTE_JSON_NOT_OBJECT")
    return obj
def sha(path:Path)->str:
    with path.open("rb") as f:
        return hashlib.file_digest(f,"sha256").hexdigest()
def absent(path:str):
    p=subprocess.run(["gh","api",path],capture_output=True,text=True,timeout=30,check=False)
    require(p.returncode!=0 and ("404" in p.stderr or "Not Found" in p.stderr),
            "PREEXISTING_TAG_OR_RELEASE_OR_ACCESS_FAILURE")

def main()->None:
    require(os.getenv("GITHUB_ACTIONS")=="true"
        and os.getenv("P08_V013_RELEASE_ONCE")=="YES"
        and os.geteuid()!=0 and len(os.getenv("GH_TOKEN",""))>=20,
        "NONROOT_OWNER_APPROVED_ACTION_ONLY")
    root=Path(os.environ["RUNNER_TEMP"])/"p08-v013-immutable-issue"
    require(root.is_dir() and not root.is_symlink(),"FINAL_ASSET_ROOT_INVALID")
    require(cmd("git","-C","target","rev-parse","HEAD")==TARGET
        and cmd("git","-C","target","rev-parse","HEAD^{tree}")==TREE
        and cmd("git","-C","gov","rev-parse","HEAD")==GOV_SHA
        and Path("target/VERSION").read_text().strip()=="0.1.13",
        "SOURCE_OR_GOVERNANCE_NOT_FINAL")
    require(not cmd("git","-C","target","status","--porcelain","--untracked-files=all"),
        "SOURCE_WORKTREE_DIRTY")
    require(api("repos/"+PRODUCT+"/git/ref/heads/main")["object"]["sha"]==TARGET
        and api("repos/"+GOV+"/git/ref/heads/main")["object"]["sha"]==GOV_SHA,
        "MAIN_SOURCE_OR_GOVERNANCE_MOVED")
    require(api("repos/"+CHANNEL+"/contents/projects/P08-ADOPS.json?ref=main")["sha"]
        ==OLD_CHANNEL_BLOB,"OFFICIAL_V012_CHANNEL_MOVED")
    previous=api("repos/"+PRODUCT+"/releases/tags/v0.1.12")
    require(previous.get("tag_name")=="v0.1.12"
        and previous.get("draft") is False and previous.get("prerelease") is False,
        "OFFICIAL_PREVIOUS_RELEASE_NOT_VALID")
    old_assets={a.get("name"):a.get("id") for a in previous.get("assets",[])}
    require(all(old_assets.get(n)==v for n,v in PREV_ASSETS.items()),
        "HISTORICAL_V012_ASSET_CHANGED")
    ref=api("repos/"+PRODUCT+"/git/ref/tags/v0.1.12")
    require(ref.get("object",{}).get("sha")==OLD,"HISTORICAL_V012_TAG_CHANGED")

    # Job result is not inferred from repo writes or fabricated logs.
    run=api("repos/llhzx2018/core-free-runner-public/actions/runs/"+str(RUN_ID))
    require(run.get("head_sha")==RUN_HEAD and run.get("conclusion")=="success",
            "FINAL_MAIN_THREE_NATIVE_ENGINES_NOT_PROVEN")
    jobs=api("repos/llhzx2018/core-free-runner-public/actions/runs/"+str(RUN_ID)+"/jobs?per_page=100")
    actual={j.get("id") for j in jobs.get("jobs",[]) if j.get("conclusion")=="success"}
    require(RUN_JOBS<=actual,"FINAL_MAIN_THREE_DB_JOBS_NOT_SUCCESS")
    absent("repos/"+PRODUCT+"/git/ref/tags/"+TAG)
    absent("repos/"+PRODUCT+"/releases/tags/"+TAG)

    for name in ASSETS:
        f=root/name
        require(f.is_file() and not f.is_symlink() and f.stat().st_size>0,
                "OFFICIAL_ASSET_MISSING")
    require(sha(root/FULL)==FULL_SHA and sha(root/UPDATE)==UPDATE_SHA,
            "FINAL_PACKAGE_SHA_NOT_MACHINE_PROVEN")
    provenance=json.loads((root/"RELEASE_PROVENANCE.json").read_text())
    require(provenance.get("project_id")=="P08"
        and provenance.get("repository")==PRODUCT
        and provenance.get("source_version")=="0.1.12"
        and provenance.get("source_sha")==OLD
        and provenance.get("source_full_manifest_sha256")==OLD_MANIFEST
        and provenance.get("target_version")=="0.1.13"
        and provenance.get("target_sha")==TARGET
        and provenance.get("target_tree_sha")==TREE
        and provenance.get("governance_sha")==GOV_SHA
        and provenance.get("full_sha256")==FULL_SHA
        and provenance.get("atomic_sha256")==UPDATE_SHA
        and provenance.get("schema_changes") is False
        and provenance.get("backup_required") is True
        and provenance.get("rollback_supported") is True
        and provenance.get("production_auto_apply") is False,
        "OFFICIAL_PROVENANCE_NOT_EXACT")
    sums=set((root/"SHA256SUMS").read_text().splitlines())
    require(sums=={sha(root/n)+"  "+n for n in ASSETS[:-1]},
            "SHA256SUMS_MISMATCH")
    with zipfile.ZipFile(root/FULL) as f:
        fm=json.loads(f.read("FULL_MANIFEST.json"))
        require(fm.get("source_sha")==TARGET
            and fm.get("target_version")=="0.1.13"
            and fm.get("type")=="CLEAN_FULL_ONLY"
            and fm.get("data_included") is False
            and len(fm.get("files",[]))>6100 and f.testzip() is None,
            "REAL_FINAL_FULL_MANIFEST_INVALID")
    with zipfile.ZipFile(root/UPDATE) as f:
        am=json.loads(f.read("ATOMIC_MANIFEST.json"))
        require(am.get("type")=="P08_ATOMIC_CODE_ONLY_V1"
            and am.get("source_sha")==OLD
            and am.get("source_version")=="0.1.12"
            and am.get("source_full_manifest_sha256")==OLD_MANIFEST
            and am.get("target_sha")==TARGET
            and am.get("target_version")=="0.1.13"
            and am.get("schema_changes") is False
            and len(am.get("files",[]))>6100
            and f.testzip() is None,"REAL_FINAL_607B_ATOMIC_INVALID")

    # Only AFTER all prepublication native & release checks: create once.
    cmd("gh","release","create",TAG,*(str(root/n) for n in ASSETS),
        "-R",PRODUCT,"--target",TARGET,
        "--title","VF AdOps v0.1.13 — Owner one-click Atomic update safety",
        "--notes-file",str(root/"RELEASE_NOTES.md"))
    issued=api("repos/"+PRODUCT+"/releases/tags/"+TAG)
    require(issued.get("tag_name")==TAG and issued.get("draft") is False
        and issued.get("prerelease") is False and issued.get("id",0)>0
        and api("repos/"+PRODUCT+"/git/ref/tags/"+TAG)["object"]["sha"]==TARGET,
        "REMOTE_RELEASE_OR_TAG_IDENTITY_FAIL")
    assets={a.get("name"):a for a in issued.get("assets",[])}
    require(set(assets)==set(ASSETS),"REMOTE_ASSET_LIST_MISMATCH")
    for name in ASSETS:
        a=assets[name]
        require(isinstance(a.get("id"),int) and a["id"]>0
                and a.get("size")==(root/name).stat().st_size,
                "REMOTE_ASSET_ID_OR_SIZE_CHANGED")
        digest=a.get("digest")
        require(digest is None or digest=="sha256:"+sha(root/name),
                "REMOTE_ASSET_API_DIGEST_MISMATCH")
    dest=root/"remote"
    dest.mkdir(mode=0o700)
    cmd("gh","release","download",TAG,"-R",PRODUCT,"-D",str(dest))
    require({p.name for p in dest.iterdir()}==set(ASSETS),
            "REMOTE_DOWNLOAD_ASSET_SET_WRONG")
    for name in ASSETS:
        require(sha(dest/name)==sha(root/name)
                and (dest/name).stat().st_size==(root/name).stat().st_size,
                "REMOTE_ASSET_SHA_OR_BYTES_DIFFERENT")
    require(api("repos/"+CHANNEL+"/contents/projects/P08-ADOPS.json?ref=main")["sha"]
            ==OLD_CHANNEL_BLOB,"CHANNEL_PREMATURELY_MODIFIED")
    after=api("repos/"+PRODUCT+"/releases/tags/v0.1.12")
    require(after.get("id")==previous.get("id")
        and all({a.get("name"):a.get("id") for a in after.get("assets",[])}.get(n)==v
                for n,v in PREV_ASSETS.items()),"HISTORICAL_V012_IMMUTABILITY_FAILED")

    print("P08_V013_OFFICIAL_TAG_RELEASE_REMOTE_BYTES=PASS")
    print("P08_V013_FINAL_RELEASE_SHA="+TARGET)
    print("P08_V013_RELEASE_ID="+str(issued["id"]))
    print("P08_V013_FULL_ASSET_ID="+str(assets[FULL]["id"]))
    print("P08_V013_FULL_BYTES="+str((root/FULL).stat().st_size))
    print("P08_V013_FULL_SHA256="+FULL_SHA)
    print("P08_V013_UPDATE_ASSET_ID="+str(assets[UPDATE]["id"]))
    print("P08_V013_UPDATE_BYTES="+str((root/UPDATE).stat().st_size))
    print("P08_V013_UPDATE_SHA256="+UPDATE_SHA)
    print("P08_V013_OLD_V012_RELEASE_ASSETS_UNCHANGED=PASS")
    print("P08_V013_CORE_UPDATES_CHANNEL=UNCHANGED_PENDING_SEPARATE_VERIFICATION")
    print("P08_V013_OWNER_PRODUCTION_CLOUDPANEL_DNS=UNTOUCHED")

if __name__=="__main__":
    try:
        main()
    except (RuntimeError,KeyError,TypeError,ValueError,OSError,zipfile.BadZipFile,
            json.JSONDecodeError,IndexError) as e:
        code=str(e)
        if not code.startswith("P08_V013_"):code="P08_V013_INTERNAL_CHECK_FAILED"
        print("P08_V013_OFFICIAL_ISSUANCE_STOP="+code[:110],file=sys.stderr)
        sys.exit(1)
