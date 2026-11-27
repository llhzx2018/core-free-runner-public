#!/usr/bin/env python3
"""P07-M01 independent, unpublished UX4 candidate builder/installer.

Uses the unchanged, pinned P07 atomic engine and exact official predecessor
identity. This development checkout is not the anonymous distribution route.
No node deployment, service start, external proxy configuration or release.
"""
from __future__ import annotations
import argparse, fcntl, hashlib, importlib.util, json, os, stat, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MODULE="P07-M01"
SLOT="m01"
LABEL="网络代理节点（V2Ray）"
ENTRY="vf-node.sh"
OLD="0.1.0-ux3"
NEW="0.1.0-ux4"
OLD_META="b52b2d17095bc9e84567319a71fa19a8822bd6bb696bac3dfccd85d80923d6ab"
OLD_SHA="13e79e7c7a4f1170c74da24e783804c3c2bda06fe6c46b768497694e826b3ed7"
OVERLAY={"vf-node.sh":"68e8a61d9374cda0c735c6e8c21aea24649666d8","lib/common.sh":"f34f11099683106af71954060e151814c754b66d"}
OVERLAY_ROOT=ROOT/"packages/p07-network-node/0.1.0-ux4"
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
    builder=load("m01_candidate_builder",BUILDER)
    prior=builder.build_payload(MODULE,LABEL,OLD,ENTRY,builder.dev.make_m01)
    need(sha(prior["MODULE_MANIFEST.json"])==OLD_META,"旧版不是准确的官方发行内容")
    need(prior["MODULE_MANIFEST.json"]==manifest(OLD,prior),"旧版清单不一致")
    files={n:b for n,b in prior.items() if n!="MODULE_MANIFEST.json"}
    for name,digest in OVERLAY.items(): files[name]=pinned(OVERLAY_ROOT/name,digest)
    files["VERSION"]=(NEW+"\n").encode()
    identity=files["SOURCE_IDENTITY"].decode()
    old_line="P07_NETWORK_NODE_VERSION="+OLD+"\n"
    need(identity.count(old_line)==1,"旧节点源身份不一致")
    files["SOURCE_IDENTITY"]=(identity.replace(old_line,"P07_NETWORK_NODE_VERSION="+NEW+"\n",1)
                              +"CANDIDATE_SOURCE_ONLY=YES\nFORMAL_RELEASE=NO\n").encode()
    files["MANIFEST.sha256"]="".join(f"{sha(b)}  {n}\n" for n,b in sorted(files.items())
                                    if n!="MANIFEST.sha256").encode()
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
    engine=load("m01_pinned_atomic",ENGINE)
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
    parser=argparse.ArgumentParser(description="M01 UX4 DEV 独立安装候选")
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
        print("M01 独立候选操作安全停止："+type(exc).__name__,file=sys.stderr)
        return 13
if __name__=="__main__":raise SystemExit(main())
