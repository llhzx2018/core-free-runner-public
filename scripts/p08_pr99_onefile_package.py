#!/usr/bin/env python3
"""Deterministic P08 PR99 one-file PHP maintenance ZIP; NOT an Atomic or FULL."""
from __future__ import annotations
import argparse, hashlib, json, subprocess, sys, zipfile
from pathlib import Path

SOURCE="349f4c0d46a8350c18cb36b6c8b0c60d2c096c6b"
BLOB="c0e1bd8e26337b8463b57f99f12b8cd44903d0f6"
SCRIPT="P08_015_EmptyMedia_Once.php"
NAMES=[SCRIPT,"MAINTENANCE_PROVENANCE.json","OWNER_INSTRUCTIONS_CN.md","SHA256SUMS"]
OLD="369fcb0aa8fef71b0a2b79c2b7a6c473d2527c3e"
TARGET="ed96b18627cd0a63b1da20a1fd8c9b6c1808f159"
OLD_FULL="538d161339849214999eb6f85da40623a149fc9cf1b592c9e5907f751c434f73"
FULL="7f6a3050db060448df391f0dc5a8a3a2de45c9f28a704cb76606694b82bd084f"
UPDATE="6cd533631c3651117f09ffce3829a565d16d945f7f1e4938c27d678c75e3c399"
def digest(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def gitblob(b:bytes)->str:return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()
def must(ok:bool,msg:str):
    if not ok:raise ValueError("P08_PR99_STOP_"+msg)
def getscript(source:Path)->bytes:
    p=source/"src/Upgrade/LegacyMediaUpgradeBridgeCli.php"
    b=p.read_bytes()
    must(b.startswith(b"<?php") and len(b)>30000 and gitblob(b)==BLOB,"SOURCE_SCRIPT")
    sha=subprocess.run(["git","-C",str(source),"rev-parse","HEAD"],capture_output=True,text=True,check=True).stdout.strip()
    must(sha==SOURCE and (source/"VERSION").read_text().strip()=="0.1.16","SOURCE_SHA")
    return b
def records(b:bytes)->dict[str,bytes]:
    meta={
      "schema":"p08.pr99.maintenance.only.v1",
      "project_id":"P08",
      "repository":"llhzx2018/vf-adops",
      "source_sha":SOURCE,"script_git_blob":BLOB,"script_sha256":digest(b),
      "script_filename":SCRIPT,
      "original_issued_v015_sha":OLD,"official_immutable_v016_sha":TARGET,
      "official_v015_full_sha256":OLD_FULL,
      "official_v016_full_sha256":FULL,
      "official_v016_update_sha256":UPDATE,
      "only_site":"/home/lanlihong-adops/htdocs/adops.lanlihong.com",
      "only_site_user":"lanlihong-adops",
      "original_v015_normal_one_click_eligible":False,
      "production_auto_apply":False,"modifies_existing_release_assets":False,
      "release_kind":"unique_one_time_maintenance_only_not_atomic",
      "requires_owner_password":True,"requires_two_native_backups":True,
      "owner_preview":"POST_RELEASE_REQUIRED_NOT_PASS",
      "owner_real_use":"POST_OWNER_MANUAL_PRODUCTION_REQUIRED_NOT_PASS",
    }
    docs="""# P08 v0.1.15 MySQL 空素材旧站一次性维护

这是独立的 PHP 维护文件，并非 v0.1.16 FULL 或 UPDATE，
不是后台一键升级，不会在网页浏览或加载时执行。

只允许真实旧版 /home/lanlihong-adops/htdocs/adops.lanlihong.com，
由非 root 站点用户 lanlihong-adops 手工执行。
PHP 文件必须置于该用户的
~/.p08-v015-empty-media-once/P08_015_EmptyMedia_Once.php，
目录权限 0700，文件权限 0600，禁止放在 Web public 目录。

必须从未更改的官方 v0.1.16 GitHub Release 获取 FULL 与 UPDATE，
对照 MAINTENANCE_PROVENANCE.json 验证 SHA-256，
将 FULL 在该用户 HOME 下解压到
~/.p08-v015-empty-media-once/official-full（0700）。
不得覆盖正在运行的旧版或任何数据库、Token、用户备份。
先使用 --maintenance-audit 只读确认；
全部身份和保护条件满足、Owner 单独确认后才运行
--maintenance-apply，管理员密码仅经 STDIN 传入，
禁止作为 shell 参数、环境变量或日志输出。
命令最后包含 CONFIRM_MEDIA_SAFE_V015_TO_V016 确认词。
错误密码、素材异常、数据库非空、未验证源或资产必须拒绝。
任何失败应停止并保留恢复快照，绝不伪造媒体文件。
"""
    res={
      SCRIPT:b,
      "MAINTENANCE_PROVENANCE.json":(json.dumps(meta,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode(),
      "OWNER_INSTRUCTIONS_CN.md":docs.encode(),
    }
    res["SHA256SUMS"]="".join(f"{digest(res[k])}  {k}\n" for k in NAMES[:3]).encode()
    return res
def verify(path:Path,source:Path):
    must(not path.is_symlink() and path.is_file(),"ARCHIVE_FILE")
    with zipfile.ZipFile(path) as z:
        infos=z.infolist()
        must([i.filename for i in infos]==NAMES and z.testzip() is None,"ARCHIVE_ENTRIES_CRC")
        for i in infos:
            must(((i.external_attr>>16)&0o170000)==0o100000,"ARCHIVE_NONREGULAR")
            must(".." not in i.filename.split("/") and not i.filename.startswith("/"),"ARCHIVE_TRAVERSAL")
        items={k:z.read(k) for k in NAMES}
        script=getscript(source)
        must(items[SCRIPT]==script,"ARCHIVE_SOURCE_BYTES")
        meta=json.loads(items["MAINTENANCE_PROVENANCE.json"])
        must(meta["source_sha"]==SOURCE and meta["script_git_blob"]==BLOB
             and meta["script_sha256"]==digest(script),"ARCHIVE_MANIFEST")
        must(meta["production_auto_apply"] is False
             and meta["original_v015_normal_one_click_eligible"] is False,"UNSAFE_FLAGS")
        must(items["SHA256SUMS"]=="".join(f"{digest(items[k])}  {k}\n" for k in NAMES[:3]).encode(),"ARCHIVE_CHECKSUMS")
        must(not any(x in b"".join(items.values()) for x in [b"github_pat_",b"DB_PASSWORD="]),"SECRETS")
    print("P08_PR99_EXACT_FINAL_ZIP_STRUCTURE_AND_BYTES=PASS")
def build(path:Path,source:Path):
    data=records(getscript(source));path.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(path,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name in NAMES:
            entry=zipfile.ZipInfo(name,date_time=(2020,1,1,0,0,0))
            entry.compress_type=zipfile.ZIP_DEFLATED
            entry.create_system=3
            entry.external_attr=0o100600 << 16
            z.writestr(entry,data[name],compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    verify(path,source)
    print("P08_PR99_FINAL_ZIP_SHA256="+digest(path.read_bytes()))
    print("P08_PR99_EXACT_MERGED_MAIN="+SOURCE)
    print("P08_PR99_PHP_GIT_BLOB="+BLOB)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True,type=Path)
    p.add_argument("--output",type=Path)
    p.add_argument("--verify",type=Path)
    a=p.parse_args()
    try:
        if a.output:build(a.output,a.source)
        elif a.verify:verify(a.verify,a.source)
        else:p.error("--output or --verify required")
    except (ValueError,zipfile.BadZipFile,OSError,KeyError,subprocess.CalledProcessError) as e:
        print("P08_PR99_FINAL_DELIVERY=BLOCKED:"+str(e),file=sys.stderr)
        sys.exit(1)
