"""P07 五模块唯一工具箱入口：各自回滚及 M05 私有试用 ZIP 安全门禁。

This suite intentionally uses only non-mutating invalid inputs. Actual M05
private ZIP install and its rollback run in a disposable GitHub-hosted native
five-module coexistence job, not on the Owner's VPS.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
TOOLBOX=ROOT/"installers/p07-toolbox.sh"


def invoke(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(TOOLBOX), *args],
                          capture_output=True, text=True, timeout=20)


class FiveModuleSelectedOwnerOperations(unittest.TestCase):
    def test_single_entry_exposes_five_owned_rollback_commands(self):
        source=TOOLBOX.read_text(encoding="utf-8")
        for module in range(1,6):
            identifier=f"{module:02d}"
            self.assertEqual(source.count(f"--rollback-m{identifier})"),1)
        self.assertEqual(source.count("--install-m05-local)"),1)
        self.assertEqual(source.count("--install-m05-offline)"),1)
        # Historical M03 Owner trials remain inert without a selected
        # development operation; the common Owner menu never runs them.
        start=source.index("run_server_ops() {")
        end=source.index("\n}\n",start)
        m03_entry=source[start:end]
        self.assertNotIn("run_server_ops_owner124_trial",m03_entry)
        self.assertNotIn("run_server_ops_owner143_trial",m03_entry)
        self.assertNotIn("release143",m03_entry)
        self.assertIn('M05_BUNDLE_URL=""',source)
        self.assertIn('M05_BUNDLE_SHA256=""',source)
        help_text=invoke("--help")
        self.assertEqual(help_text.returncode,0,help_text.stderr)
        for x in ("--rollback-m01","--rollback-m02","--rollback-m03",
                  "--rollback-m04","--rollback-m05","--install-m05-local",
                  "--install-m05-offline"):
            self.assertIn(x,help_text.stdout)
        self.assertIn("P07-M05 新服务器初始化",source)
        self.assertIn("P07-M04 服务器维护与安全",source)

    def test_wrong_confirmations_fail_before_module_installers_or_network(self):
        for module in range(1,6):
            name=f"m{module:02d}"
            with self.subTest(name=name):
                build="0.1.0-unsafe-fixture"
                result=invoke("--rollback-"+name,build,
                              "P07-M05:"+build if module!=5 else "P07-M04:"+build)
                self.assertEqual(result.returncode,13,result.stderr)

    def test_local_path_and_integrity_negatives_rejected(self):
        with tempfile.TemporaryDirectory(prefix="p07-m05-local-negative-") as t:
            folder=Path(t)
            candidate=folder/"candidate.zip"
            candidate.write_bytes(b"not a real ZIP")
            sha=hashlib.sha256(candidate.read_bytes()).hexdigest()
            def attempt(path,checksum,confirm):
                return invoke("--install-m05-local",str(path),checksum,confirm)
            invalid=[
                (candidate,sha,"P07-M04:INSTALL:"+sha),
                (candidate,sha,"P07-M05:INSTALL:wrong"),
                (candidate,"0"*40,"P07-M05:INSTALL:"+"0"*40),
                ("relative/file.zip",sha,"P07-M05:INSTALL:"+sha),
                (folder/"absent.zip",sha,"P07-M05:INSTALL:"+sha),
            ]
            symlink=folder/"linked.zip"
            symlink.symlink_to(candidate)
            invalid.append((symlink,sha,"P07-M05:INSTALL:"+sha))
            for path,checksum,confirm in invalid:
                with self.subTest(path=str(path),confirm=confirm):
                    result=attempt(path,checksum,confirm)
                    self.assertEqual(result.returncode,13,result.stderr)
            self.assertEqual(candidate.read_bytes(),b"not a real ZIP")

    def test_missing_cli_parameters_do_not_fallback_to_other_modules(self):
        for args in (("--install-m05-local",),
                     ("--rollback-m01",),("--rollback-m04",),
                     ("--rollback-m05",)):
            result=invoke(*args)
            self.assertEqual(result.returncode,13,result.stderr)

    def test_offline_trial_does_not_depend_on_git_token_or_network(self):
        source=TOOLBOX.read_text(encoding="utf-8")
        fragment=source.split("install_m05_offline_trial() {",1)[1].split("\n}\n",1)[0]
        self.assertIn('bash "$tmp" --verify-only',fragment)
        self.assertIn('bash "$tmp" --install-only',fragment)
        for dependency in ("curl ", "ssh ", "git ", "gh auth",
                           "VF_PRIVATE_READ_TOKEN", "VF_RELEASE_WRITE_TOKEN"):
            self.assertNotIn(dependency,fragment)
        self.assertIn('"$confirmation" == "P07-M05:INSTALL"',fragment)

    def test_m05_is_not_distributed_by_a_private_candidate_url(self):
        source=TOOLBOX.read_text(encoding="utf-8")
        # Distinguish local byte-proven Owner trial from a public release URL.
        self.assertRegex(source,r'M05_BUNDLE_URL=""')
        self.assertNotIn("owner-trial/p07-m05-20261112-private-zip",source)
        self.assertNotIn("github.com/llhzx2018/vf-server-ops/blob",source)
        self.assertIn('P07-M05:INSTALL:$checksum',source)


if __name__=="__main__":
    unittest.main()
