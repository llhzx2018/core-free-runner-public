"""P07 5 modules: one disposable-host coexistence test, four unaffected on each upgrade.

Only on GitHub-hosted ephemeral ubuntu-24.04, exact private M05 checkout is
temporary and NEVER published. Does not install V2Ray nodes, CloudPanel,
change website data, run VPS migration or modify Owner production.
"""
from __future__ import annotations

import hashlib
import importlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
PRODUCT=ROOT/"product"
MODULES=Path("/opt/vfops-modules")
TARGETS={
    "M01 网络代理节点（V2Ray）":MODULES/"m01",
    "M02 服务器性能检测（VPS 验机）":MODULES/"m02",
    "M03 网站与数据":Path("/opt/vf-server-ops"),
    "M04 服务器维护与安全":MODULES/"m04",
    "M05 新服务器初始化":MODULES/"m05",
}
M01_INSTALLER_REF="9f5c0d7362cfc766958ab9eb408faf99313546b5"
M01_INSTALLER_BLOB="590c9adf99c45ceeb38443813005ed68c1b0d694"
M04_INSTALLER_REF="587874f15df0c82d5adf22d5900c8fe620eafdc4"
M04_INSTALLER_BLOB="fb250ca3fa33c1f8b238c58f0d6b22e2140bf0b3"


def run(*args: str, env: dict | None=None, timeout: int=240) -> subprocess.CompletedProcess:
    result=subprocess.run(list(args),env=env,capture_output=True,text=True,timeout=timeout)
    if result.returncode:
        raise AssertionError("Command failed rc=%s %s stderr=%s"%(result.returncode, args[:2],result.stderr[-1100:]))
    return result


def download_blob(url: str, sha: str, dest: Path) -> None:
    run("curl","-fsSL","--proto","=https","--tlsv1.2","--max-time","50",url,"-o",str(dest),timeout=70)
    data=dest.read_bytes()
    got=hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
    if got != sha:
        raise AssertionError("Standalone module installer exact SHA-1 mismatch")


def bash_function(text: str,name: str) -> str:
    start=re.search(r"^"+re.escape(name)+r"\(\) \{\s*$",text,re.M)
    if start is None:
        raise AssertionError("missing "+name)
    close=re.search(r"^}\s*$",text[start.end():],re.M)
    if close is None:
        raise AssertionError("incomplete "+name)
    return text[start.start():start.end()+close.end()]


def tree_hash(root: Path) -> str:
    if not root.exists() and not root.is_symlink():
        raise AssertionError("module not installed: "+str(root))
    result=hashlib.sha256()
    for path in [root,*sorted(root.rglob("*"))]:
        state=path.lstat()
        relative=str(path.relative_to(root)) if path!=root else "."
        result.update(repr((relative,state.st_mode,state.st_size,state.st_mtime_ns)).encode())
        if path.is_symlink():
            result.update(os.readlink(path).encode())
        elif path.is_file():
            result.update(hashlib.sha256(path.read_bytes()).digest())
    return result.hexdigest()


