#!/usr/bin/env python3
"""Public M02-only route for the already issued UX4 archive; no server benchmark on install."""
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
SOURCE="76c46e042f19d9a289ef31b1c16db2caba837f63"
RELEASE="p07-m02-v2.1.1-ux4-20261128"
MODULE="P07-M02"
LIMIT=8*1024*1024
BASE=Path("/opt/vfops-modules")
CONF=dict(slot="m02",version="2.1.1-ux4",previous="2.1.1-ux3",
    filename="P07-M02-2.1.1-ux4.zip",
    sha="1cae35bf31f119ae1ad891df4846503bbea45745ad8ac55678b666a35aaa35ad",
    meta="1663d325fc2781c949d81c95ea84ef14ba31d23c37cd1c7d3674bc8f15bef92a",
    entry="vps-audit.sh",label="服务器性能检测（VPS 验机）")
INSTALLERS={
    "p07-m02-ux4-atomic.py":"c90ceb89655010b192f400839f218890727ddd5d",
    "p07-three-ux-atomic.py":"9fc4ecfab8bca665ccde238f0e40631657205f82",
}

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
    if result.returncode or ((module=="P07-M02" and "V2.1.1" not in result.stdout) or
                             (module!="P07-M02" and conf["version"] not in result.stdout)):
        blocked("新版入口版本检查失败")
    if module=="P07-M02":
        result=subprocess.run(["bash",str(entry),"--build-id"],capture_output=True,text=True,timeout=12)
        if result.returncode or result.stdout.strip()!=conf["version"]:
            blocked("验机程序构建身份错误")


def get_candidate(temp):
    for name,digest in INSTALLERS.items():
        fetch("https://raw.githubusercontent.com/"+REPO+"/"+SOURCE+"/installers/"+name,
              temp/name,digest,"gitblob")
    path=temp/"p07-m02-ux4-atomic.py"
    spec=importlib.util.spec_from_file_location("p07_m02_exact_installer",path)
    candidate=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(candidate)
    return candidate

def main():
    if len(sys.argv)!=2 or sys.argv[1]!=MODULE:
        blocked("仅可从工具箱进入指定模块")
    conf=CONF
    home=BASE/conf["slot"]
    prior=validate_paths(home)
    if prior==conf["version"]:
        verified_new(home,MODULE,conf)
        return 0
    if prior is not None and prior!=conf["previous"]:
        blocked("当前安装不在本轮已验证升级范围；旧程序保留")
    if os.geteuid()!=0:
        blocked("首次安装或升级必须使用 root")
    with tempfile.TemporaryDirectory(prefix="p07-m02-ux4-official-") as raw:
        temp=Path(raw)
        c=get_candidate(temp)
        try:
            engine=c.engine_for(BASE)
            if prior:
                c.verify_saved(home/"releases"/prior,prior,MODULE)
        except c.Blocked as error:
            blocked(str(error))
        if prior:
            print(f"{MODULE} {conf['label']}：已核验旧正式版 {prior}，新版本 {conf['version']}。")
            print("仅升级本模块程序；其它模块、V2Ray 服务、系统更新和 CloudPanel 均不自动执行。")
            if not sys.stdin.isatty() or not sys.stdout.isatty():
                blocked("升级需要在交互式 SSH 中由本人确认")
            try:
                answer=input("确认仅升级本模块？[y/N]：").strip()
            except EOFError:
                blocked("终端已关闭输入；本次未确认升级，原模块不变")
            if answer.lower()!="y":
                blocked("已取消，本次无写入")
        archive=temp/conf["filename"]
        fetch("https://github.com/"+REPO+"/releases/download/"+RELEASE+"/"+conf["filename"],archive,conf["sha"])
        if validate_paths(home)!=prior:
            blocked("下载期间旧版本指针发生变化")
        # Compare the confirmed origin again inside the original install lock.
        current_state=engine.current_state
        def guarded_current_state(root,module):
            current,actual=current_state(root,module)
            if actual!=prior:
                blocked("安装锁内的版本指针与确认时不符")
            return current,actual
        engine.current_state=guarded_current_state
        try:
            installed=engine.install(MODULE,archive,conf["sha"])
        except (c.Blocked,engine.Rejected) as error:
            blocked(str(error))
        if installed!=conf["version"]:
            blocked("原子安装后的版本未达到目标")
    verified_new(home,MODULE,conf)
    print(f"{MODULE} {conf['label']}：独立 UX 新版已就绪，未修改其它模块。")
    return 0

if __name__=="__main__":
    try:
        raise SystemExit(main())
    except (Blocked,OSError,ValueError,KeyError,RuntimeError,TimeoutError,subprocess.SubprocessError) as e:
        print("P07 独立 UX 升级已安全停止："+str(e),file=sys.stderr)
        raise SystemExit(13)
