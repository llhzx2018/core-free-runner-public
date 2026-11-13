"""P07-M01 网络代理节点、M02 服务器性能检测、M04 服务器维护与安全:
run the exact Toolbox ensure functions with synthetic isolated PTYs and
module-specific fake IO. Never install on a real VPS.
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
SOURCE = ROOT / "installers/p07-toolbox.sh"
MODULES = (
    ("m01", "0.1.0-rc13", "0.1.0-ux1"),
    ("m02", "2.1.0-rc7-field", "2.1.1-ux1"),
    ("m04", "0.1.0-rc83", "0.1.0-ux2"),
)


def function(source: str, name: str) -> str:
    m = re.search(r"^" + re.escape(name) + r"\(\) \{$", source, re.M)
    if not m:
        raise AssertionError(f"missing real function: {name}")
    tail = source[m.start():]
    close = re.search(r"^}$", tail, re.M)
    if close is None:
        raise AssertionError(f"no closing brace: {name}")
    return tail[:close.end()]


class P07ModuleTargetUpgradeGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding="utf-8")

    def execute(self, module, installed, target, *, valid=True,
                response=None, bad_hash=False):
        with tempfile.TemporaryDirectory(prefix="p07-target-upgrade-") as tmp:
            home = Path(tmp) / "modules" / module
            old = home / "releases" / installed
            old.mkdir(parents=True)
            (home / "current").symlink_to("releases/" + installed)
            (Path(tmp) / "other-module").write_text("KEEP")
            stub = r'''
set +e
C_RED=''; C_RESET=''
say(){ printf 'MESSAGE:%s\n' "$*"; }
id(){ echo 0; }
sha256_file(){
  if [[ "$P07_BAD_HASH" == 1 ]]; then printf 'BADHASH\n'; else printf '%s\n' "$P07_EXPECTED_HASH"; fi
}
p07_git_blob_sha1(){
  if [[ "$P07_BAD_HASH" == 1 ]]; then printf 'BADHASH\n'; else printf '%s\n' "$P07_EXPECTED_BLOB"; fi
}
readlink(){ /usr/bin/readlink "$@"; }
m01_verified_current(){ [[ "$P07_VALID" == 1 ]]; }
m02_verified_current(){ [[ "$P07_VALID" == 1 ]]; }
m04_verified_current(){ [[ "$P07_VALID" == 1 ]]; }
curl(){
  local arg output=''
  while (( $# )); do
    arg="$1"; shift
    [[ "$arg" == '-o' ]] && { output="$1"; shift; }
  done
  [[ -n "$output" ]] || return 9
  printf 'echo synthetic\n' >"$output"
  printf 'ACTION:download\n'
}
bash(){
  case "$*" in
    *'--version') echo 'P07 synthetic V2.1.1'; return 0 ;;
    *'--build-id') echo '2.1.1-ux1'; return 0 ;;
    *' install')
      printf 'ACTION:install-manager\n'
      local slot
      slot="$P07_MODULE_ROOT/current"
      /bin/mkdir -p "$P07_MODULE_ROOT/releases/$P07_TARGET"
      /bin/ln -s "releases/$P07_TARGET" "$P07_MODULE_ROOT/.next-manager"
      /bin/mv -Tf "$P07_MODULE_ROOT/.next-manager" "$slot"
      return 0 ;;
    *) /bin/bash "$@" ;;
  esac
}
M01_ROOT="$P07_MODULE_ROOT"
M02_ROOT="$P07_MODULE_ROOT"
M04_ROOT="$P07_MODULE_ROOT"
M01_INSTALLER_URL='https://example.invalid/owned-m01'
M01_INSTALLER_BLOB='1111111111111111111111111111111111111111'
M04_INSTALLER_URL='https://example.invalid/owned-m04'
M04_INSTALLER_BLOB='2222222222222222222222222222222222222222'
VPS_AUDIT_URL='https://example.invalid/owned-m02'
VPS_AUDIT_SHA256='3333333333333333333333333333333333333333333333333333333333333333'
VPS_AUDIT_EXPECTED='V2.1.1'
VF_NODE_EXPECTED="$P07_TARGET"
VPS_AUDIT_BUILD_EXPECTED="$P07_TARGET"
M04_BUILD_EXPECTED="$P07_TARGET"
M01_RUNTIME="$P07_MODULE_ROOT/current/vf-node.sh"
M04_RUNTIME="$P07_MODULE_ROOT/current/vf-system-care.sh"
'''
            body = function(self.source, "ensure_" + module + "_current")
            script = Path(tmp) / "harness.sh"
            script.write_text(
                "#!/usr/bin/env bash\n" + stub + "\n" + body
                + "\nensure_" + module + "_current\n"
                + "RESULT=$?\n"
                + "printf 'RESULT:%s\n' \"$RESULT\"\n"
                + "printf 'CURRENT:%s\n' \"$(/usr/bin/readlink \"$P07_MODULE_ROOT/current\")\"\n"
                + "printf 'SIBLING:%s\n' \"$(cat \"$P07_TEST_TMP/other-module\")\"\n",
                encoding="utf-8")
            env = dict(os.environ, NO_COLOR="1", P07_MODULE_ROOT=str(home),
                       P07_TARGET=target, P07_TEST_TMP=tmp,
                       P07_VALID="1" if valid else "0",
                       P07_BAD_HASH="1" if bad_hash else "0",
                       P07_EXPECTED_BLOB=("1"*40 if module=="m01" else "2"*40),
                       P07_EXPECTED_HASH="3"*64)
            cmd = ["bash", str(script)]
            if response is not None:
                if not shutil.which("script"):
                    self.skipTest("PTY wrapper unavailable")
                cmd = ["script", "-q", "-e", "-c", "bash " + str(script), "/dev/null"]
            run = subprocess.run(cmd, input=response, text=True, capture_output=True,
                                 env=env, timeout=8)
            self.assertEqual(run.returncode, 0, run.stderr)
            output = run.stdout.replace("\r", "")
            self.assertIn("SIBLING:KEEP", output)
            self.assertNotIn("\x1b", output)
            return output

    def test_main_menu(self):
        for module,old,new in MODULES:
            with self.subTest(module=module):
                out = self.execute(module,new,new)
                self.assertIn("RESULT:0",out)
                self.assertIn("CURRENT:releases/"+new,out)
                self.assertNotIn("ACTION:download",out)

    def test_readonly(self):
        for module,old,new in MODULES:
            with self.subTest(module=module):
                out=self.execute(module,old,new)
                self.assertIn("RESULT:7",out)
                self.assertIn("CURRENT:releases/"+old,out)
                self.assertNotIn("ACTION:download",out)

    def test_write_confirmation(self):
        for module,old,new in MODULES:
            with self.subTest(module=module):
                out=self.execute(module,old,new,response="n\n")
                self.assertIn("RESULT:7",out)
                self.assertIn("CURRENT:releases/"+old,out)
                self.assertNotIn("ACTION:download",out)

    def test_cancel_eof_invalid(self):
        for module,old,new in MODULES:
            with self.subTest(module=module):
                out=self.execute(module,old,new,response="x\n")
                self.assertIn("RESULT:7",out)
                self.assertIn("CURRENT:releases/"+old,out)
                self.assertNotIn("ACTION:download",out)

    def test_success(self):
        for module,old,new in MODULES:
            with self.subTest(module=module):
                out=self.execute(module,old,new,response="y\n")
                self.assertIn("RESULT:0",out)
                self.assertIn("CURRENT:releases/"+new,out)
                self.assertIn("ACTION:download",out)

    def test_failure_block(self):
        for module,old,new in MODULES:
            with self.subTest(module=module):
                out=self.execute(module,old,new,valid=False)
                self.assertIn("RESULT:13",out)
                self.assertIn("CURRENT:releases/"+old,out)
                self.assertNotIn("ACTION:download",out)

    def test_no_color_non_tty(self):
        for module,old,new in MODULES:
            with self.subTest(module=module):
                out=self.execute(module,old,new,response="y\n",bad_hash=True)
                self.assertIn("RESULT:6",out)
                self.assertIn("CURRENT:releases/"+old,out)
                self.assertIn("ACTION:download",out)
                self.assertNotIn("ACTION:install-manager",out)

    def test_immutable_bootstrap_pins(self):
        self.assertIn('M01_BOOTSTRAP_BUILD="0.1.0-rc13"',self.source)
        self.assertIn('VPS_AUDIT_BOOTSTRAP_BUILD="2.1.0-rc7-field"',self.source)
        self.assertIn('M04_BOOTSTRAP_BUILD="0.1.0-rc83"',self.source)
        for name in ("m01_verified_current","m02_verified_current","m04_verified_current"):
            self.assertIn("*) return 1", function(self.source,name))


if __name__ == "__main__":
    unittest.main()
