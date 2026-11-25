#!/usr/bin/env python3
"""Public RC4 maintenance route. Real tests require a disposable hosted runner.
No production access; the only substituted interface is prepublication download transport.
"""
import hashlib
import json
import os
from pathlib import Path
import py_compile
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest
import zipfile

REPO=Path(__file__).resolve().parents[1]
TOOLBOX=REPO/"installers/p07-toolbox.sh"
WRAPPER=REPO/"installers/p07-m03-ownertrial147rc4-atomic.sh"
OLD="0.1.0-release147-rc3"
NEW="0.1.0-release147-rc4"
OLD_SHA="3646285a2732c8249d0296a72c7ce6fae83be1e9564d76849e65bc396642672d"
NEW_SHA="ef6e8731c4b0a7501d2fe55f18f86a74f374d03ad0e7030709b3120a7b13f1e7"
ROOT=Path("/opt/vf-server-ops-ownertrial147rc3")
PREV=Path(str(ROOT)+".previous")
NEWROOT=Path(str(ROOT)+".new")
LOCK=Path(str(ROOT)+".upgrade.lock")
BIN=Path("/usr/local/bin/vfops-rc147rc3")
STABLE=Path("/opt/vf-server-ops")
SIBLINGS=Path("/opt/vfops-modules")
STATE=Path("/var/lib/vf-server-ops")
TAG="p07-m03-v0.1.0-release147-rc4-maintenance-20261125"
NAME="P07-M03-0.1.0-release147-rc4-MAINTENANCE.zip"
BASE="https://github.com/llhzx2018/core-free-runner-public/releases/download/"
RAW="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main/installers/p07-m03-ownertrial147rc4-atomic.sh"
API="https://api.github.com/repos/llhzx2018/core-free-runner-public/releases/"
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def blob(p):
    d=p.read_bytes()
    return hashlib.sha1(b"blob "+str(len(d)).encode()+b"\0"+d).hexdigest()
def exists(p): return p.exists() or p.is_symlink()
def fingerprint(p):
    if not exists(p): return None
    if p.is_symlink(): return ("link",os.readlink(p))
    if p.is_file(): return ("file",digest(p))
    return tuple((x.relative_to(p).as_posix(),("link",os.readlink(x)) if x.is_symlink() else ("file",digest(x)) if x.is_file() else ("dir",)) for x in sorted(p.rglob("*")))
class PublicContract(unittest.TestCase):
    def test_exact_pins_and_scope(self):
        t=TOOLBOX.read_text(); w=WRAPPER.read_text()
        self.assertIn('M03_OWNER_TRIAL_INSTALLER_BLOB="'+blob(WRAPPER)+'"',t)
        self.assertIn('VF_SERVER_OPS_BUILD_EXPECTED="0.1.0-release146"',t)
        self.assertIn('M03_OWNER_TRIAL_PREVIOUS_BUILD="'+OLD+'"',t)
        self.assertIn('M03_OWNER_TRIAL_BUILD="'+NEW+'"',t)
        self.assertIn("ZIP_SHA256='"+NEW_SHA+"'",w)
        self.assertIn("RUNTIME_BLOB='980ef2b84b521f41b1d2ca51fa09ac5c83ecaea9'",w)
        self.assertIn("INSTALLER_BLOB='33556a8df5c5c0903613ecc42077d9292ca22cfc'",w)
        self.assertIn("P07_M03_EXPECTED_SOURCE=",t)
        for f in (TOOLBOX,WRAPPER):
            self.assertEqual(subprocess.run(["bash","-n",str(f)]).returncode,0)
    def test_readonly_main_menu_and_no_color(self):
        p=subprocess.run(["bash",str(TOOLBOX),"--help"],capture_output=True,text=True,timeout=10,env={**os.environ,"NO_COLOR":"1"})
        self.assertEqual(p.returncode,0)
        self.assertNotIn("\x1b",p.stdout)
        for s in ("网络代理节点","服务器性能检测","网站与数据","服务器维护与安全","新服务器初始化"):
            self.assertIn(s,p.stdout)
        p=subprocess.run(["bash",str(TOOLBOX)],input="3\n2\ny\n",capture_output=True,text=True,timeout=10)
        self.assertEqual(p.returncode,2)
        self.assertIn("交互式终端",p.stderr)

