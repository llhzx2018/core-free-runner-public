#!/usr/bin/env python3
"""Owner-authorized P08 v016 Mode Y only. Exact immutable proof before ANY tag.
Runtime secret via GitHub Actions only. Never touches Owner Production."""
from __future__ import annotations
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

REPO="llhzx2018/vf-adops"
SHA="ed96b18627cd0a63b1da20a1fd8c9b6c1808f159"
FUNC="67b3b98477f93028007c44e648a0b759991c8f19"
GOV="80ab251e15e63fc01a4e587e93054b0f6d0179a5"
OLD="369fcb0aa8fef71b0a2b79c2b7a6c473d2527c3e"
OLD_RELEASE=453401976
OLD_FULL=(774232524,"538d161339849214999eb6f85da40623a149fc9cf1b592c9e5907f751c434f73")
OLD_UPDATE=(774232507,"e8b949d46f6adba0221c6a258c2e844891379494f7ed5b8dcb5903689e4fe51f")
FINAL_FULL="7f6a3050db060448df391f0dc5a8a3a2de45c9f28a704cb76606694b82bd084f"
FINAL_UPDATE="6cd533631c3651117f09ffce3829a565d16d945f7f1e4938c27d678c75e3c399"
NATIVE_RUN=44915042470
NATIVE_HEAD="42d2172c5b1a520b0f26c1cef95652c2488cc492"
BROWSER_RUN=44916014874
BROWSER_HEAD="ec3124c09b1b14de43a794cef6d384d9c52ca10f"
PACKAGE_RUN=44915781073
PACKAGE_HEAD="f0ffcf3e60404fe7ab48607d717727cef9f3e427"

def need(v,code):
    if not v: raise RuntimeError("P08_V016_MODE_Y_STOP_"+code)
def cmd(args,timeout=200):
    p=subprocess.run(args,text=True,capture_output=True,timeout=timeout)
    if p.returncode:
        # No raw gh/curl errors: they can contain private URLs or credentials.
        raise RuntimeError("P08_V016_MODE_Y_STOP_TOOL_"+args[0].upper().replace('-','_'))
    return p.stdout.strip()
def api(path):
    return json.loads(cmd(["gh","api",path],90))
