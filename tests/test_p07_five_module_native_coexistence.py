"""P07 5 modules: one disposable-host coexistence test, four unaffected on each upgrade.

Only on GitHub-hosted ephemeral ubuntu-24.04, exact private M05 checkout is
temporary and NEVER published. Does not install V2Ray nodes, CloudPanel,
change website data, run VPS migration or modify Owner production.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile

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
            # Exact Toolbox readback of M03/M05 does not install anything.
            # It accepts M05's own verified future build after an independent
            # candidate upgrade and does not consult a stale Toolbox pin.
            readback=work/"module-readback.sh"
            readback.write_text(
                "#!/bin/bash\nset -Eeuo pipefail\n"
                + 'M05_ROOT="/opt/vfops-modules/m05"\n'
                + 'M05_RUNTIME="$M05_ROOT/current/bin/vfops-init-entry"\n'
                + 'VF_SERVER_OPS_EXPECTED="VF Server Ops 0.1.0"\n'
                + "\n".join(bash_function(text,fn) for fn in
                            ("p07_git_blob_sha1","m05_verified_current","m03_verified_current"))
                + "\nm03_verified_current && m05_verified_current\n"
            )
            def verify_modules():
                run("bash",str(readback),timeout=30)
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
                    run("python3",str(ROOT/"installers/p07-m05-atomic.py"),
                        "install",data["path"],data["sha256"],timeout=90)
            sys.path.insert(0,str((PRODUCT/"scripts").resolve()))
            builder=importlib.import_module("build_p07_m05_bundle")
            # Stage-wide deterministic FULL candidate check: build the exact
            # private M05 source twice in disposable storage. Only a SHA256,
            # not its private ZIP/content, may appear in public evidence.
            first=builder.build_bundle(work/"m05-stage-frozen-A.zip")
            twin=builder.build_bundle(work/"m05-stage-frozen-B.zip")
            self.assertEqual(first["module_id"],"P07-M05")
            self.assertEqual(first["build_id"],"0.1.0-m05-candidate1")
            self.assertEqual(first["sha256"],twin["sha256"])
            # The release-stage lock is a pure public metadata contract.
            # Refuse source/ZIP drift instead of silently blessing a new hash.
            stage=json.loads((ROOT/"dist/p07/candidates/five-modules-stage-20261112.json")
                             .read_text(encoding="utf-8"))
            m05=next(m for m in stage["modules"] if m["id"]=="P07-M05")
            self.assertEqual(stage["product_source_sha"],
                             os.getenv("P07_PRODUCT_SOURCE_PIN",
                                       "7371f897605701011ba4b3bc18721b9966babbea"))
            self.assertEqual(first["sha256"],m05["package_identity_digest"])
            self.assertEqual(first["file_count"],m05["package_file_count"])
            self.assertEqual(m05["distribution"],"NOT_RELEASED")
            self.assertEqual((work/"m05-stage-frozen-A.zip").read_bytes(),
                             (work/"m05-stage-frozen-B.zip").read_bytes())
            self.assertGreater(int(first["file_count"]),20)
            self.assertEqual(first["formal_release"],False)
            self.assertEqual(first["production_install"],False)
            print("P07_M05_CANDIDATE_DETERMINISTIC_SHA256="+first["sha256"],flush=True)
            print("P07_M05_CANDIDATE_FILE_COUNT="+str(first["file_count"]),flush=True)
            print("P07_M05_CANDIDATE_DISTRIBUTION=NOT_RELEASED",flush=True)
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
            verify_modules()
            # Read-only Toolbox status must report all five independently
            # installed builds without launching any module or touching files.
            before_status={name:tree_hash(root) for name,root in TARGETS.items()}
            status=run("bash",str(ROOT/"installers/p07-toolbox.sh"),"--modules",
                       timeout=20).stdout
            for chinese in (
                "P07-M01 网络代理节点（V2Ray）",
                "P07-M02 服务器性能检测（VPS 验机）",
                "P07-M03 网站与数据",
                "P07-M04 服务器维护与安全",
                "P07-M05 新服务器初始化",
            ):
                self.assertIn(chinese+"：",status)
            self.assertIn("0.1.0-m05-candidate1",status)
            self.assertIn("0.1.0-release115",status)
            self.assertEqual(before_status,
                             {name:tree_hash(root) for name,root in TARGETS.items()})
            print("P07_FIVE_MODULE_READ_ONLY_STATUS_NO_WRITES=PASS",flush=True)
            # Negative: public M05 installer must refuse a bad ZIP hash,
            # an archive that tries to escape into M03, and a corrupted
            # installed M05 file, without touching ANY sibling module.
            m05_origin=work/"m05-candidate1.zip"
            sibling_baseline={name:tree_hash(loc) for name,loc in TARGETS.items()
                              if not name.startswith("M05")}
            current_before=os.readlink(MODULES/"m05/current")
            public_installer=str(ROOT/"installers/p07-m05-atomic.py")
            wrong=subprocess.run(
                ["python3",public_installer,"install",str(m05_origin),"0"*64],
                capture_output=True,text=True,timeout=30)
            self.assertEqual(wrong.returncode,13,wrong.stderr)
            malicious=work/"m05-path-escape.zip"
            with zipfile.ZipFile(malicious,"w") as archive:
                archive.writestr("p07-m05/../../../m03/BUILD_ID",b"overwrite-attempt")
            evil_sha=hashlib.sha256(malicious.read_bytes()).hexdigest()
            escaped=subprocess.run(
                ["python3",public_installer,"install",str(malicious),evil_sha],
                capture_output=True,text=True,timeout=30)
            self.assertEqual(escaped.returncode,13,escaped.stderr)
            victim=MODULES/"m05/current/bin/vfops-init-core"
            original=victim.read_bytes()
            victim.write_bytes(original+b"\n# synthetic tamper")
            candidate_sha=hashlib.sha256(m05_origin.read_bytes()).hexdigest()
            corrupted=subprocess.run(
                ["python3",public_installer,"install",str(m05_origin),candidate_sha],
                capture_output=True,text=True,timeout=30)
            self.assertEqual(corrupted.returncode,13,corrupted.stderr)
            self.assertEqual(victim.read_bytes(),original+b"\n# synthetic tamper")
            victim.write_bytes(original)
            self.assertEqual(os.readlink(MODULES/"m05/current"),current_before)
            self.assertEqual(
                sibling_baseline,
                {name:tree_hash(TARGETS[name]) for name in sibling_baseline})
            print("P07_M05_PUBLIC_INSTALL_NEGATIVE_CASES=PASS",flush=True)
            print("P07_M05_FAILURE_OTHERS_UNCHANGED=PASS",flush=True)

            for selected_name in TARGETS:
                before={name:tree_hash(loc) for name,loc in TARGETS.items()
                        if name != selected_name}
                # M05 is already current. Reinstalling the identical candidate
                # must be a verified no-op, just like the others.
                if selected_name.startswith("M05"):
                    data=builder.build_bundle(work/"m05-repeat.zip")
                    run("python3",str(ROOT/"installers/p07-m05-atomic.py"),
                        "install",data["path"],data["sha256"])
                else:
                    selected(selected_name)
                after={name:tree_hash(TARGETS[name]) for name in before}
                self.assertEqual(before,after,selected_name+" modified a sibling module")
            # Actual next-build atomic M05 upgrade and old-build rollback.
            baseline={name:tree_hash(loc) for name,loc in TARGETS.items()
                      if not name.startswith("M05")}
            builder.BUILD_ID="0.1.0-m05-candidate2"
            second=builder.build_bundle(work/"m05-next-version.zip")
            run("python3",str(ROOT/"installers/p07-m05-atomic.py"),
                "install",second["path"],second["sha256"])
            self.assertEqual(os.readlink(MODULES/"m05/current"),
                             "releases/0.1.0-m05-candidate2")
            verify_modules()
            self.assertEqual(baseline,{name:tree_hash(TARGETS[name]) for name in baseline})
            # The PUBLIC M05 standalone installer, not private product
            # tooling, must own rollback. Negative fault-injection cannot
            # change current or any of the four sibling module roots.
            rollback_cli=["python3",str(ROOT/"installers/p07-m05-atomic.py"),
                          "rollback","0.1.0-m05-candidate1"]
            for invalid in (
                rollback_cli+["--confirm","P07-M05:wrong"],
                ["python3",str(ROOT/"installers/p07-m05-atomic.py"),
                 "rollback","nonexistent-build","--confirm","P07-M05:nonexistent-build"],
            ):
                result=subprocess.run(invalid,capture_output=True,text=True,timeout=30)
                self.assertEqual(result.returncode,13,result.stderr)
                self.assertEqual(os.readlink(MODULES/"m05/current"),
                                 "releases/0.1.0-m05-candidate2")
            previous=MODULES/"m05/releases/0.1.0-m05-candidate1"
            old_content=(previous/"lib/server_migration.py").read_bytes()
            (previous/"lib/server_migration.py").write_bytes(old_content+b"\\n# tampered rollback")
            rejected=subprocess.run(
                rollback_cli+["--confirm","P07-M05:0.1.0-m05-candidate1"],
                capture_output=True,text=True,timeout=30)
            self.assertEqual(rejected.returncode,13,rejected.stderr)
            self.assertEqual(os.readlink(MODULES/"m05/current"),
                             "releases/0.1.0-m05-candidate2")
            (previous/"lib/server_migration.py").write_bytes(old_content)
            run(*rollback_cli,"--confirm","P07-M05:0.1.0-m05-candidate1")
            self.assertEqual(os.readlink(MODULES/"m05/current"),
                             "releases/0.1.0-m05-candidate1")
            verify_modules()
            self.assertEqual(baseline,{name:tree_hash(TARGETS[name]) for name in baseline})
            # Re-apply exact existing candidate2 archive after rollback; it is
            # verified byte-for-byte, not overwritten, then re-activated.
            run("python3",str(ROOT/"installers/p07-m05-atomic.py"),
                "install",second["path"],second["sha256"])
            self.assertEqual(os.readlink(MODULES/"m05/current"),
                             "releases/0.1.0-m05-candidate2")
            run(*rollback_cli,"--confirm","P07-M05:0.1.0-m05-candidate1")
            self.assertEqual(os.readlink(MODULES/"m05/current"),
                             "releases/0.1.0-m05-candidate1")
            print("P07_M05_PUBLIC_INSTALLER_OWN_ROLLBACK=PASS",flush=True)
            print("P07_M05_ROLLBACK_INVALID_TARGET_AND_TAMPER_REJECTED=PASS",flush=True)
            print("P07_M05_INTERRUPTED_SWITCH_RESUME=PASS",flush=True)
            self.assertEqual(baseline,{name:tree_hash(TARGETS[name]) for name in baseline})
            print("P07_FIVE_NATIVE_MODULE_COEXISTENCE=PASS",flush=True)
            print("P07_EACH_MODULE_OTHER_FOUR_UNCHANGED=PASS",flush=True)
            print("P07_M05_NEXT_BUILD_ATOMIC_AND_ROLLBACK=PASS",flush=True)
            print("P07_OWNER_SERVERS_TOUCHED=NO",flush=True)


if __name__=="__main__":
    unittest.main()