@unittest.skipUnless(os.environ.get("P07_RC4_REAL_ENTRY")=="1","explicit disposable hosted real-entry run only")
class RealEntry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS")!="true" or os.environ.get("RUNNER_ENVIRONMENT")!="github-hosted" or os.geteuid()!=0:
            raise RuntimeError("real entry requires isolated GitHub-hosted root runner")
        cls.paths=(ROOT,PREV,NEWROOT,LOCK,BIN,STABLE,SIBLINGS,STATE)
        if any(exists(p) for p in cls.paths):
            raise RuntimeError("refuse existing runtime/state on runner")
        cls.old=Path(os.environ["P07_RC3_ZIP"]).resolve()
        cls.new=Path(os.environ["P07_RC4_ZIP"]).resolve()
        if digest(cls.old)!=OLD_SHA or digest(cls.new)!=NEW_SHA: raise RuntimeError("package identity mismatch")
    def setUp(self):
        if any(exists(p) for p in self.paths): self.fail("unexpected residue")
        self.tmp=tempfile.TemporaryDirectory(prefix="p07-rc4-public-real-")
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.clean_owned)
        self.work=Path(self.tmp.name)
        self.log=self.work/"transport.log"
        self.shim=self.work/"bin"; self.shim.mkdir()
        self.env={**os.environ,"NO_COLOR":"1","PYTHONDONTWRITEBYTECODE":"1","PATH":str(self.shim)+":"+os.environ["PATH"],"VF_TEST_LOG":str(self.log),"VF_TEST_WRAPPER":str(WRAPPER),"VF_TEST_ZIP":str(self.new)}
        self.env.pop("P07_PUBLIC_ROOT",None)
        for p in (STABLE, SIBLINGS, STATE):
            p.mkdir()
        for s in ("m01","m02","m04","m05"):
            q=SIBLINGS/s; q.mkdir(); (q/"KEEP").write_text(s+" unchanged")
        (STABLE/"BUILD_ID").write_text("0.1.0-release146\n")
        (STATE/"old-22-task-fixture").write_text("immutable historical fixture")
        self.sentinels={p:fingerprint(p) for p in (STABLE,SIBLINGS,STATE)}
        self.write_transport()
    def clean_owned(self):
        for p in self.paths:
            if p.is_symlink() or p.is_file(): p.unlink()
            elif p.is_dir(): shutil.rmtree(p)
    def preserve(self):
        for p,v in self.sentinels.items(): self.assertEqual(fingerprint(p),v,str(p))
    def write_transport(self):
        # Test-only transport: exact candidate bytes; no assertion of issued remote assets.
        source=r"""#!/usr/bin/env python3
import json,os,pathlib,shutil,sys
a=sys.argv[1:]
url=next((x for x in a if x.startswith(("https://","file://"))),"")
if url.startswith("file://"):
    os.execv("/usr/bin/curl",["curl",*a])
if "-o" not in a: sys.exit(97)
dst=pathlib.Path(a[a.index("-o")+1])
with open(os.environ["VF_TEST_LOG"],"a") as f: f.write(url+"\n")
raw=RAW_URL
zipurl=ZIP_URL
api=API_URL
tag=TAG_NAME
name=ASSET_NAME
mode=os.environ.get("VF_TEST_TRANSPORT","normal")
if url==raw:
    if mode=="bad-wrapper": dst.write_text("#!/bin/bash\nexit 0\n")
    else: shutil.copyfile(os.environ["VF_TEST_WRAPPER"],dst)
elif url==zipurl:
    if mode in ("fallback","bad-meta"): sys.exit(22)
    if mode=="bad-zip": dst.write_bytes(b"corrupt test artifact")
    else: shutil.copyfile(os.environ["VF_TEST_ZIP"],dst)
elif url==api+"tags/"+tag:
    dst.write_text(json.dumps({"tag_name":tag,"draft":False,"assets":[{"name":name,"browser_download_url":zipurl,"size":719273 if mode!="bad-meta" else 1,"state":"uploaded","id":123456789}]}))
elif url==api+"assets/123456789" and mode=="fallback":
    shutil.copyfile(os.environ["VF_TEST_ZIP"],dst)
else:
    sys.exit(98)
"""
        for key,value in (("RAW_URL",RAW),("ZIP_URL",BASE+TAG+"/"+NAME),("API_URL",API),("TAG_NAME",TAG),("ASSET_NAME",NAME)):
            source=source.replace(key,repr(value))
        p=self.shim/"curl";p.write_text(source);p.chmod(0o755)
    def install_old(self,caches=False):
        olddir=self.work/"old";olddir.mkdir()
        with zipfile.ZipFile(self.old) as z: z.extractall(olddir)
        e={**self.env,"P07_PUBLIC_ROOT":olddir.as_uri(),"P07_INSTALL_DIR":str(ROOT),"P07_PREVIOUS_DIR":str(PREV),"P07_BIN_LINK":str(BIN),"P07_NO_EXEC":"1","P07_ALLOW_NONROOT":"1"}
        p=subprocess.run(["bash",str(olddir/"installers/p07-final.sh")],env=e,capture_output=True,text=True,timeout=120)
        self.assertEqual(p.returncode,0,"original installer failed "+p.stderr[-500:])
        self.assertEqual((ROOT/"BUILD_ID").read_text().strip(),OLD)
        if caches:
            with zipfile.ZipFile(self.new) as z:
                for name in ("policy.py","ux.py"):
                    (ROOT/"lib"/name).write_bytes(z.read("dist/p07/0.1.0/overlay/lib/"+name))
            # RC3's signed manifest owns cache source identities. The two
            # allowed extra source files are not signed cache sources.
            signed={line.split("  ",1)[1] for line in (ROOT/".runtime-manifest.gitblob").read_text().splitlines()}
            cache_sources=[p for p in sorted((ROOT/"lib").glob("*.py")) if p.relative_to(ROOT).as_posix() in signed]
            self.assertNotIn(ROOT/"lib/policy.py",cache_sources)
            self.assertNotIn(ROOT/"lib/ux.py",cache_sources)
            options=[(p,k) for k in (0,1) for p in cache_sources]
            self.assertGreaterEqual(len(options),66)
            for p,k in options[:66]: py_compile.compile(str(p),optimize=k,doraise=True)
            self.assertEqual(len(list((ROOT/"lib/__pycache__").glob("*.pyc"))),66)
        self.log.unlink(missing_ok=True)
    def entry(self,answer="y",mode="normal",extra=None,expect_block=False):
        env={**self.env,"VF_TEST_TRANSPORT":mode,**(extra or {})}
        # The exact public toolbox runs on a real pseudo-terminal, then selects 3/2.
        # 0 exits the authenticated child on success; blank acknowledges failure.
        commands="3\n2\n"+answer+"\n0\n0\n0\n"
        p=subprocess.run(["script","-qefc","bash "+shlex.quote(str(TOOLBOX)),"/dev/null"],input=commands,text=True,capture_output=True,env=env,timeout=180)
        output=p.stdout+p.stderr
        self.preserve()
        markers=re.findall(r"RC3_UPGRADE_PROVENANCE_BLOCKED=[^\r\n]+|错误阶段：[A-Z_]+|试用安装器身份/语法验证失败|试用包安装失败|原运行时归属或完整性无法确认|已有试用目录、恢复点或命令身份未确认|独立维护程序已就绪",output)
        diagnostic="exit="+str(p.returncode)+" markers="+repr(markers)
        self.assertEqual(p.returncode,0,"menu did not return safely: "+diagnostic)
        if expect_block:
            self.assertNotIn("独立维护程序已就绪",output)
            self.assertTrue(any("失败" in m or "BLOCKED" in m or "未确认" in m or "错误阶段" in m for m in markers),diagnostic)
        return output
    def unchanged(self,before):
        self.assertEqual(fingerprint(ROOT),before)
        self.assertFalse(exists(PREV))
        self.assertFalse(exists(NEWROOT))
        self.preserve()
    def test_real_public_upgrade_legacy_caches_and_reentry(self):
        self.install_old(caches=True); before=fingerprint(ROOT)
        output=self.entry()
        self.assertIn("独立维护程序已就绪",output,"LEGACY_CACHE_UPGRADE: "+repr(re.findall(r"RC3_UPGRADE_PROVENANCE_BLOCKED=[^\r\n]+|错误阶段：[A-Z_]+|原运行时归属或完整性无法确认",output)))
        self.assertEqual((ROOT/"BUILD_ID").read_text().strip(),NEW)
        self.assertEqual(fingerprint(PREV),before)
        self.assertEqual(os.readlink(BIN),str(ROOT/"bin/vfops-user"))
        self.assertIn(RAW,self.log.read_text())
        self.assertIn(BASE+TAG+"/"+NAME,self.log.read_text())
        self.log.unlink()
        output=self.entry(answer="0")
        self.assertIn("无须重新下载",output)
        self.assertFalse(self.log.exists())
        self.assertEqual(fingerprint(PREV),before)
    def test_real_public_fresh_install(self):
        output=self.entry()
        self.assertIn("独立维护程序已就绪",output)
        self.assertEqual((ROOT/"BUILD_ID").read_text().strip(),NEW)
        self.assertFalse(exists(PREV))
    def test_real_public_fresh_install_and_no_color(self):
        output=self.entry()
        self.assertEqual((ROOT/"BUILD_ID").read_text().strip(),NEW)
        self.assertFalse(exists(PREV))
        # Never accept screen clear sequences in NO_COLOR. Report only
        # escape sequence identities rather than dumping the runtime transcript.
        escapes=re.findall(r"\x1b\[[0-9;]*[A-Za-z]",output)
        self.assertNotIn("\x1b", "".join(escapes), "NO_COLOR_CONTROL_SEQUENCES="+repr(escapes))
    def test_cancel_and_invalid_confirmation(self):
        self.install_old(); before=fingerprint(ROOT)
        for a in ("n","invalid",""):
            output=self.entry(answer=a)
            self.assertIn("已取消",output)
            self.assertFalse(self.log.exists())
            self.unchanged(before)
    def test_bad_wrapper_and_bad_zip_rejected(self):
        self.install_old(); before=fingerprint(ROOT)
        for mode in ("bad-wrapper","bad-zip","bad-meta"):
            self.entry(mode=mode,expect_block=True); self.unchanged(before)
    def test_fallback_transport_real_bytes(self):
        self.install_old()
        output=self.entry(mode="fallback")
        self.assertIn("独立维护程序已就绪",output)
        self.assertIn(API+"assets/123456789",self.log.read_text())
        self.assertEqual((ROOT/"BUILD_ID").read_text().strip(),NEW)
    def test_unknown_identity_and_symlink_rejected_without_download(self):
        self.install_old()
        marker=ROOT/"BUILD_ID"; marker.write_text("UNKNOWN\n")
        before=fingerprint(ROOT)
        self.entry(expect_block=True);self.unchanged(before);self.assertFalse(self.log.exists())
        marker.write_text(OLD+"\n")
        mf=ROOT/".runtime-manifest.gitblob"; original=mf.read_bytes(); mf.unlink()
        other=self.work/"manifest";other.write_bytes(original);mf.symlink_to(other)
        before=fingerprint(ROOT)
        self.entry(expect_block=True);self.unchanged(before);self.assertFalse(self.log.exists())
    def test_unknown_extra_source_and_preexisting_rollback_slot(self):
        self.install_old()
        x=ROOT/"lib/unknown-source.py";x.write_text("raise RuntimeError('never execute')")
        before=fingerprint(ROOT)
        self.entry(expect_block=True); self.unchanged(before); x.unlink()
        PREV.mkdir();(PREV/"KEEP").write_text("do not rotate")
        old=fingerprint(ROOT);prev=fingerprint(PREV)
        self.entry(expect_block=True)
        self.assertEqual(fingerprint(ROOT),old)
        self.assertEqual(fingerprint(PREV),prev)
        self.preserve()
    def test_actual_swap_failure_rolls_back(self):
        self.install_old();before=fingerprint(ROOT)
        p=self.shim/"mv"
        p.write_text('#!/bin/sh\nif [ "$1" = "$P07_INSTALL_DIR.new" ]; then exit 77; fi\nexec /usr/bin/mv "$@"\n')
        p.chmod(0o755)
        output=self.entry(expect_block=True)
        self.assertIn("安装失败",output)
        self.unchanged(before)
    def test_unsigned_extra_cache_is_rejected_not_run(self):
        self.install_old()
        with zipfile.ZipFile(self.new) as z:
            extra=ROOT/"lib/policy.py"
            extra.write_bytes(z.read("dist/p07/0.1.0/overlay/lib/policy.py"))
        py_compile.compile(str(extra),doraise=True)
        before=fingerprint(ROOT)
        output=self.entry(expect_block=True)
        self.assertIn("RC3 bytecode source unsigned",output)
        self.unchanged(before)
if __name__=="__main__": unittest.main()