class AllFiveModuleNativeCoexistence(unittest.TestCase):
    @unittest.skipUnless(os.getenv("P07_NATIVE_FIVE")=="1","exact ephemeral GitHub runner only")
    def test_all_five_coexist_and_each_upgrade_touches_only_selected_module(self):
        self.assertEqual(os.geteuid(),0)
        self.assertEqual(os.getenv("GITHUB_ACTIONS"),"true")
        self.assertTrue(os.getenv("RUNNER_TEMP"))
        self.assertTrue((PRODUCT/"scripts/install_p07_m05_bundle.py").is_file())
        for target in list(TARGETS.values())+[
            Path("/opt/vf-server-ops.previous"),Path("/usr/local/bin/vfops")
        ]:
            self.assertFalse(target.exists() or target.is_symlink(),
                             "refuse any pre-existing site, module, or global entry")
        text=(ROOT/"installers/p07-toolbox.sh").read_text()
        with tempfile.TemporaryDirectory(prefix="p07-native-five-") as work:
            work=Path(work)
            m01=work/"m01-installer.sh"
            m04=work/"m04-installer.sh"
            download_blob("https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/"+
                          M01_INSTALLER_REF+"/installers/p07-vf-node-independent-rc13.sh",
                          M01_INSTALLER_BLOB,m01)
            download_blob("https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/"+
                          M04_INSTALLER_REF+"/installers/p07-system-care-rc83-isolated.sh",
                          M04_INSTALLER_BLOB,m04)
            # M02 is a pinned SHA-256 audit executable installed by its
            # own extracted standalone Toolbox function (no other module).
            settings="\n".join(line for line in text.splitlines()
                                  if re.match(r"^(VPS_AUDIT_(PUBLIC|EXPECTED|BUILD_EXPECTED|URL|SHA256)|M02_ROOT)=",line))
            names=("sha256_file","m02_verified_current","ensure_m02_current")
            harness=work/"m02-install.sh"
            harness.write_text(
                "#!/usr/bin/env bash\nset -Eeuo pipefail\n"+settings+"\n"+
                "C_RED=''; C_GREEN=''; C_RESET=''\n"
                "say() { printf '%s\\n' \"$*\"; }\n"+
                "\n".join(bash_function(text,name) for name in names)+
                "\nensure_m02_current\n"
            )
            def selected(name: str):
                if name.startswith("M01"):
                    run("bash",str(m01),"install")
                elif name.startswith("M02"):
                    run("bash",str(harness),timeout=130)
                elif name.startswith("M03"):
                    run("bash",str(ROOT/"installers/p07-final.sh"),
                        env={**os.environ,"P07_NO_EXEC":"1","NO_COLOR":"1"},timeout=230)
                elif name.startswith("M04"):
                    run("bash",str(m04),"install",timeout=130)
                elif name.startswith("M05"):
                    data=builder.build_bundle(work/"m05-candidate1.zip")
                    run("python3",str(PRODUCT/"scripts/install_p07_m05_bundle.py"),
                        "--archive",data["path"],"--sha256",data["sha256"],timeout=90)
            sys.path.insert(0,str((PRODUCT/"scripts").resolve()))
            builder=importlib.import_module("build_p07_m05_bundle")
            # Install once, observe ownership and version of the resulting
            # module directory, then run each module's own updater again.
            for name in TARGETS:
                selected(name)
            self.assertEqual(
                os.readlink(MODULES/"m01/current"),"releases/0.1.0-rc13")
            self.assertEqual(
                os.readlink(MODULES/"m02/current"),"releases/2.1.0-rc7-field")
            self.assertEqual(
                os.readlink(MODULES/"m04/current"),"releases/0.1.0-rc83")
            self.assertEqual(
                os.readlink(MODULES/"m05/current"),"releases/0.1.0-m05-candidate1")
            self.assertEqual((TARGETS["M03 网站与数据"]/"BUILD_ID").read_text().strip(),
                             "0.1.0-release115")
            for selected_name in TARGETS:
                before={name:tree_hash(loc) for name,loc in TARGETS.items()
                        if name != selected_name}
                # M05 is already current. Reinstalling the identical candidate
                # must be a verified no-op, just like the others.
                if selected_name.startswith("M05"):
                    data=builder.build_bundle(work/"m05-repeat.zip")
                    run("python3",str(PRODUCT/"scripts/install_p07_m05_bundle.py"),
                        "--archive",data["path"],"--sha256",data["sha256"])
                else:
                    selected(selected_name)
                after={name:tree_hash(TARGETS[name]) for name in before}
                self.assertEqual(before,after,selected_name+" modified a sibling module")
            # Actual next-build atomic M05 upgrade and old-build rollback.
            baseline={name:tree_hash(loc) for name,loc in TARGETS.items()
                      if not name.startswith("M05")}
            builder.BUILD_ID="0.1.0-m05-candidate2"
            second=builder.build_bundle(work/"m05-next-version.zip")
            run("python3",str(PRODUCT/"scripts/install_p07_m05_bundle.py"),
                "--archive",second["path"],"--sha256",second["sha256"])
            self.assertEqual(os.readlink(MODULES/"m05/current"),
                             "releases/0.1.0-m05-candidate2")
            self.assertEqual(baseline,{name:tree_hash(TARGETS[name]) for name in baseline})
            run("python3",str(PRODUCT/"scripts/install_p07_m05_bundle.py"),
                "--rollback-build","0.1.0-m05-candidate1",
                "--confirm-rollback","P07-M05:0.1.0-m05-candidate1")
            self.assertEqual(os.readlink(MODULES/"m05/current"),
                             "releases/0.1.0-m05-candidate1")
            self.assertEqual(baseline,{name:tree_hash(TARGETS[name]) for name in baseline})
            print("P07_FIVE_NATIVE_MODULE_COEXISTENCE=PASS",flush=True)
            print("P07_EACH_MODULE_OTHER_FOUR_UNCHANGED=PASS",flush=True)
            print("P07_M05_NEXT_BUILD_ATOMIC_AND_ROLLBACK=PASS",flush=True)
            print("P07_OWNER_SERVERS_TOUCHED=NO",flush=True)


if __name__=="__main__":
    unittest.main()
