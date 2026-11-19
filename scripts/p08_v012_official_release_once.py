#!/usr/bin/env python3
"""P08 R210: exact P08 v0.1.12 genuine legacy v010 Atomic lineage; no channel or Production writes."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

PRODUCT="llhzx2018/vf-adops"
GOV_REPO="llhzx2018/gov-doc"
UPDATES="llhzx2018/core-updates"
SOURCE="dac7bc1d5410c077f32e522eb5740537f618ef9d"
GOV_SHA="883c92ce1a987b5f6e5729b7b73fd098ffaf14ae"
SOURCE_TREE="154c43365b84a85150c6af89770e2116275667c4"
EXPECTED_CHANNEL_BLOB="368cc70658048bfe160d498b01f6a585fa0f15a5"
TAG="v0.1.12"
FULL="VF_AdOps_V0.1.12_FULL.zip"
UPDATE="VF_AdOps_V0.1.12_UPDATE.zip"
PREVIOUS_SOURCE="ef78dcb21117c822e2756360280f2418f794704f"
PREVIOUS_FULL_MANIFEST_SHA="efebfefde3115864dba71c2e56fedae2f7ada8ad4064010473d716b689f67fe9"
ASSETS=(FULL,UPDATE,"RELEASE_PROVENANCE.json","RELEASE_NOTES.md","SHA256SUMS")

def stop(code):
    raise RuntimeError("P08_R210_"+code)

def check(condition, code):
    if not condition: stop(code)

def cmd(*args):
    p=subprocess.run(list(args),capture_output=True,text=True,check=False,timeout=150)
    if p.returncode:
        # Never echo private API replies, token, or a release POST payload.
        stop("CMD_FAILED_"+args[0].upper().replace("-","_"))
    return p.stdout.strip()

def api(route):
    return json.loads(cmd("gh","api",route))

def sha(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file,"sha256").hexdigest()

def absent(route):
    p=subprocess.run(["gh","api",route],capture_output=True,text=True,check=False,timeout=30)
    # Refuse both pre-existing identity and infrastructure/auth/other errors.
    check(p.returncode!=0 and ("404" in p.stderr or "Not Found" in p.stderr),
          "TAG_OR_RELEASE_EXISTS_OR_CANNOT_CHECK")

def main():
    check(os.environ.get("GITHUB_ACTIONS")=="true" and os.environ.get("P08_R210_ISOLATED")=="YES",
          "ISOLATED_CI_ONLY")
    check(os.getuid()!=0 and len(os.environ.get("GH_TOKEN",""))>=20,
          "NONROOT_WRITER_TOKEN_REQUIRED")
    root=Path(os.environ["RUNNER_TEMP"])/"p08-r210-final"
    check(root.is_dir() and not root.is_symlink(),"ARTIFACT_ROOT_NOT_READY")
    check(api("repos/"+PRODUCT+"/git/ref/heads/main")["object"]["sha"]==SOURCE,"SOURCE_MOVED")
    check(api("repos/"+GOV_REPO+"/git/ref/heads/main")["object"]["sha"]==GOV_SHA,"GOVERNANCE_MOVED")
    channel=api("repos/"+UPDATES+"/contents/projects/P08-ADOPS.json?ref=main")
    check(channel["sha"]==EXPECTED_CHANNEL_BLOB,"V011_ATOMIC_CHANNEL_MOVED")
    check(api("repos/"+PRODUCT+"/releases/tags/v0.1.10")["id"]==450188625,
          "IMMUTABLE_V010_RELEASE_MOVED")
    check(api("repos/"+PRODUCT+"/releases/tags/v0.1.11")["id"]==450980192,
          "IMMUTABLE_PREVIOUS_RELEASE_MOVED")
    absent("repos/"+PRODUCT+"/git/ref/tags/"+TAG)
    absent("repos/"+PRODUCT+"/releases/tags/"+TAG)
    for name in ASSETS:
        file=root/name
        check(file.is_file() and not file.is_symlink() and file.stat().st_size>0,"RELEASE_ASSET_MISSING")
    provenance=json.loads((root/"RELEASE_PROVENANCE.json").read_text())
    check(provenance.get("product")=="P08" and provenance.get("repository")==PRODUCT
        and provenance.get("target_version")=="0.1.12"
        and provenance.get("target_sha")==SOURCE
        and provenance.get("tree_sha")==SOURCE_TREE
        and provenance.get("governance_sha")==GOV_SHA
        and provenance.get("asset_role")=="CLEAN_FULL_AND_ATOMIC_010_LEGACY_TO_012"
        and provenance.get("source_version")=="0.1.10"
        and provenance.get("source_sha")==PREVIOUS_SOURCE
        and provenance.get("source_full_manifest_sha256")==PREVIOUS_FULL_MANIFEST_SHA
        and provenance.get("schema_changes") is False
        and provenance.get("data_included") is False
        and provenance.get("production_auto_apply") is False
        and provenance.get("release_mode")=="ONE_CASE_P08_012_ATOMIC_LINEAGE_POST_RELEASE_OWNER_MANUAL"
        and provenance.get("full_sha256")==sha(root/FULL)
        and provenance.get("atomic_sha256")==sha(root/UPDATE),
        "PROVENANCE_SOURCE_OR_ROLE_MISMATCH")
    index=(root/"SHA256SUMS").read_text().splitlines()
    check(len(index)==4 and set(index)=={
        sha(root/n)+"  "+n for n in (FULL,UPDATE,"RELEASE_PROVENANCE.json","RELEASE_NOTES.md")
    },"CHECKSUMS_MISMATCH")
    with zipfile.ZipFile(root/FULL) as z:
        m=json.loads(z.read("FULL_MANIFEST.json"))
        check(m.get("source_sha")==SOURCE and m.get("target_version")=="0.1.12"
              and m.get("type")=="CLEAN_FULL_ONLY" and m.get("update_type")=="NOT_ATOMIC"
              and m.get("data_included") is False,"FULL_MANIFEST_UNTRUSTED")
        check(b"0.1.12" in z.read("VERSION")
              and len(m["files"])>6100 and z.testzip() is None,
              "FULL_ZIP_CORRUPT")
    with zipfile.ZipFile(root/UPDATE) as z:
        atomic=json.loads(z.read("ATOMIC_MANIFEST.json"))
        check(atomic.get("type")=="P08_ATOMIC_CODE_ONLY_V1"
            and atomic.get("source_version")=="0.1.10"
            and atomic.get("target_version")=="0.1.12"
            and atomic.get("source_sha")==PREVIOUS_SOURCE
            and atomic.get("source_full_manifest_sha256")==PREVIOUS_FULL_MANIFEST_SHA
            and atomic.get("target_sha")==SOURCE
            and atomic.get("schema_changes") is False
            and len(atomic.get("files",[]))>6100
            and z.testzip() is None,"ATOMIC_MANIFEST_OR_SCHEMA_UNTRUSTED")
    # Do not attempt publication until source, identity, canonical channel, and
    # actual assembled asset checks pass. No Power to change Production.
    cmd("gh","release","create",TAG,
        *(str(root/n) for n in ASSETS),
        "-R",PRODUCT,"--target",SOURCE,
        "--title","VF AdOps v0.1.12 — Verified continuous Atomic lineage repair",
        "--notes-file",str(root/"RELEASE_NOTES.md"))
    released=api("repos/"+PRODUCT+"/releases/tags/"+TAG)
    check(released.get("tag_name")==TAG and released.get("draft") is False
          and released.get("prerelease") is False and released.get("id",0)>0
          and api("repos/"+PRODUCT+"/git/ref/tags/"+TAG)["object"]["sha"]==SOURCE,
          "OFFICIAL_TAG_IDENTITY_MISMATCH")
    assets={a["name"]:a for a in released.get("assets",[])}
    check(set(assets)==set(ASSETS),"REMOTE_ASSET_SET_INVALID")
    for name in ASSETS:
        remote=assets[name]
        check(isinstance(remote.get("id"),int) and remote["id"]>0
              and remote.get("size")== (root/name).stat().st_size,
              "OFFICIAL_REMOTE_METADATA_MISMATCH")
    dest=root/"remote"
    dest.mkdir(mode=0o700)
    cmd("gh","release","download",TAG,"-R",PRODUCT,"-D",str(dest))
    check({p.name for p in dest.iterdir()}==set(ASSETS),"REMOTE_ASSET_NAMES_CHANGED")
    for name in ASSETS:
        check(sha(dest/name)==sha(root/name)
              and (dest/name).stat().st_size==(root/name).stat().st_size,
              "REMOTE_ASSET_BYTES_CHANGED")
    check(api("repos/"+UPDATES+"/contents/projects/P08-ADOPS.json?ref=main")["sha"]==EXPECTED_CHANNEL_BLOB,
          "UNCHANGED_OLD_ATOMIC_CHANNEL_HAS_CHANGED")
    check(api("repos/"+PRODUCT+"/releases/tags/v0.1.10")["id"]==450188625
          and api("repos/"+PRODUCT+"/releases/tags/v0.1.11")["id"]==450980192,
          "OLD_RELEASE_CHANGED")
    print("P08_R210_OFFICIAL_FULL_AND_ATOMIC_RELEASE_EXACT_TAG_REMOTE_ID_SHA=PASS")
    print("P08_R210_RELEASE_ID="+str(released["id"]))
    print("P08_R210_OFFICIAL_FULL_ASSET_ID="+str(assets[FULL]["id"]))
    print("P08_R210_OFFICIAL_FULL_BYTES="+str((root/FULL).stat().st_size))
    print("P08_R210_OFFICIAL_FULL_SHA256="+sha(root/FULL))
    print("P08_R210_OFFICIAL_UPDATE_ASSET_ID="+str(assets[UPDATE]["id"]))
    print("P08_R210_OFFICIAL_UPDATE_BYTES="+str((root/UPDATE).stat().st_size))
    print("P08_R210_OFFICIAL_UPDATE_SHA256="+sha(root/UPDATE))
    print("P08_R210_OFFICIAL_ATOMIC_010_LEGACY_TO_012=ISSUED_VERIFIED")
    print("P08_R210_OLD_V010_AND_V011_RELEASE_AND_CHANNEL=UNCHANGED_UNTIL_APPROVED_ATOMIC_CHANNEL_COMMIT")
    print("P08_R210_PRODUCTION_CLOUDPANEL_DNS=UNTOUCHED")

if __name__=="__main__":
    try:
        main()
    except (RuntimeError,KeyError,TypeError,ValueError,OSError,zipfile.BadZipFile,
            subprocess.TimeoutExpired,IndexError) as e:
        print("P08_R210_ISSUANCE_STOP="+str(e).splitlines()[0][:140],file=sys.stderr)
        sys.exit(1)
