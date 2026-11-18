#!/usr/bin/env python3
"""Official P07 M01/M02/M04 menu-only upgrade route (never auto-provision).

Only the explicitly selected module may be installed, only after verifying
the existing module's immutable signed origin and asking Owner permission.
Works with the public official five-module UX release; does not touch
CloudPanel, DNS, websites, databases or the other four module roots.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
import urllib.request

REPO="llhzx2018/core-free-runner-public"
RELEASE="p07-all-ux-v0.1.0-20261118"
INSTALLER_COMMIT="cadbe0b84b9d39a70df7f6863ef6967449f90886"
INSTALLER_GIT_BLOB="9fc4ecfab8bca665ccde238f0e40631657205f82"
LIMIT=60*1024*1024
MODULES={
    "P07-M01":dict(slot="m01",version="0.1.0-ux3",previous="0.1.0-ux2",
        filename="P07-M01-0.1.0-ux3.zip",
        sha="13e79e7c7a4f1170c74da24e783804c3c2bda06fe6c46b768497694e826b3ed7",
        meta="b52b2d17095bc9e84567319a71fa19a8822bd6bb696bac3dfccd85d80923d6ab",
        entry="vf-node.sh",label="网络代理节点（V2Ray）"),
    "P07-M02":dict(slot="m02",version="2.1.1-ux3",previous="2.1.1-ux2",
        filename="P07-M02-2.1.1-ux3.zip",
        sha="88da5b8219fb7e04d606eb3de998d872747cb05153bdd93c7351b46f957164b4",
        meta="0c4d646c59b7aa1e8ad23ac37e1c2139b4f29692b446926e5728d94ca079387a",
        entry="vps-audit.sh",label="服务器性能检测（VPS 验机）"),
    "P07-M04":dict(slot="m04",version="0.1.0-ux5",previous="0.1.0-ux4",
        filename="P07-M04-0.1.0-ux5.zip",
        sha="2ff45c263f930e258a3c323b6c009e0973531d3f90a2e432a66aed704c9baa7d",
        meta="370385aab38b4b8f4c069e40ed59fa8d5c6454d65c7982925d0fb123404eb0d7",
        entry="vf-system-care.sh",label="服务器维护与安全"),
}
BASE=Path("/opt/vfops-modules")
class Blocked(Exception):pass
def blocked(message):raise Blocked(message)
def sha(data):return hashlib.sha256(data).hexdigest()
def gitblob(data):return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
def fetch(url,destination,expected,kind="sha256"):
    if not url.startswith(("https://raw.githubusercontent.com/llhzx2018/","https://github.com/llhzx2018/")):
        blocked("不可信的来源地址")
    request=urllib.request.Request(url,headers={"User-Agent":"P07-Official-UX-Route"})
    with urllib.request.urlopen(request,timeout=90) as response:
        data=response.read(LIMIT+1)
    if not data or len(data)>LIMIT:blocked("下载文件大小异常")
    actual=gitblob(data) if kind=="gitblob" else sha(data)
    if actual!=expected:blocked("官方文件 SHA/Git blob 与锁定身份不一致")
    destination.write_bytes(data)
def get_installer(temp):
    path=temp/"p07-three-ux-atomic.py"
    url=("https://raw.githubusercontent.com/"+REPO+"/"+
         INSTALLER_COMMIT+"/installers/p07-three-ux-atomic.py")
    fetch(url,path,INSTALLER_GIT_BLOB,"gitblob")
    spec=importlib.util.spec_from_file_location("p07_three_ux_atomic_verified",path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
def validate_paths(home):
    if BASE.is_symlink() or home.is_symlink():blocked("不可信的模块安装根目录")
    if (home/"releases").is_symlink():blocked("不可信的版本目录")
    if home.exists() and not home.is_dir():blocked("已有模块根目录被占用")
    current=home/"current"
    if current.is_symlink():
        rel=os.readlink(current)
        if not re.fullmatch(r"releases/[A-Za-z0-9._-]{1,64}",rel):
            blocked("模块指针不是受控发行目录")
        return rel.removeprefix("releases/")
    if current.exists():blocked("已有 current 不是原子版本指针")
    return None
def verified_new(home,module,conf):
    target=home/"releases"/conf["version"]
    if target.is_symlink() or not target.is_dir():blocked("新版安装目录异常")
    meta=target/"MODULE_MANIFEST.json"
    if meta.is_symlink() or not meta.is_file() or sha(meta.read_bytes())!=conf["meta"]:
        blocked("新版本完整性清单不是已发布签名")
    try:
        data=json.loads(meta.read_text(encoding="utf-8"))
        if (data.get("schema")!="vf.p07.ux.module-bundle.v1" or
            data.get("module_id")!=module or
            data.get("module_build_id")!=conf["version"] or
            data.get("entrypoint")!=conf["entry"] or
            data.get("installation_isolation")!=module+"_ONLY"):
            blocked("新版本身份不匹配")
        files=data["files"]
        if not isinstance(files,dict) or len(files)>100 or len(files)<2:
            blocked("文件清单不完整")
        actual={}
        for item in target.rglob("*"):
            if item.is_symlink():blocked("运行目录包含链接")
            if item.is_file():actual[item.relative_to(target).as_posix()]=item
            elif not item.is_dir():blocked("运行目录包含特殊文件")
        if set(actual)!=set(files)|{"MODULE_MANIFEST.json"}:
            blocked("运行目录包含未登记文件")
        for name,digest in files.items():
            if (not isinstance(name,str) or not re.fullmatch(r"[A-Za-z0-9_./-]+",name)
                or ".." in PurePosixPath(name).parts or
                not isinstance(digest,str) or not re.fullmatch(r"[0-9a-f]{64}",digest)
                or sha(actual[name].read_bytes())!=digest):
                blocked("运行文件 SHA 校验失败")
    except (ValueError,KeyError,TypeError,UnicodeError,OSError) as error:
        blocked("运行文件完整性异常")
    entry=target/conf["entry"]
    result=subprocess.run(["bash",str(entry),"--version"],capture_output=True,text=True,timeout=12)
    if result.returncode or conf["version"] not in result.stdout:
        blocked("新版入口版本检查失败")
    if module=="P07-M02":
        result=subprocess.run(["bash",str(entry),"--build-id"],capture_output=True,text=True,timeout=12)
        if result.returncode or result.stdout.strip()!=conf["version"]:
            blocked("验机程序构建身份错误")
def main():
    if len(sys.argv)!=2 or sys.argv[1] not in MODULES:
        blocked("仅可从工具箱进入指定模块")
    module=sys.argv[1];conf=MODULES[module];home=BASE/conf["slot"]
    current_version=validate_paths(home)
    if current_version==conf["version"]:
        verified_new(home,module,conf)
        return 0
    if current_version is not None and current_version!=conf["previous"]:
        blocked("当前安装不在本轮已验证升级范围；旧程序保留")
    # A real user's old install is checked against the original pinned
    # public manifest BEFORE asking permission or executing any owner code.
    with tempfile.TemporaryDirectory(prefix="p07-official-ux-",dir="/tmp") as temporary:
        temp=Path(temporary)
        installer=get_installer(temp)
        if current_version:
            installer.verify_saved(home/"releases"/current_version,current_version,module)
            print(f"{module} {conf['label']}：已核验旧正式版 {current_version}，新版本 {conf['version']}。")
            print("仅升级本模块程序；其它模块、V2Ray 服务、系统更新和 CloudPanel 均不自动执行。")
            if not sys.stdin.isatty() or not sys.stdout.isatty():
                blocked("升级需要在交互式 SSH 中由本人确认")
            answer=input("确认仅升级本模块？[y/N]：").strip()
            if answer.lower()!="y":blocked("已取消，本次无写入")
        if os.geteuid()!=0:blocked("首次安装或升级必须使用 root")
        zipfile=temp/conf["filename"]
        fetch("https://github.com/"+REPO+"/releases/download/"+RELEASE+"/"+conf["filename"],
              zipfile,conf["sha"])
        # Prevent a stale confirmation after concurrent system changes.
        if validate_paths(home)!=current_version:
            blocked("下载期间旧版本指针发生变化")
        if current_version:
            installer.verify_saved(home/"releases"/current_version,current_version,module)
        target_version=installer.install(module,zipfile,conf["sha"])
        if target_version!=conf["version"]:blocked("原子安装后的版本未达到目标")
    verified_new(home,module,conf)
    print(f"{module} {conf['label']}：独立 UX 新版已就绪，未修改其它模块。")
    return 0
if __name__=="__main__":
    try:raise SystemExit(main())
    except (Blocked,OSError,ValueError,KeyError,TimeoutError,subprocess.SubprocessError) as e:
        print("P07 独立 UX 升级已安全停止："+str(e),file=sys.stderr)
        raise SystemExit(13)
