"""Actual public HTTPS / PTY distribution proof on a disposable hosted runner only."""
import hashlib
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
TOOL=ROOT/"installers/p07-toolbox.sh"
ROUTE=ROOT/"installers/p07-m02-ux4-owner-route.py"
BASE=Path("/opt/vfops-modules")
M03=Path("/opt/vf-server-ops")
HOME=BASE/"m02"
OLD="2.1.1-ux3"
NEW="2.1.1-ux4"
OLD_SHA="88da5b8219fb7e04d606eb3de998d872747cb05153bdd93c7351b46f957164b4"
OLD_URL="https://github.com/llhzx2018/core-free-runner-public/releases/download/p07-all-ux-v0.1.0-20261118/P07-M02-2.1.1-ux3.zip"
ENV=dict(os.environ,NO_COLOR="1",TERM="dumb",PYTHONDONTWRITEBYTECODE="1")

def run(argv,data=b"",expected=0):
    p=subprocess.run(argv,input=data,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=ENV,timeout=180)
    out=p.stdout.decode("utf-8",errors="replace")
    assert p.returncode==expected,(p.returncode,out)
    return out

def tty(argv,data,expected=0):
    return run(["script","-qfec","stty cols 80 rows 24; "+shlex.join(map(str,argv)),"/dev/null"],data,expected)

def current(version):
    assert os.readlink(HOME/"current")=="releases/"+version
    assert run(["bash",str(HOME/"current/vps-audit.sh"),"--build-id"]).strip()==version

def tree(root):
    return [(str(p.relative_to(root)),p.lstat().st_mode,os.readlink(p) if p.is_symlink()
             else hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "")
            for p in sorted(root.rglob("*"))]

def test_actual_public_route():
    assert os.geteuid()==0 and os.environ.get("GITHUB_ACTIONS")=="true"
    assert os.environ.get("RUNNER_ENVIRONMENT")=="github-hosted"
    assert os.environ.get("GITHUB_REPOSITORY")=="llhzx2018/core-free-runner-public"
    assert not BASE.exists() and not BASE.is_symlink()
    assert not M03.exists() and not M03.is_symlink()
    BASE.mkdir()
    try:
        M03.mkdir()
        siblings=[BASE/"m01",BASE/"m04",BASE/"m05",M03]
        for p in siblings:
            p.mkdir(exist_ok=True)
            (p/"untouched").write_text("fixture:"+p.name)
            (p/"untouched").chmod(0o640)
        before=[tree(p) for p in siblings]
        with tempfile.TemporaryDirectory() as td:
            old=Path(td)/"old.zip"
            run(["curl","--proto","=https","--tlsv1.2","-fsSL","--max-time","90",OLD_URL,"-o",str(old)])
            assert hashlib.sha256(old.read_bytes()).hexdigest()==OLD_SHA
            run(["python3","-B",str(ROOT/"installers/p07-three-ux-atomic.py"),"P07-M02","install",str(old),OLD_SHA])
            current(OLD)
            saved=tree(HOME)
            old_tree=tree(HOME/"releases"/OLD)
            out=run(["bash",str(TOOL),"--modules"])
            assert OLD in out and tree(HOME)==saved
            out=tty(["bash",str(TOOL)],b"2\nn\n\n0\n")
            assert "已取消" in out and "确认仅升级本模块" in out
            assert tree(HOME)==saved
            for data in (b"x\n",b"\x04"):
                out=tty(["python3","-B",str(ROUTE),"P07-M02"],data,13)
                assert "安全停止" in out and tree(HOME)==saved
            out=run(["python3","-B",str(ROUTE),"P07-M02"],b"y\n",13)
            assert "交互式 SSH" in out and tree(HOME)==saved
            file=HOME/"current/vps-audit.sh"
            original=file.read_bytes()
            file.write_bytes(original+b"\n# damaged fixture\n")
            damaged=tree(HOME)
            out=run(["python3","-B",str(ROUTE),"P07-M02"],b"",13)
            assert "安全停止" in out and "Traceback" not in out and tree(HOME)==damaged
            file.write_bytes(original)
            assert tree(HOME)==saved
            out=tty(["bash",str(TOOL)],b"2\ny\n0\n\n0\n")
            assert "确认仅升级本模块" in out and "独立 UX 新版已就绪" in out
            current(NEW)
            assert tree(HOME/"releases"/OLD)==old_tree
            assert hashlib.sha256((HOME/"current/MODULE_MANIFEST.json").read_bytes()).hexdigest()=="1663d325fc2781c949d81c95ea84ef14ba31d23c37cd1c7d3674bc8f15bef92a"
            saved=tree(HOME)
            out=tty(["bash",str(TOOL)],b"2\n0\n\n0\n")
            assert "确认仅升级本模块" not in out and tree(HOME)==saved
            assert NEW in run(["bash",str(TOOL),"--modules"])
            run(["bash",str(TOOL),"--rollback-m02",OLD,"incorrect"],expected=13)
            assert tree(HOME)==saved
            run(["bash",str(TOOL),"--rollback-m02",OLD,"P07-M02:"+OLD])
            current(OLD)
            out=tty(["bash",str(TOOL)],b"2\ny\n0\n\n0\n")
            assert "独立 UX 新版已就绪" in out
            current(NEW)
            shutil.rmtree(HOME)
            out=tty(["bash",str(TOOL)],b"2\n0\n\n0\n")
            assert "独立 UX 新版已就绪" in out
            current(NEW)
            assert [tree(p) for p in siblings]==before
            print("M02_PUBLIC_DISTRIBUTION=PASS actual anonymous UX3->UX4; cancel/EOF/invalid/nonTTY/tamper; rollback/reupgrade; fresh install; four siblings unchanged")
    finally:
        shutil.rmtree(BASE)
        if M03.exists(): shutil.rmtree(M03)

if __name__=="__main__":
    test_actual_public_route()
