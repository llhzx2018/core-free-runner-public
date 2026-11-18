#!/usr/bin/env python3
"""P07 M01/M02/M04 isolated atomic module installer.

No server provisioning, no agent service start/stop, no CloudPanel, no DNS.
Only the selected module's /opt/vfops-modules/mNN release+current may change.
A ZIP is untrusted until its caller-pinned SHA256 and its full internal
MODULE_MANIFEST.json have been verified. No implicit cross-module upgrade.
"""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import uuid
import zipfile

CONFIG={
 "P07-M01":("m01","网络代理节点（V2Ray）","vf-node.sh","0.1.0-ux3","0.1.0-ux2"),
 "P07-M02":("m02","服务器性能检测（VPS 验机）","vps-audit.sh","2.1.1-ux3","2.1.1-ux2"),
 "P07-M04":("m04","服务器维护与安全","vf-system-care.sh","0.1.0-ux5","0.1.0-ux4"),
}
BASE=Path("/opt/vfops-modules")
MAX_SIZE=50*1024*1024

class Rejected(Exception): pass
def block(reason): raise Rejected(reason)
def sha(content): return hashlib.sha256(content).hexdigest()
def valid_build(s): return bool(re.fullmatch(r"[A-Za-z0-9._-]{1,64}",s))
def safe_folder(p):
    if p.is_symlink() or p.exists() and not p.is_dir(): block("已有路径不是安全目录")
    p.mkdir(mode=0o755,parents=False,exist_ok=True)
    if p.is_symlink(): block("不允许符号链接目录")

