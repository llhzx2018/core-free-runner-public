"""P07-M03 网站与数据: reproduce Owner's `P07_M03_VERIFY_FAILED` from real Toolbox call.

Exercise the exact extracted main-branch function, real published updater script,
actual Git blob check and PTY confirmation. Replace only production /opt paths
with isolated test paths and stop at a deliberately wrong ZIP hash. No VPS writes.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOLBOX = ROOT / "installers/p07-toolbox.sh"
INSTALLER = ROOT / "installers/p07-m03-release135-repair.sh"
OLD_BUILD = "0.1.0-release115"


def toolbox_function(source: str) -> str:
    start = re.search(r"^ensure_server_ops_current\(\) \{$", source, re.M)
    if not start:
        raise AssertionError("M03 owner entry function missing")
    tail = source[start.start():]
    close = re.search(r"^\}$", tail, re.M)
    if not close:
        raise AssertionError("M03 owner entry function not closed")
    return tail[:close.end()]


class OwnerM03ToolboxRealEntry(unittest.TestCase):
    def run_upgrade(self, user_input: str | None, *, omit_install: bool = False):
        if user_input is not None and not shutil.which("script"):
            self.skipTest("util-linux script PTY wrapper not installed")
        with tempfile.TemporaryDirectory(prefix="p07-m03-entry-") as root:
            tmp = Path(root)
            runtime = tmp / "m03-runtime"
            runtime.mkdir()
            build = runtime / "BUILD_ID"
            build.write_text(OLD_BUILD + "\n")
            sibling = tmp / "m04-preserve"
            sibling.write_text("OTHER_MODULE_KEEP\n")
            downloads = tmp / "network-activity"
            stubbin = tmp / "bin"
            stubbin.mkdir()
            curl = stubbin / "curl"
            curl.write_text("""#!/usr/bin/env bash
set -Eeuo pipefail
url=''
out=''
while (( $# )); do
  arg="$1"; shift
  case "$arg" in
    -o) out="$1"; shift ;;
    https://*) url="$arg" ;;
  esac
done
[[ -n "$out" ]] || exit 33
printf '%s\\n' "$url" >> "$P07_TEST_DOWNLOAD_LOG"
if [[ "$url" == *'/installers/p07-m03-release135-repair.sh' ]]; then
  cp -- "$P07_TEST_REAL_INSTALLER" "$out"
else
  # Caller reached the REAL M03 installer and its guarded ZIP phase.
  printf 'not-the-signed-release-zip' > "$out"
fi
""", encoding="utf-8")
            curl.chmod(0o755)

            source = toolbox_function(TOOLBOX.read_text(encoding="utf-8"))
            if omit_install:
                old = 'P07_TOOLBOX_PARENT=1 P07_NO_EXEC=1 bash "$tmp" install'
                if old not in source:
                    raise AssertionError("can't construct historical regression")
                source = source.replace(old, 'P07_TOOLBOX_PARENT=1 P07_NO_EXEC=1 bash "$tmp"')
            # Rewire ONLY the old installed runtime marker; no real /opt writes.
            source = source.replace("/opt/vf-server-ops/BUILD_ID", '"$P07_TEST_RUNTIME/BUILD_ID"')
            harness = tmp / "harness.sh"
            harness.write_text(
                """#!/usr/bin/env bash
set -Eeuo pipefail
C_RED=''; C_RESET=''
VF_SERVER_OPS_BUILD_EXPECTED='0.1.0-release135'
M03_BOOTSTRAP_BUILD='0.1.0-release115'
VF_SERVER_OPS_INSTALLER_BLOB='ede84039edc66fdbb5f218b6b505b9edd00bb3a7'
VF_SERVER_OPS_INSTALLER='https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main/installers/p07-m03-release135-repair.sh'
say() { printf '%s\\n' "$*"; }
m03_verified_current() { [[ "$(cat "$P07_TEST_RUNTIME/BUILD_ID")" == '0.1.0-release115' ]]; }
p07_git_blob_sha1() { git hash-object "$1"; }
""" + source + """
if ensure_server_ops_current; then
  rc=0
else
  rc=$?
fi
printf 'OWNER_M03_ENTRY_RESULT=%s\\n' "$rc"
exit 0
""", encoding="utf-8")
            env = dict(os.environ, NO_COLOR="1", P07_ALLOW_NONROOT="1",
                       PATH=str(stubbin) + os.pathsep + os.environ["PATH"],
                       P07_TEST_REAL_INSTALLER=str(INSTALLER),
                       P07_TEST_DOWNLOAD_LOG=str(downloads),
                       P07_TEST_RUNTIME=str(runtime))
            command = ["bash", str(harness)]
            if user_input is not None:
                command = ["script", "-q", "-e", "-c", "bash " + str(harness), "/dev/null"]
            result = subprocess.run(command, text=True, input=user_input,
                                    capture_output=True, env=env, timeout=30)
            result_text = result.stdout.replace("\r", "") + result.stderr
            self.assertEqual(build.read_text(), OLD_BUILD + "\n")
            self.assertEqual(sibling.read_text(), "OTHER_MODULE_KEEP\n")
            self.assertNotIn("已完成本模块升级", result_text)
            urls = downloads.read_text().splitlines() if downloads.exists() else []
            return result_text, urls

    def test_owner_y_reaches_real_installer_signed_zip_stage(self):
        out, urls = self.run_upgrade("y\n")
        self.assertIn("已核验旧正式版", out)
        self.assertIn("OWNER_M03_ENTRY_RESULT=13", out)
        self.assertIn("错误阶段：HASH_MISMATCH", out)
        self.assertNotIn("错误阶段：P07_M03_VERIFY_FAILED", out)
        self.assertEqual(len(urls), 2, urls)
        self.assertTrue(urls[0].endswith("/p07-m03-release135-repair.sh"))
        self.assertIn("dist/p07/0.1.0-release135", urls[1])

    def test_historical_missing_install_argument_reproduces_real_failure(self):
        out, urls = self.run_upgrade("y\n", omit_install=True)
        self.assertIn("OWNER_M03_ENTRY_RESULT=13", out)
        self.assertIn("错误阶段：P07_M03_VERIFY_FAILED", out)
        self.assertEqual(len(urls), 1, urls)

    def test_cancel_and_no_tty_do_not_download(self):
        out, urls = self.run_upgrade("n\n")
        self.assertIn("OWNER_M03_ENTRY_RESULT=7", out)
        self.assertIn("升级取消", out)
        self.assertEqual(urls, [])
        out, urls = self.run_upgrade(None)
        self.assertIn("OWNER_M03_ENTRY_RESULT=7", out)
        self.assertIn("非交互模式未修改", out)
        self.assertEqual(urls, [])

    def test_real_installer_rejects_implicit_or_unknown_commands(self):
        for args in ([], ["--made-up"], ["install", "another"]):
            r = subprocess.run(["bash", str(INSTALLER), *args],
                               capture_output=True, text=True, timeout=4)
            self.assertEqual(r.returncode, 13, r.stderr)
            self.assertIn("错误阶段：P07_M03_VERIFY_FAILED", r.stderr)

if __name__ == "__main__":
    unittest.main()
