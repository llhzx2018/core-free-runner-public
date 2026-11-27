#!/usr/bin/env python3
"""Unpublished P07-M02-only candidate; uses the existing atomic installer.

This is not a public download route. Only exact issued UX3 and exact
development UX4 runtime identities are admitted. The shared installer and
public toolbox are unchanged. No benchmark or system service is started.
"""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import zipfile

MODULE="P07-M02"
LABEL="服务器性能检测（VPS 验机）"
OLD="2.1.1-ux3"
NEW="2.1.1-ux4"
OLD_META="0c4d646c59b7aa1e8ad23ac37e1c2139b4f29692b446926e5728d94ca079387a"
NEW_BLOB="88b38d2ca46ac7325da8b45621a1f0cf16cf8951"
ENGINE_BLOB="9fc4ecfab8bca665ccde238f0e40631657205f82"
ENGINE=Path(__file__).resolve().with_name("p07-three-ux-atomic.py")
BASE=Path("/opt/vfops-modules")
ENTRY="vps-audit.sh"
META="MODULE_MANIFEST.json"

class Blocked(Exception): pass
def require(ok,reason):
    if not ok: raise Blocked(reason)
def sha(data): return hashlib.sha256(data).hexdigest()
def blob(data): return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()

def manifest(build,script):
    value={"schema":"vf.p07.ux.module-bundle.v1","module_id":MODULE,
           "module_name":LABEL,"module_build_id":build,"entrypoint":ENTRY,
           "installation_isolation":MODULE+"_ONLY",
           "files":{"VERSION":sha((build+"\n").encode()),ENTRY:sha(script)}}
    return (json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(",",":"))+"\n").encode()

def check_payload(build,files):
    require(build in (OLD,NEW),"不允许未知的验机版本")
    require(set(files)=={ENTRY,"VERSION",META},"验机文件清单不一致")
    require(files["VERSION"]==(build+"\n").encode(),"验机版本标记不一致")
    require(files[META]==manifest(build,files[ENTRY]),"验机完整性清单不一致")
    if build==OLD:
        require(sha(files[META])==OLD_META,"旧版不是已发行 UX3 的准确内容")
    else:
        require(blob(files[ENTRY])==NEW_BLOB,"新版不是冻结 UX4 的准确内容")

def verify_saved(root,build,module):
    require(module==MODULE,"本安装器仅处理 M02")
    require(root.is_dir() and not root.is_symlink(),"版本目录不安全")
    entries=list(root.iterdir())
    require(all(p.is_file() and not p.is_symlink() for p in entries),"版本目录存在链接或特殊文件")
    check_payload(build,{p.name:p.read_bytes() for p in entries})

def engine_for(base):
    require(ENGINE.is_file() and not ENGINE.is_symlink() and blob(ENGINE.read_bytes())==ENGINE_BLOB,
            "原子安装引擎身份不符")
    spec=importlib.util.spec_from_file_location("p07_m02_ux4_engine",ENGINE)
    engine=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    engine.BASE=base
    engine.CONFIG={MODULE:("m02",LABEL,ENTRY,NEW,OLD)}
    engine.verify_saved=verify_saved
    read=engine.read_package
    def exact_read(archive,checksum,module):
        build,files=read(archive,checksum,module)
        require(build==NEW,"拒绝使用旧包覆盖新版")
        check_payload(build,files)
        return build,files
    engine.read_package=exact_read
    return engine

def rollback(engine,build,confirmation):
    require(os.geteuid()==0,"回滚需要 root")
    require(build==OLD and confirmation==MODULE+":"+OLD,"回滚确认或版本不正确")
    home=engine.BASE/"m02"
    require(engine.BASE.is_dir() and not engine.BASE.is_symlink() and
            home.is_dir() and not home.is_symlink() and
            (home/"releases").is_dir() and not (home/"releases").is_symlink(),
            "模块目录不安全")
    # Same lock as the original install, so verification and switch cannot
    # race another legitimate module upgrade.
    fd=os.open(home/".install.lock",os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW|os.O_NONBLOCK,0o600)
    with os.fdopen(fd,"w") as lock:
        info=os.fstat(lock.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_uid==0,"模块锁不安全")
        fcntl.flock(lock,fcntl.LOCK_EX)
        current,now=engine.current_state(home,MODULE)
        require(now in (OLD,NEW),"模块尚未安装")
        verify_saved(home/"releases"/OLD,OLD,MODULE)
        if now!=OLD: engine.switching(home,current,OLD)
    return OLD

def main():
    parser=argparse.ArgumentParser(description="M02 UX4 DEV candidate atomic installer")
    sub=parser.add_subparsers(dest="command",required=True)
    p=sub.add_parser("install");p.add_argument("archive",type=Path);p.add_argument("sha256")
    p=sub.add_parser("rollback");p.add_argument("--confirm",required=True)
    args=parser.parse_args()
    try:
        engine=engine_for(BASE)
        if args.command=="install":
            result=engine.install(MODULE,args.archive,args.sha256)
        else:
            result=rollback(engine,OLD,args.confirm)
    except (Blocked,OSError,ValueError,RuntimeError,KeyError,zipfile.BadZipFile) as error:
        print("M02 独立安装/回滚已安全停止："+str(error),file=sys.stderr)
        return 13
    except Exception as error:
        # The reused engine has its own exception class; never advertise success.
        print("M02 独立安装/回滚未完成："+type(error).__name__,file=sys.stderr)
        return 13
    print("M02 独立候选版本 "+result+" 已就绪；其他模块未改变。")
    return 0

if __name__=="__main__":raise SystemExit(main())