def read_package(zip_path, expected_sha, expected_module):
    if expected_module not in CONFIG: block("不是允许的 P07 子模块")
    if not re.fullmatch(r"[0-9a-f]{64}",expected_sha): block("非法 SHA256")
    if zip_path.is_symlink() or not zip_path.is_file() or zip_path.stat().st_size>MAX_SIZE:
        block("安装包不存在或不安全")
    if sha(zip_path.read_bytes())!=expected_sha: block("安装包 SHA256 不匹配")
    prefix="p07-"+expected_module.split("-")[-1].lower()+"/"
    result={}
    with zipfile.ZipFile(zip_path) as z:
        if not 1<=len(z.infolist())<=100: block("安装包文件数量异常")
        total=0
        for item in z.infolist():
            name=item.filename
            if item.is_dir() or not name.startswith(prefix): block("发现其他模块或非法路径")
            rel=name[len(prefix):]
            p=PurePosixPath(rel)
            if (not rel or not rel.isascii() or "\\" in rel or "//" in rel or
                p.is_absolute() or "." in p.parts or ".." in p.parts or
                len(p.parts)>5 or not re.fullmatch(r"[A-Za-z0-9_./-]+",rel)):
                block("安装包内有非法路径")
            if stat.S_IFMT(item.external_attr>>16)!=stat.S_IFREG: block("ZIP 含链接或特殊文件")
            if rel in result or item.file_size>8*1024*1024 or item.file_size<=0: block("重复或空文件")
            total+=item.file_size
            if total>MAX_SIZE: block("包内容超限")
            result[rel]=z.read(item)
    if "MODULE_MANIFEST.json" not in result: block("缺模块身份")
    try:
        meta=json.loads(result.pop("MODULE_MANIFEST.json"))
        config=CONFIG[expected_module]
        if (meta.get("schema")!="vf.p07.ux.module-bundle.v1" or
            meta.get("module_id")!=expected_module or
            meta.get("module_name")!=config[1] or
            meta.get("entrypoint")!=config[2] or
            meta.get("installation_isolation")!=expected_module+"_ONLY" or
            not valid_build(meta.get("module_build_id")) or
            meta["module_build_id"] not in config[3:] or
            meta.get("files")!={n:sha(b) for n,b in result.items()} or
            result.get("VERSION")!=(meta["module_build_id"]+"\n").encode() or
            config[2] not in result):
            block("模块、版本或完整性清单不一致")
        build=meta["module_build_id"]
        if expected_module=="P07-M01":
            required={"MANIFEST.sha256","SOURCE_IDENTITY","lib/common.sh","uninstall.sh","status.sh"}
        elif expected_module=="P07-M04":
            required={"MANIFEST.gitblob","lib/common.sh","lib/resource_apply.py","updates.sh"}
        else: required={config[2],"VERSION"}
        if not required.issubset(result): block("模块运行依赖不完整")
        result["MODULE_MANIFEST.json"]=json.dumps(meta,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()+b"\n"
        return build,result
    except (ValueError,TypeError,KeyError,UnicodeError):
        block("模块清单无法解析")

def verify_saved(root,expected):
    if not root.is_dir() or root.is_symlink(): block("旧版本路径异常")
    marker=root/"MODULE_MANIFEST.json"
    if not marker.is_file() or marker.is_symlink(): block("旧版本没有完整性清单")
    try: meta=json.loads(marker.read_bytes())
    except Exception: block("旧模块清单损坏")
    if meta.get("module_build_id")!=expected: block("旧版本身份不符")
    files=meta.get("files")
    if not isinstance(files,dict): block("旧版本完整性损坏")
    actual={p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    if actual!=set(files)|{"MODULE_MANIFEST.json"}: block("旧模块文件数量变化")
    for name,expected_sha in files.items():
        p=root/name
        if p.is_symlink() or not p.is_file() or sha(p.read_bytes())!=expected_sha:
            block("已有文件内容变化")

def current_state(home,module):
    current=home/"current"
    if current.is_symlink():
        link=os.readlink(current)
        if not re.fullmatch(r"releases/[A-Za-z0-9._-]{1,64}",link): block("现有模块指针异常")
        build=link.removeprefix("releases/")
        if build not in CONFIG[module][3:]: block("旧版本不在本次许可来源内")
        verify_saved(home/link,build)
        return current,build
    if current.exists(): block("现有模块目录不能覆盖")
    return current,None

def switching(home,current,build):
    temp=home/(".switch-"+uuid.uuid4().hex)
    try:
        temp.symlink_to("releases/"+build)
        os.replace(temp,current)
    finally:
        if temp.is_symlink(): temp.unlink()

def install(module,archive,checksum):
    if os.geteuid()!=0: block("独立安装需要 root")
    build,files=read_package(archive,checksum,module)
    if build!=CONFIG[module][3]: block("拒绝安装历史包覆盖新模块")
    safe_folder(BASE)
    home=BASE/CONFIG[module][0]; safe_folder(home)
    rel=home/"releases";safe_folder(rel)
    lockfile=home/".install.lock"
    if lockfile.is_symlink(): block("模块锁不安全")
    fd=os.open(lockfile,os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"w") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        current,prior=current_state(home,module)
        target=rel/build
        if target.exists() or target.is_symlink():
            verify_saved(target,build)
            if prior!=build: switching(home,current,build)
            return build
        stage=home/(".stage-"+uuid.uuid4().hex)
        try:
            stage.mkdir(mode=0o700)
            for name,data in sorted(files.items()):
                path=stage/name;path.parent.mkdir(parents=True,exist_ok=True)
                with path.open("xb") as f:f.write(data)
                path.chmod(0o755 if name.endswith(".sh") else 0o644)
            entry=stage/CONFIG[module][2]
            check=subprocess.run(["bash","-n",str(entry)],timeout=12)
            if check.returncode: block("入口脚本语法错误")
            option="--build-id" if module=="P07-M02" else "--version"
            run=subprocess.run(["bash",str(entry),option],capture_output=True,text=True,timeout=15)
            if run.returncode or build not in run.stdout:
                block("模块运行版号未验证")
            stage.chmod(0o755)
            os.replace(stage,target)
            switching(home,current,build)
        finally:
            if stage.exists():shutil.rmtree(stage)
        return build

def rollback(module,build,confirmation):
    if os.geteuid()!=0: block("回滚需要 root")
    if module not in CONFIG or build not in CONFIG[module][3:] or confirmation!=module+":"+build:
        block("回滚身份或确认不正确")
    home=BASE/CONFIG[module][0]
    if home.is_symlink() or not home.is_dir(): block("模块不存在")
    current,now=current_state(home,module)
    if not now:block("模块尚未安装")
    verify_saved(home/"releases"/build,build)
    switching(home,current,build)
    return build

def main():
    p=argparse.ArgumentParser(description="P07 M01/M02/M04 independent atomic installer")
    p.add_argument("module",choices=CONFIG)
    subs=p.add_subparsers(dest="command",required=True)
    a=subs.add_parser("install");a.add_argument("zip",type=Path);a.add_argument("sha256")
    b=subs.add_parser("rollback");b.add_argument("version");b.add_argument("--confirm",required=True)
    x=p.parse_args()
    try:
        if x.command=="install": version=install(x.module,x.zip,x.sha256)
        else:version=rollback(x.module,x.version,x.confirm)
        print(f"{x.module} {CONFIG[x.module][1]}：独立版本 {version}；其它模块未改变。")
    except (Rejected,OSError,ValueError,KeyError,subprocess.SubprocessError,zipfile.BadZipFile) as e:
        print(f"{x.module} 独立升级安全阻断：{e}",file=sys.stderr);return 13
    return 0

if __name__=="__main__":raise SystemExit(main())
