#!/usr/bin/env python3
"""P08 R180: one-shot official v0.1.8 CLEAN FULL only. No Atomic/channel/Production writes."""
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
SOURCE="76511f1b0263abf4de34dbfafd87b918eb60e209"
GOV_SHA="a1d783e31e6e22b037f0d9140a8046f25da210fc"
SOURCE_TREE="e48809e49dbee28aff58e2a50598ddf2ca932432"
EXPECTED_CHANNEL_BLOB="c3ec384fcba3f3305bfe10f7f757d82f9b4927d2"
TAG="v0.1.8"
FULL="VF_AdOps_V0.1.8_FULL.zip"
ASSETS=(FULL,"RELEASE_PROVENANCE.json","RELEASE_NOTES.md","SHA256SUMS")

def stop(code):
    raise RuntimeError("P08_R180_"+code)

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
    check(os.environ.get("GITHUB_ACTIONS")=="true" and os.environ.get("P08_R180_ISOLATED")=="YES",
          "ISOLATED_CI_ONLY")
    check(os.getuid()!=0 and len(os.environ.get("GH_TOKEN",""))>=20,
          "NONROOT_WRITER_TOKEN_REQUIRED")
    root=Path(os.environ["RUNNER_TEMP"])/"p08-r180-final"
    check(root.is_dir() and not root.is_symlink(),"ARTIFACT_ROOT_NOT_READY")
    check(api("repos/"+PRODUCT+"/git/ref/heads/main")["object"]["sha"]==SOURCE,"SOURCE_MOVED")
    check(api("repos/"+GOV_REPO+"/git/ref/heads/main")["object"]["sha"]==GOV_SHA,"GOVERNANCE_MOVED")
    channel=api("repos/"+UPDATES+"/contents/projects/P08-ADOPS.json?ref=main")
    check(channel["sha"]==EXPECTED_CHANNEL_BLOB,"OLD_ATOMIC_CHANNEL_MOVED")
    check(api("repos/"+PRODUCT+"/releases/tags/v0.1.7")["id"]==449685536,
          "IMMUTABLE_PREVIOUS_RELEASE_MOVED")
    absent("repos/"+PRODUCT+"/git/ref/tags/"+TAG)
    absent("repos/"+PRODUCT+"/releases/tags/"+TAG)
    for name in ASSETS:
        file=root/name
        check(file.is_file() and not file.is_symlink() and file.stat().st_size>0,"RELEASE_ASSET_MISSING")
    provenance=json.loads((root/"RELEASE_PROVENANCE.json").read_text())
    check(provenance.get("product")=="P08" and provenance.get("repository")==PRODUCT
        and provenance.get("target_version")=="0.1.8"
        and provenance.get("target_sha")==SOURCE
        and provenance.get("tree_sha")==SOURCE_TREE
        and provenance.get("governance_sha")==GOV_SHA
        and provenance.get("asset_role")=="CLEAN_FULL_ONLY"
        and provenance.get("data_included") is False
        and provenance.get("atomic_017_to_018_issued") is False
        and provenance.get("full_sha256")==sha(root/FULL),
        "PROVENANCE_SOURCE_OR_ROLE_MISMATCH")
    index=(root/"SHA256SUMS").read_text().splitlines()
    check(len(index)==3 and set(index)=={
        sha(root/n)+"  "+n for n in (FULL,"RELEASE_PROVENANCE.json","RELEASE_NOTES.md")
    },"CHECKSUMS_MISMATCH")
    with zipfile.ZipFile(root/FULL) as z:
        m=json.loads(z.read("FULL_MANIFEST.json"))
        check(m.get("source_sha")==SOURCE and m.get("target_version")=="0.1.8"
              and m.get("type")=="CLEAN_FULL_ONLY" and m.get("update_type")=="NOT_ATOMIC"
              and m.get("data_included") is False,"FULL_MANIFEST_UNTRUSTED")
        check(b"0.1.8" in z.read("VERSION")
              and len(m["files"])>6100 and z.testzip() is None,
              "FULL_ZIP_CORRUPT")
    # Do not attempt publication until source, identity, canonical channel, and
    # actual assembled asset checks pass. No Power to change Production.
    cmd("gh","release","create",TAG,
        *(str(root/n) for n in ASSETS),
        "-R",PRODUCT,"--target",SOURCE,
        "--title","VF AdOps v0.1.8 — Domain-portable Clean FULL installer",
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
    check(api("repos/"+PRODUCT+"/releases/tags/v0.1.7")["id"]==449685536,
          "OLD_RELEASE_CHANGED")
    print("P08_R180_OFFICIAL_FULL_ONLY_RELEASE_EXACT_TAG_REMOTE_ID_SHA=PASS")
    print("P08_R180_RELEASE_ID="+str(released["id"]))
    print("P08_R180_OFFICIAL_FULL_ASSET_ID="+str(assets[FULL]["id"]))
    print("P08_R180_OFFICIAL_FULL_BYTES="+str((root/FULL).stat().st_size))
    print("P08_R180_OFFICIAL_FULL_SHA256="+sha(root/FULL))
    print("P08_R180_OFFICIAL_ATOMIC_017_TO_018=NOT_ISSUED")
    print("P08_R180_OLD_V017_RELEASE_AND_ATOMIC_CHANNEL=UNCHANGED")
    print("P08_R180_PRODUCTION_CLOUDPANEL_DNS=UNTOUCHED")

if __name__=="__main__":
    try:
        main()
    except (RuntimeError,KeyError,TypeError,ValueError,OSError,zipfile.BadZipFile,
            subprocess.TimeoutExpired,IndexError) as e:
        print("P08_R180_ISSUANCE_STOP="+str(e).splitlines()[0][:140],file=sys.stderr)
        sys.exit(1)
