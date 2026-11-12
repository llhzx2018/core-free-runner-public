"""P07 5 modules: one disposable-host coexistence test, four unaffected on each upgrade.

Only on GitHub-hosted ephemeral ubuntu-24.04, exact private M05 checkout is
temporary and NEVER published. Does not install V2Ray nodes, CloudPanel,
change website data, run VPS migration or modify Owner production.
"""
from __future__ import annotations

import hashlib
import http.server
import importlib
import json
import os
from pathlib import Path
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
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
M01_INSTALLER_REF="adf4d8cc0db69255fb4a6aff58857561a0652bf6"
M01_INSTALLER_BLOB="8313adef7dd235b645fc815a7bded933fc289f82"
M04_INSTALLER_REF="75c7336b8467114f8bc3396dc06144e48275a39a"
M04_INSTALLER_BLOB="d39cef5d0915a99753d688f10fb1dbe74c0dac98"


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


def install_m05_via_local_https(work: Path, zip_path: Path, checksum: str,
                                source: str) -> None:
    """Exercise genuine HTTPS/curl/checksum/Toolbox M05 installation, no public upload.

    Private M05 source stays inside this ephemeral runner. Self-signed HTTPS
    cert is trusted ONLY by the disposable process via CURL_CA_BUNDLE.
    """
    server_dir=work/"m05-https"
    server_dir.mkdir()
    offered=server_dir/"owner-trial.zip"
    shutil.copyfile(zip_path,offered)
    public_installer=ROOT/"installers/p07-m05-atomic.py"
    installer_bytes=public_installer.read_bytes()
    installed_blob=hashlib.sha1(
        b"blob "+str(len(installer_bytes)).encode()+b"\0"+installer_bytes
    ).hexdigest()
    self_blob="17e47121ac27f31162d93a72aa0b1dbea602ea01"
    if installed_blob!=self_blob:
        raise AssertionError("public M05 installer pin drift")
    shutil.copyfile(public_installer,server_dir/"m05-atomic.py")
    cert=work/"m05-local-cert.pem"
    key=work/"m05-local-key.pem"
    run("openssl","req","-x509","-newkey","rsa:2048","-sha256","-nodes",
        "-days","1","-keyout",str(key),"-out",str(cert),
        "-subj","/CN=localhost","-addext","subjectAltName=DNS:localhost",
        timeout=35)
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,directory=str(server_dir),**kwargs)
        def log_message(self,*args):
            pass
    server=http.server.ThreadingHTTPServer(("127.0.0.1",0),QuietHandler)
    tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(str(cert),str(key))
    server.socket=tls.wrap_socket(server.socket,server_side=True)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        url="https://localhost:"+str(server.server_address[1])
        harness=work/"m05-verified-https.sh"
        functions="\n".join(bash_function(source,name) for name in
                            ("sha256_file","p07_git_blob_sha1",
                             "m05_verified_current","ensure_m05_current"))
        harness.write_text(
            "#!/bin/bash\nset -Eeuo pipefail\n"
            + 'M05_ROOT="/opt/vfops-modules/m05"\n'
            + 'M05_RUNTIME="$M05_ROOT/current/bin/vfops-init-entry"\n'
            + 'M05_BUNDLE_URL="'+url+'/owner-trial.zip"\n'
            + 'M05_BUNDLE_SHA256="'+checksum+'"\n'
            + 'M05_INSTALLER_URL="'+url+'/m05-atomic.py"\n'
            + 'M05_INSTALLER_BLOB="'+self_blob+'"\n'
            + "C_RED=''; C_YELLOW=''; C_RESET=''\n"
            + 'say() { printf "%s\\n" "$*"; }\n'
            + functions + "\nensure_m05_current\n"
        )
        env={**os.environ,"CURL_CA_BUNDLE":str(cert),"NO_COLOR":"1"}
        sibling={n:tree_hash(p) for n,p in TARGETS.items()
                 if not n.startswith("M05")}
        offered.write_bytes(b"incorrect-byte-stream")
        invalid=subprocess.run(["bash",str(harness)],env=env,
                               capture_output=True,text=True,timeout=35)
        if invalid.returncode!=6:
            raise AssertionError("tampered HTTPS package was not rejected: "
                                 +str(invalid.returncode))
        if TARGETS["M05 新服务器初始化"].exists():
            raise AssertionError("M05 root unexpectedly created by bad ZIP")
        offered.write_bytes(zip_path.read_bytes())
        run("bash",str(harness),env=env,timeout=100)
        run("bash",str(harness),env=env,timeout=30)  # verified idempotence
        if os.readlink(MODULES/"m05/current")!="releases/0.1.0-m05-candidate1":
            raise AssertionError("M05 HTTPS installation version mismatch")
        if sibling!={n:tree_hash(TARGETS[n]) for n in sibling}:
            raise AssertionError("M05 HTTPS install modified unrelated modules")
        print("P07_M05_HTTPS_VERIFIED_DOWNLOAD_INSTALL=PASS",flush=True)
        print("P07_M05_HTTPS_CORRUPT_PACKAGE_REJECTED=PASS",flush=True)
        print("P07_M05_HTTPS_OTHER_FOUR_UNCHANGED=PASS",flush=True)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=10)


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
                    install_m05_via_local_https(
                        work,Path(data["path"]),str(data["sha256"]),text
                    )
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
            # Owner Trial: install M05 only from its explicitly verified local
            # private ZIP; the other four module roots stay byte-identical.
            local_zip=work/"m05-candidate1.zip"
            local_sha=hashlib.sha256(local_zip.read_bytes()).hexdigest()
            local_cli=["bash",str(ROOT/"installers/p07-toolbox.sh"),
                       "--install-m05-local",str(local_zip),local_sha,
                       "P07-M05:INSTALL:"+local_sha]
            local_baseline={name:tree_hash(target) for name,target in TARGETS.items()
                            if not name.startswith("M05")}
            run(*local_cli,timeout=90)
            incorrect=subprocess.run(
                ["bash",str(ROOT/"installers/p07-toolbox.sh"),
                 "--install-m05-local",str(local_zip),"0"*64,
                 "P07-M05:INSTALL:"+"0"*64],
                capture_output=True,text=True,timeout=30)
            self.assertEqual(incorrect.returncode,6,incorrect.stderr)
            wrong_confirmation=subprocess.run(
                local_cli[:-1]+["P07-M03:INSTALL:"+local_sha],
                capture_output=True,text=True,timeout=20)
            self.assertEqual(wrong_confirmation.returncode,13,wrong_confirmation.stderr)
            self.assertEqual(os.readlink(MODULES/"m05/current"),
                             "releases/0.1.0-m05-candidate1")
            self.assertEqual(local_baseline,
                             {name:tree_hash(TARGETS[name]) for name in local_baseline})
            # Existing separately pinned M01/M04 rollback programs remain
            # independently callable through the common Toolbox CLI.
            for module,version in (("m01","0.1.0-rc13"),("m04","0.1.0-rc83")):
                run("bash",str(ROOT/"installers/p07-toolbox.sh"),
                    "--rollback-"+module,version,
                    "P07-"+module.upper()+":"+version,timeout=110)
                self.assertEqual(local_baseline,
                                 {name:tree_hash(TARGETS[name]) for name in local_baseline})
            print("P07_M05_LOCAL_PRIVATE_ZIP_GATE=PASS",flush=True)
            print("P07_M05_LOCAL_NEGATIVE_HASH_AND_CONFIRM=PASS",flush=True)
            print("P07_TOOLBOX_M01_M04_OWNER_ROLLBACK=PASS",flush=True)
            # P07-M02 服务器性能检测（VPS 验机） verifies its own
            # pinned audit binary before any independent pointer rollback.
            m02_root=MODULES/"m02"
            m02_prior="2.1.0-rc7-field"
            m02_other={name:tree_hash(loc) for name,loc in TARGETS.items()
                       if loc!=m02_root}
            m02_future=m02_root/"releases/2.1.0-synthetic-future"
            m02_future.mkdir()
            # This is a VALID locally owned future build. Invalid current
            # identities must remain rejected rather than implicitly repaired.
            m02_script=m02_future/"vps-audit.sh"
            m02_script.write_text(
                '#!/bin/bash\ncase "${1:-}" in\n'
                '  --version) echo V2.2.0 ;;\n'
                '  --build-id) echo 2.1.0-synthetic-future ;;\n'
                '  *) exit 13 ;;\nesac\n'
            )
            m02_script.chmod(0o755)
            (m02_future/"MANIFEST.sha256").write_text(
                hashlib.sha256(m02_script.read_bytes()).hexdigest()
                + "  vps-audit.sh\n"
            )
            m02_switch=m02_root/".test-switch"
            m02_switch.symlink_to("releases/2.1.0-synthetic-future")
            os.replace(m02_switch,m02_root/"current")
            m02_rollback=["bash",str(ROOT/"installers/p07-toolbox.sh"),
                          "--rollback-m02",m02_prior]
            for confirmation in ("P07-M02:WRONG",):
                bad=subprocess.run(m02_rollback+[confirmation],
                                   capture_output=True,text=True,timeout=20)
                self.assertEqual(bad.returncode,13,bad.stderr)
            m02_bin=m02_root/"releases"/m02_prior/"vps-audit.sh"
            m02_bytes=m02_bin.read_bytes()
            m02_bin.write_bytes(m02_bytes+b"\\n# synthetic tamper")
            bad=subprocess.run(m02_rollback+["P07-M02:"+m02_prior],
                               capture_output=True,text=True,timeout=20)
            self.assertEqual(bad.returncode,13,bad.stderr)
            self.assertEqual(os.readlink(m02_root/"current"),
                             "releases/2.1.0-synthetic-future")
            m02_bin.write_bytes(m02_bytes)
            run(*(m02_rollback+["P07-M02:"+m02_prior]),timeout=20)
            self.assertEqual(os.readlink(m02_root/"current"),
                             "releases/"+m02_prior)
            self.assertEqual(m02_other,{name:tree_hash(TARGETS[name])
                                        for name in m02_other})
            print("P07_M02_OWN_ROLLBACK_AND_TAMPER_REJECTION=PASS",flush=True)
            # Module OWN rollback commands: M01 network manager and M04
            # system-care return from a controlled synthetic future pointer
            # only after verifying the original immutable release bytes.
            # This does not execute real proxy or operating-system tuning.
            for label, target_root, standalone, build, module_id, critical in (
                ("P07-M01 网络代理节点（V2Ray）", MODULES/"m01", m01,
                 "0.1.0-rc13", "P07-M01", "vf-node.sh"),
                ("P07-M04 服务器维护与安全", MODULES/"m04", m04,
                 "0.1.0-rc83", "P07-M04", "vf-system-care.sh"),
            ):
                saved={name:tree_hash(root) for name,root in TARGETS.items()
                       if root!=target_root}
                synthetic=target_root/"releases/0.1.0-synthetic-future"
                synthetic.mkdir()
                (synthetic/"MARKER").write_text("owned disposable placeholder")
                pointer=target_root/"current"
                next_pointer=target_root/".test-switch"
                next_pointer.symlink_to("releases/0.1.0-synthetic-future")
                os.replace(next_pointer,pointer)
                rollback_cmd=["bash",str(standalone),"rollback",build]
                invalid=subprocess.run(
                    rollback_cmd+[module_id+":WRONG"],
                    capture_output=True,text=True,timeout=20)
                self.assertEqual(invalid.returncode,13,invalid.stderr)
                self.assertEqual(os.readlink(pointer),
                                 "releases/0.1.0-synthetic-future")
                origin=target_root/"releases"/build/critical
                original=origin.read_bytes()
                origin.write_bytes(original+b"\\n# deliberate-tamper")
                invalid=subprocess.run(
                    rollback_cmd+[module_id+":"+build],
                    capture_output=True,text=True,timeout=20)
                self.assertEqual(invalid.returncode,13,invalid.stderr)
                self.assertEqual(os.readlink(pointer),
                                 "releases/0.1.0-synthetic-future")
                origin.write_bytes(original)
                run(*(rollback_cmd+[module_id+":"+build]),timeout=20)
                self.assertEqual(os.readlink(pointer),"releases/"+build)
                self.assertEqual(saved,{name:tree_hash(TARGETS[name])
                                        for name in saved},label)
                print(module_id+"_PUBLIC_OWN_ROLLBACK_AND_BAD_HASH_REFUSAL=PASS",
                      flush=True)
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
            run("bash",str(ROOT/"installers/p07-toolbox.sh"),
                "--install-m05-local",str(second["path"]),second["sha256"],
                "P07-M05:INSTALL:"+second["sha256"],timeout=100)
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
            run("bash",str(ROOT/"installers/p07-toolbox.sh"),
                "--rollback-m05","0.1.0-m05-candidate1",
                "P07-M05:0.1.0-m05-candidate1",timeout=100)
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
            run("bash",str(ROOT/"installers/p07-toolbox.sh"),
                "--rollback-m05","0.1.0-m05-candidate1",
                "P07-M05:0.1.0-m05-candidate1",timeout=100)
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
