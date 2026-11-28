#!/usr/bin/env python3
"""P07-M04 independent, unpublished UX6 candidate builder/installer.

Uses the unchanged, pinned P07 atomic engine and exact official predecessor
identity. This development checkout is not the anonymous distribution route.
No APT mutation, system service change, CloudPanel operation or release.
"""
from __future__ import annotations
import argparse, fcntl, hashlib, importlib.util, json, os, stat, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MODULE="P07-M04"
SLOT="m04"
LABEL="服务器维护与安全"
ENTRY="vf-system-care.sh"
OLD="0.1.0-ux5"
NEW="0.1.0-ux6"
OLD_META="370385aab38b4b8f4c069e40ed59fa8d5c6454d65c7982925d0fb123404eb0d7"
OLD_SHA="2ff45c263f930e258a3c323b6c009e0973531d3f90a2e432a66aed704c9baa7d"
OVERLAY={"vf-system-care.sh":"f654cb3092d314f97efd91823fab32b70b1fc638","lib/common.sh":"3ba600e9febd4b7570847d0ac1e887019c7f53e8","updates.sh":"52da66b997f65f563b5365388c35e27d0339dd5f"}
OVERLAY_ROOT=ROOT/"packages/p07-system-care/0.1.0-ux6"
BASE=Path("/opt/vfops-modules")
ENGINE="installers/p07-three-ux-atomic.py"
BUILDER="scripts/build_p07_ux_three_release_candidates.py"
DEV="scripts/build_p07_ux_prepublication_candidates.py"
PINS={ENGINE:"9fc4ecfab8bca665ccde238f0e40631657205f82",
      BUILDER:"116f10167722b14842065317a18437d2dbd24627",
      DEV:"c8efd4176b64d6bc2ad065340c2a78be28e0c723"}

class Blocked(Exception): pass
def need(ok,message):
    if not ok: raise Blocked(message)
def sha(data): return hashlib.sha256(data).hexdigest()
def blob(data): return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
def pinned(path,digest):
    need(path.is_file() and not path.is_symlink(),"候选依赖缺失或不安全")
    data=path.read_bytes()
    need(blob(data)==digest,"候选依赖身份不符")
    return data
def load(name,rel):
    path=ROOT/rel
    pinned(path,PINS[rel])
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def manifest(build,files):
    meta={"schema":"vf.p07.ux.module-bundle.v1","module_id":MODULE,"module_name":LABEL,
          "module_build_id":build,"entrypoint":ENTRY,"installation_isolation":MODULE+"_ONLY",
          "files":{n:sha(b) for n,b in files.items() if n!="MODULE_MANIFEST.json"}}
    return (json.dumps(meta,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode()

def payloads():
    pinned(ROOT/DEV,PINS[DEV])
    builder=load("m04_candidate_builder",BUILDER)
    prior=builder.build_payload(MODULE,LABEL,OLD,ENTRY,builder.dev.make_m04)
    need(sha(prior["MODULE_MANIFEST.json"])==OLD_META,"旧版不是准确的官方发行内容")
    need(prior["MODULE_MANIFEST.json"]==manifest(OLD,prior),"旧版清单不一致")
    files={n:b for n,b in prior.items() if n!="MODULE_MANIFEST.json"}
    for name,digest in OVERLAY.items(): files[name]=pinned(OVERLAY_ROOT/name,digest)
    files["VERSION"]=(NEW+"\n").encode()
    files["MANIFEST.gitblob"]="".join(f"{blob(b)}  {n}\n" for n,b in sorted(files.items())
                                     if n!="MANIFEST.gitblob").encode()
    files["MODULE_MANIFEST.json"]=manifest(NEW,files)
    return builder,prior,files

def verify_saved(root,build,expected):
    need(root.is_dir() and not root.is_symlink(),"版本目录异常")
    actual={}
    for p in root.rglob("*"):
        need(not p.is_symlink(),"版本中存在符号链接")
        if p.is_dir(): continue
        st=p.lstat()
        need(stat.S_ISREG(st.st_mode) and st.st_nlink==1,"版本中存在特殊文件或硬链接")
        actual[p.relative_to(root).as_posix()]=p.read_bytes()
    need(actual==expected,"版本身份或文件内容不一致")

def paths_safe(base):
    for p in (base,base/SLOT,base/SLOT/"releases"):
        if not os.path.lexists(p): continue
        st=p.lstat()
        need(stat.S_ISDIR(st.st_mode) and st.st_uid==0 and not st.st_mode&0o022,"模块目录不安全")
    lock=base/SLOT/".install.lock"
    if os.path.lexists(lock):
        st=lock.lstat()
        need(stat.S_ISREG(st.st_mode) and st.st_uid==0 and st.st_nlink==1 and not st.st_mode&0o022,
             "模块锁不安全")

def engine_for(base,prior,files):
    engine=load("m04_pinned_atomic",ENGINE)
    engine.BASE=base
    engine.CONFIG={MODULE:(SLOT,LABEL,ENTRY,NEW,OLD)}
    def verify(root,build,module):
        need(module==MODULE and build in (OLD,NEW),"模块身份不符")
        verify_saved(root,build,prior if build==OLD else files)
    engine.verify_saved=verify
    original=engine.read_package
    def exact_read(archive,checksum,module):
        build,payload=original(archive,checksum,module)
        need(build==NEW and payload==files,"拒绝未知或重新封装的候选")
        return build,payload
    engine.read_package=exact_read
    return engine

def install(engine,archive,checksum):
    paths_safe(engine.BASE)
    return engine.install(MODULE,archive,checksum)

def rollback(engine,confirmation):
    need(os.geteuid()==0 and confirmation==MODULE+":"+OLD,"回滚需要正确确认")
    paths_safe(engine.BASE)
    home=engine.BASE/SLOT
    need(home.is_dir() and (home/"releases").is_dir(),"模块尚未安装")
    fd=os.open(home/".install.lock",os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW|os.O_NONBLOCK,0o600)
    with os.fdopen(fd,"w") as lock:
        st=os.fstat(lock.fileno())
        need(stat.S_ISREG(st.st_mode) and st.st_uid==0 and st.st_nlink==1,"模块锁不安全")
        fcntl.flock(lock,fcntl.LOCK_EX)
        current,now=engine.current_state(home,MODULE)
        need(now in (OLD,NEW),"当前版本异常")
        engine.verify_saved(home/"releases"/OLD,OLD,MODULE)
        if now!=OLD: engine.switching(home,current,OLD)
    return OLD

def main():
    parser=argparse.ArgumentParser(description="M04 UX6 DEV 独立安装候选")
    sub=parser.add_subparsers(dest="command",required=True)
    b=sub.add_parser("build");b.add_argument("output",type=Path)
    p=sub.add_parser("install");p.add_argument("archive",type=Path);p.add_argument("sha256")
    q=sub.add_parser("rollback");q.add_argument("--confirm",required=True)
    args=parser.parse_args()
    try:
        builder,prior,files=payloads()
        if args.command=="build":
            out=args.output.resolve()
            need(ROOT not in out.parents and out!=ROOT,"候选包必须写入独立目录")
            print("DEV_ONLY_SHA256="+builder.output_zip(out,MODULE,files)); return 0
        engine=engine_for(BASE,prior,files)
        result=install(engine,args.archive,args.sha256) if args.command=="install" else rollback(engine,args.confirm)
        print(MODULE+" 独立候选版本 "+result+"；其他模块未改变。")
        return 0
    except Exception as exc:
        print("M04 独立候选操作安全停止："+type(exc).__name__,file=sys.stderr)
        return 13
if __name__=="__main__":raise SystemExit(main())
