#!/usr/bin/env python3
"""P08 R174: one-shot official v0.1.7 release + authenticated channel CAS.

Authorized only for exact P08 PR65 merged SHA and GOV-DOC Mode P. No
Production, no repair deployment, and no overwrite/reissue of old tags.
This is disposable proof-lane code, not product runtime or shared policy.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

PRODUCT="llhzx2018/vf-adops"
UPDATES="llhzx2018/core-updates"
TARGET="aad233c72213d2fcb3e2400ee1316bb7d8e9f071"
GOV="5bf99b73afc70a976ec6753ed5c71554b9f36a13"
BASE_MANIFEST="cda5fbe9523dbdb5d35d0a1ef5ea4e55e45d3ad19de1a82b259f7ed2edc1de46"
BASE_SHA="75fdcab08f84e5bb7e4edb1a3f42098096907598"
PREVIOUS_CHANNEL_BLOB="ebc65ffc38a59121eda6d70025cbae4ba6f1cddb"
TAG="v0.1.7"
FULL="VF_AdOps_V0.1.7_FULL.zip"
UPDATE="VF_AdOps_V0.1.7_UPDATE.zip"
RESCUE="P08_v0.1.7_Recovery_Once.php"
ARTIFACTS=[FULL,UPDATE,RESCUE,"RELEASE_PROVENANCE.json","SHA256SUMS"]

def fail(code):
    raise RuntimeError("P08_R174_"+code)

def cmd(*args):
    p=subprocess.run(args,capture_output=True,text=True,check=False)
    if p.returncode!=0:
        # Deliberately do not print stderr/credentials/raw API response.
        fail("COMMAND_STOP_"+args[0].upper().replace("-","_"))
    return p.stdout.strip()

def api(route):
    return json.loads(cmd("gh","api",route))

def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f,"sha256").hexdigest()

def check(cond,code):
    if not cond: fail(code)

def main():
    check(len(os.environ.get("GH_TOKEN",""))>=20,"RELEASE_CREDENTIAL_MISSING")
    root=Path(os.environ["RUNNER_TEMP"])/"p08-r174"
    check(root.is_dir() and not root.is_symlink(),"ARTIFACT_ROOT_MISSING")
    check(api("repos/"+PRODUCT+"/git/ref/heads/main")["object"]["sha"]==TARGET,"PRODUCT_MAIN_MOVED")
    check(api("repos/llhzx2018/gov-doc/git/ref/heads/main")["object"]["sha"]==GOV,"GOV_MAIN_MOVED")
    identity=api("repos/"+UPDATES+"/contents/projects/P08-ADOPS.json?ref=main")
    check(identity.get("sha")==PREVIOUS_CHANNEL_BLOB,"CHANNEL_CHANGED")
    original=json.loads(base64.b64decode(identity["content"]))
    check(original.get("source_sha")==BASE_SHA
          and original.get("source_full_manifest_sha256")==BASE_MANIFEST
          and original.get("target_version")=="0.1.6"
          and original.get("from_versions")==["0.1.5"],"CHANNEL_SOURCE_NOT_ISSUED_015")
    # No release or tag collision: fail closed rather than clobbering bytes.
    for endpoint in ("repos/"+PRODUCT+"/git/ref/tags/"+TAG,
                     "repos/"+PRODUCT+"/releases/tags/"+TAG):
        p=subprocess.run(["gh","api",endpoint],capture_output=True,text=True)
        check(p.returncode!=0 and ("404" in p.stderr or "Not Found" in p.stderr),
              "EXISTING_OFFICIAL_TAG_OR_RELEASE_REFUSED")
    for filename in ARTIFACTS:
        check((root/filename).is_file() and not (root/filename).is_symlink(),
              "RELEASE_FILE_MISSING")
    receipt=json.loads((root/"RELEASE_PROVENANCE.json").read_text())
    check(receipt.get("target_sha")==TARGET and receipt.get("governance_sha")==GOV
          and receipt.get("previous_sha")==BASE_SHA
          and receipt.get("source_full_manifest_sha256")==BASE_MANIFEST,
          "PROVENANCE_INVALID")
    local={n:(root/n).stat().st_size for n in ARTIFACTS}
    expected_checksum=(root/"SHA256SUMS").read_text()
    for name in ARTIFACTS[:-1]:
        check(sha(root/name)+"  "+name in expected_checksum.splitlines(),
              "CHECKSUM_INDEX_UNTRUSTED")
    # Only this step receives VF_RELEASE_WRITE_TOKEN. Private source never
    # enters public Git or a public artifact. Owner handles real VPS manually.
    cmd("gh","release","create",TAG,
        *(str(root/x) for x in ARTIFACTS),
        "-R",PRODUCT,"--target",TARGET,
        "--title","VF AdOps v0.1.7 — Official first-update recovery",
        "--notes-file",str(root/"RELEASE_NOTES.md"))
    release=api("repos/"+PRODUCT+"/releases/tags/"+TAG)
    check(release.get("tag_name")==TAG and release.get("draft") is False
          and release.get("prerelease") is False
          and release.get("id",0)>0
          and api("repos/"+PRODUCT+"/git/ref/tags/"+TAG)["object"]["sha"]==TARGET,
          "OFFICIAL_RELEASE_SOURCE_UNTRUSTED")
    assets={x["name"]:x for x in release.get("assets",[])}
    check(set(assets)==set(ARTIFACTS),"OFFICIAL_ASSET_SET_MISMATCH")
    for name in ARTIFACTS:
        check(isinstance(assets[name].get("id"),int)
              and assets[name]["id"]>0
              and assets[name].get("size")==local[name],"ASSET_REMOTE_METADATA_MISMATCH")
    remote=root/"remote"
    remote.mkdir(mode=0o700,exist_ok=False)
    cmd("gh","release","download",TAG,"-R",PRODUCT,"-D",str(remote))
    check({p.name for p in remote.iterdir()}==set(ARTIFACTS),"REMOTE_BYTE_SET_MISMATCH")
    for name in ARTIFACTS:
        check(sha(remote/name)==sha(root/name) and
              (remote/name).stat().st_size==local[name],"REMOTE_SHA256_MISMATCH")
    print("P08_R174_GENUINE_OFFICIAL_RELEASE_TAG_ASSET_IDS_BYTES_SHA256=PASS")
    print("P08_R174_RELEASE_ID="+str(release["id"]))
    # Never synthesize earlier compatibility or widen source_versions.
    after=original.copy()
    after.update(
        target_version="0.1.7",target_sha=TARGET,
        release_tag=TAG,release_id=release["id"],
        asset_id=assets[UPDATE]["id"],asset_name=UPDATE,
        asset_bytes=local[UPDATE],asset_sha256=sha(root/UPDATE),
        full_asset_id=assets[FULL]["id"],full_asset_name=FULL,
        full_asset_bytes=local[FULL],full_asset_sha256=sha(root/FULL),
        notes="P08 v0.1.7: only issued v0.1.5 VERSIONED owner failed-PREPARE sites; exact code-only Atomic, native backup and rollback, separate official verified one-shot rootless recovery PHP for Owner manual site-account execution. No automatic apply, migration, Production or DNS."
    )
    check(after["schema_from"]==after["schema_to"]=="1.1"
          and after["production_auto_apply"] is False
          and after["source_sha"]==BASE_SHA
          and after["source_full_manifest_sha256"]==BASE_MANIFEST
          and after["from_versions"]==["0.1.5"],"CHANNEL_BOUNDARY_INVALID")
    content=json.dumps(after,indent=2,ensure_ascii=False)+"\n"
    body={"message":"dist(P08): v0.1.7 exact official FULL and Atomic from issued 0.1.5",
          "content":base64.b64encode(content.encode()).decode(),
          "sha":identity["sha"],"branch":"main"}
    request=root/"channel-cas.json"
    request.write_text(json.dumps(body)+"\n")
    response=json.loads(cmd("gh","api","--method","PUT",
                            "repos/"+UPDATES+"/contents/projects/P08-ADOPS.json",
                            "--input",str(request)))
    check(bool(response.get("commit",{}).get("sha")),"CHANNEL_COMMIT_MISSING")
    readback=api("repos/"+UPDATES+"/contents/projects/P08-ADOPS.json?ref=main")
    exact=base64.b64decode(readback["content"]).decode()
    check(exact==content,"CHANNEL_REMOTE_READBACK_CHANGED")
    print("P08_R174_OFFICIAL_CORE_UPDATES_ATOMIC_CHANNEL_CAS_AND_READBACK=PASS")
    print("P08_R174_CHANNEL_COMMIT="+response["commit"]["sha"])
    print("P08_R174_RELEASE_SOURCE="+TARGET)
    print("P08_R174_REMOTE_UPDATE_SHA256="+sha(remote/UPDATE))
    print("P08_R174_REMOTE_FULL_SHA256="+sha(remote/FULL))
    print("P08_R174_REMOTE_RESCUE_SHA256="+sha(remote/RESCUE))

if __name__=="__main__":
    try: main()
    except (RuntimeError,KeyError,ValueError,subprocess.SubprocessError,OSError) as e:
        # If issuance was already attempted, do NOT auto-retry/clobber.
        print("P08_R174_PUBLISH_STOP="+str(e).splitlines()[0][:180],file=sys.stderr)
        sys.exit(1)