def sha(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()
def verified_run(run_id,head,count):
    path=f"repos/llhzx2018/core-free-runner-public/actions/runs/{run_id}"
    r=api(path)
    need(r.get("head_sha")==head and r.get("conclusion")=="success","RUN_IDENTITY_"+str(run_id))
    j=api(path+"/jobs?per_page=100").get("jobs",[])
    need(len(j)==count and all(x.get("conclusion")=="success" for x in j),"JOB_PROOF_"+str(run_id))
def missing(path):
    p=subprocess.run(["gh","api",path],capture_output=True,text=True,timeout=35)
    need(p.returncode!=0 and ("HTTP 404" in p.stderr or "Not Found" in p.stderr),
         "TAG_EXISTS_OR_CREDENTIAL_UNKNOWN")
def safe_channel():
    o=api("repos/llhzx2018/core-updates/contents/projects/P08-ADOPS.json?ref=main")
    c=json.loads(base64.b64decode(o["content"]).decode("utf-8"))
    need(c.get("target_version")=="0.1.15" and c.get("release_tag")=="v0.1.15"
         and c.get("release_id")==OLD_RELEASE and c.get("target_sha")==OLD
         and c.get("production_auto_apply") is False
         and c.get("backup_required") is True,"PREVIOUS_CHANNEL_UNEXPECTED")
    return o["sha"]
def assert_zip(path,manifest,expected_type,source,version):
    with zipfile.ZipFile(path) as z:
        need(z.testzip() is None,"ZIP_INTEGRITY")
        names=z.namelist()
        need(len(names)>6100 and len(names)==len(set(names)),"ZIP_ENTRIES")
        for name in names:
            need(not name.startswith("/") and ".." not in name.split("/"),"ZIP_TRAVERSAL")
            need(not name.startswith("storage/app/private/adops/landing-assets/")
                 and not name.endswith(("/.env","/github-read-token")),"ZIP_PRIVATE_DATA")
        m=json.loads(z.read(manifest))
        need(m.get("type")==expected_type and m.get("target_version")==version,"MANIFEST_TYPE_VERSION")
        need(m.get("source_sha")==source,"MANIFEST_SOURCE")
        return m

def main():
    need(os.getenv("GITHUB_ACTIONS")=="true"
         and os.getenv("GITHUB_ACTOR")=="llhzx2018"
         and os.getenv("P08_MODE_Y_ISSUE_ONCE")=="YES"
         and len(os.getenv("GH_TOKEN",""))>=20,"UNAUTHORIZED_RUNTIME")
    need(cmd(["git","-C","target","rev-parse","HEAD"])==SHA,"SOURCE_CHECKOUT")
    need(cmd(["git","-C","gov","rev-parse","HEAD"])==GOV,"GOV_CHECKOUT")
    need((Path("target")/"VERSION").read_text().strip()=="0.1.16","VERSION")
    need("## RP-07Y" in (Path("target")/"docs/authority/ACCEPTANCE_MATRIX.md").read_text(),"PROJECT_AUTHORITY")
    need("| skill-release | V3.24 |" in (Path("gov")/"CURRENT.md").read_text(),"GOV_AUTHORITY")
    verified_run(NATIVE_RUN,NATIVE_HEAD,6)
    verified_run(BROWSER_RUN,BROWSER_HEAD,2)
    verified_run(PACKAGE_RUN,PACKAGE_HEAD,1)
    need(api("repos/"+REPO+"/git/ref/heads/main")["object"]["sha"]==SHA,"MAIN_MOVED")
    need(api("repos/llhzx2018/gov-doc/git/ref/heads/main")["object"]["sha"]==GOV,"GOV_MAIN_MOVED")
    # The full git tree is independently checked, no source file may drift.
    t=api("repos/"+REPO+"/git/commits/"+SHA)["tree"]["sha"]
    need(cmd(["git","-C","target","rev-parse","HEAD^{tree}"])==t,"SOURCE_TREE_MISMATCH")
    parent=api("repos/"+REPO+"/compare/"+FUNC+"..."+SHA)
    changed={f["filename"] for f in parent["files"]}
    need(changed=={"AGENTS.md","docs/authority/CURRENT.md",
                   "docs/authority/ACCEPTANCE_MATRIX.md","docs/authority/RPD.md"},"SCOPE_DRIFT")
    channel_blob=safe_channel()
    missing("repos/"+REPO+"/git/ref/tags/v0.1.16")
    missing("repos/"+REPO+"/releases/tags/v0.1.16")
    old=api("repos/"+REPO+"/releases/tags/v0.1.15")
    need(old.get("id")==OLD_RELEASE and old.get("draft") is False
         and old.get("prerelease") is False,"ORIGINAL_RELEASE_CHANGED")
    need(api("repos/"+REPO+"/git/ref/tags/v0.1.15")["object"]["sha"]==OLD,"ORIGINAL_TAG_CHANGED")
    a={i["name"]:i for i in old.get("assets",[])}
    for name,(aid,digest) in {
      "VF_AdOps_V0.1.15_FULL.zip":OLD_FULL,
      "VF_AdOps_V0.1.15_UPDATE.zip":OLD_UPDATE,
    }.items():
        need(a.get(name,{}).get("id")==aid,"ORIGINAL_ASSET_ID_CHANGED")
        need(a[name].get("digest") in (None,"sha256:"+digest),"ORIGINAL_ASSET_DIGEST_CHANGED")
    print("P08_V016_MODE_Y_LIVE_SOURCE_GOV_13DOMAIN_3DB_HTTPS_PREISSUE=PASS")
    tmp=Path(os.environ["RUNNER_TEMP"])/"p08-v016-mode-y-official"
    need(not tmp.exists() and not tmp.is_symlink(),"SCRATCH_COLLISION")
    tmp.mkdir(mode=0o700)
    # Both original remote assets, NOT synthetically reconstructed legacy bytes.
    cmd(["gh","release","download","v0.1.15","-R",REPO,"-D",str(tmp),
         "-p","VF_AdOps_V0.1.15_FULL.zip","-p","VF_AdOps_V0.1.15_UPDATE.zip"],200)
    oldfull=tmp/"VF_AdOps_V0.1.15_FULL.zip"
    oldupdate=tmp/"VF_AdOps_V0.1.15_UPDATE.zip"
    need(sha(oldfull)==OLD_FULL[1] and sha(oldupdate)==OLD_UPDATE[1],"OLD_REMOTE_BYTES")
    with zipfile.ZipFile(oldfull) as z:
        oldman=z.read("FULL_MANIFEST.json")
        oldm=json.loads(oldman)
    need(oldm.get("source_sha")==OLD and oldm.get("target_version")=="0.1.15"
         and oldm.get("type")=="CLEAN_FULL_ONLY","ORIGINAL_MANIFEST")
    om=tmp/"old-manifest.json";om.write_bytes(oldman)
    oldmanhash=hashlib.sha256(oldman).hexdigest()
    # A no-ordinary-v015 upgrade channel is mandatory: the original worker
    # lacks nonempty landing-assets pre-switch backup. Only site-user bridge.
    future_source_versions=[]
    need("0.1.15" not in future_source_versions,"UNSAFE_015_NORMAL_CHANNEL")
    print("P08_V016_MODE_Y_IMMUTABLE_ISSUED_015_BOTH_ORIGINAL_ASSETS=PASS")
    for it in ("first","second"):
        cmd(["python3","-B","target/scripts/build_full.py",
             "--source",str(Path("target").resolve()),"--output",str(tmp/("full-"+it+".zip")),
             "--version","0.1.16","--source-sha",SHA,
             "--governance-root",str(Path("gov").resolve())],200)
        cmd(["python3","-B","target/scripts/build_atomic.py",
             "--source","target","--output",str(tmp/("update-"+it+".zip")),
             "--source-version","0.1.15","--source-sha",OLD,
             "--source-full-manifest-sha256",oldmanhash,"--previous-full-manifest",str(om),
             "--target-version","0.1.16","--target-sha",SHA],200)
    need(sha(tmp/"full-first.zip")==sha(tmp/"full-second.zip")==FINAL_FULL,"FINAL_FULL_SHA")
    need(sha(tmp/"update-first.zip")==sha(tmp/"update-second.zip")==FINAL_UPDATE,"FINAL_UPDATE_SHA")
    fm=assert_zip(tmp/"full-first.zip","FULL_MANIFEST.json","CLEAN_FULL_ONLY",SHA,"0.1.16")
    um=assert_zip(tmp/"update-first.zip","ATOMIC_MANIFEST.json","P08_ATOMIC_CODE_ONLY_V1",OLD,"0.1.16")
    need(um.get("source_full_manifest_sha256")==oldmanhash
         and um.get("target_sha")==SHA and um.get("schema_changes") is False,
         "ATOMIC_ORIGIN_SCHEMA")
    need(fm.get("data_included") is False,"FULL_USER_DATA")
    print("P08_V016_MODE_Y_FINAL_OFFICIAL_DOUBLE_ZIP_EXACT_BYTES=PASS")
    root=tmp
    names=["VF_AdOps_V0.1.16_FULL.zip","VF_AdOps_V0.1.16_UPDATE.zip"]
    (tmp/"full-first.zip").rename(tmp/names[0])
    (tmp/"update-first.zip").rename(tmp/names[1])
    for filename in ["full-second.zip","update-second.zip"]:
        (tmp/filename).unlink()
    notes="""# VF AdOps v0.1.16 · 素材备份与旧版安全升级桥

此版只合并已批准的素材备份修复 PR #94 和旧版安全桥 PR #97。
Clean FULL 用于全新空站；严禁以 FULL 覆盖已安装站点、数据库、媒体或 Token。

**重要：原始官方 v0.1.15 普通后台一键升级不兼容非空 landing-assets**，
不能将其作为安全的 v0.1.15→v0.1.16 普通一键入口，也不会向它提供可安装的自动更新提示。
已发行的 v0.1.15 只能使用已验证的站点 Linux 用户权限 + Owner 密码明确确认的一次性兼容桥，
先核验官方 Tag/FULL/UPDATE 字节及源清单、原生 DB/媒体/Token 双备份和独立恢复，再执行 Atomic；
任何来源、身份或权限不匹配都必须停止。该 CLI 不是浏览器按钮，不允许自动运行或公共写入口。

真实 SQLite WAL、MySQL8.4、MariaDB11.8 旧版桥 + SIGKILL137/备份恢复、
新版 Clean FULL、旧/新 HTTPS Chromium 390/768/1440 与 419/429/503、
13 项公共规范以及最终源码双次构建均已在隔离机器验证。
Production、CloudPanel、DNS、SSL 和正式站升级只由 Owner 手工执行；
Owner Preview 与 Real Use 仍待后置验收。
"""
    (tmp/"RELEASE_NOTES.md").write_text(notes,encoding="utf8")
    provenance={
      "project_id":"P08","repository":REPO,"source_version":"0.1.15",
      "source_sha":OLD,"source_full_manifest_sha256":oldmanhash,
      "target_version":"0.1.16","target_sha":SHA,"target_tree_sha":t,
      "governance_sha":GOV,"mode":"Y","schema_changes":False,
      "backup_required":True,"rollback_supported":True,
      "production_auto_apply":False,"normal_unbridged_v015_supported":False,
      "legacy_safe_path":"owner-password-confirmed-site-user-one-shot",
      "final_full_sha256":FINAL_FULL,"final_update_sha256":FINAL_UPDATE,
      "native_run":NATIVE_RUN,"https_run":BROWSER_RUN,"thirteen_area_run":PACKAGE_RUN,
      "owner_preview":"POST_RELEASE_REQUIRED_NOT_PASS",
      "owner_real_use":"POST_OWNER_MANUAL_PRODUCTION_REQUIRED_NOT_PASS"}
    (tmp/"RELEASE_PROVENANCE.json").write_text(json.dumps(provenance,sort_keys=True,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    tosum=names+["RELEASE_NOTES.md","RELEASE_PROVENANCE.json"]
    (tmp/"SHA256SUMS").write_text("".join(sha(tmp/n)+"  "+n+"\n" for n in tosum))
    pub=tosum+["SHA256SUMS"]
    need(set((tmp/"SHA256SUMS").read_text().splitlines())
         =={sha(tmp/n)+"  "+n for n in tosum},"SUMS_UNTRUSTED")
    # Last pre-Tag remote fence: true main/old channel, no preexisting target.
    need(api("repos/"+REPO+"/git/ref/heads/main")["object"]["sha"]==SHA,"MAIN_MOVED_PREPUBLISH")
    need(safe_channel()==channel_blob,"CHANNEL_MOVED_PREPUBLISH")
    missing("repos/"+REPO+"/git/ref/tags/v0.1.16")
    missing("repos/"+REPO+"/releases/tags/v0.1.16")
    print("P08_V016_MODE_Y_ALL_MANDATORY_PREISSUE_GATES=PASS")
    # One officially authorized, once-only operation; NO FORCE / overwrite.
    cmd(["gh","release","create","v0.1.16",
         *(str(tmp/name) for name in pub),
         "-R",REPO,"--target",SHA,"--title","VF AdOps v0.1.16 — Safe Media Bridge",
         "--notes-file",str(tmp/"RELEASE_NOTES.md")],200)
    rel=api("repos/"+REPO+"/releases/tags/v0.1.16")
    need(rel.get("draft") is False and rel.get("prerelease") is False
         and rel.get("tag_name")=="v0.1.16" and isinstance(rel.get("id"),int),"REMOTE_RELEASE")
    need(api("repos/"+REPO+"/git/ref/tags/v0.1.16")["object"]["sha"]==SHA,"REMOTE_TAG_SHA")
    assets={x["name"]:x for x in rel.get("assets",[])}
    need(set(assets)==set(pub),"REMOTE_ASSET_SET")
    for name in pub:
        x=assets[name]
        need(isinstance(x.get("id"),int) and x["id"]>0
             and x.get("size")== (tmp/name).stat().st_size,"REMOTE_ASSET_ID_SIZE")
        need(x.get("digest") in (None,"sha256:"+sha(tmp/name)),"REMOTE_SHA_HEADER")
    redownload=tmp/"remote";redownload.mkdir(mode=0o700)
    cmd(["gh","release","download","v0.1.16","-R",REPO,"-D",str(redownload)],200)
    need({p.name for p in redownload.iterdir()}==set(pub),"REMOTE_DOWNLOADED_NAMES")
    for name in pub: need(sha(redownload/name)==sha(tmp/name),"REMOTE_BYTES_"+name)
    need(api("repos/"+REPO+"/releases/tags/v0.1.15")["id"]==OLD_RELEASE,"OLD_RELEASE_MUTATED")
    need(safe_channel()==channel_blob,"CHANNEL_PREMATURE_WRITE")
    print("P08_V016_MODE_Y_OFFICIAL_RELEASE_REMOTE_REDOWNLOAD=PASS")
    print("P08_V016_RELEASE_ID="+str(rel["id"]))
    print("P08_V016_FULL_ASSET_ID="+str(assets[names[0]]["id"]))
    print("P08_V016_FULL_BYTES="+str((tmp/names[0]).stat().st_size))
    print("P08_V016_UPDATE_ASSET_ID="+str(assets[names[1]]["id"]))
    print("P08_V016_UPDATE_BYTES="+str((tmp/names[1]).stat().st_size))
    print("P08_V016_RELEASE_PUBLISHED_AT="+str(rel.get("published_at")))
    print("P08_V016_CHANNEL_STILL_V015=YES")
    print("P08_V016_PRODUCTION_CLOUDPANEL_DNS_SSL=UNTOUCHED")
if __name__=="__main__":main()
