#!/usr/bin/env python3
"""One-off real old-formal UX1 -> UX2 upgrade/rollback on an EMPTY GitHub runner.

Requires GITHUB_ACTIONS=true plus an explicit opt-in environment switch and root.
NEVER run on an Owner VPS or a machine with existing /opt/vfops-modules.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import pty
import select
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
MOD = Path("/opt/vfops-modules")
M01_OLD = "0.1.0-ux1"
M02_OLD = "2.1.1-ux1"
M01_NEW = "0.1.0-ux2"
M02_NEW = "2.1.1-ux2"
M02_OLD_SHA = "7b083e4cf105d40b04b4cbe898fb6b9e1bb7f1ef3385bc1d20829796f6852013"
M02_NEW_SHA = "18a7a7dc401772fda7344845b952bc307a46f05443d086ec5e38a1954308587d"
M01_NEW_MANIFEST_SHA = "1f66f642769848e5be0c9a25ccb58a60e97e40fe2eb58a088233a5c129f1cb90"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(value: bool, reason: str) -> None:
    if not value:
        raise AssertionError(reason)


def run(args: list[str], timeout: int = 90) -> str:
    p = subprocess.run(args, cwd=ROOT, env=dict(os.environ, NO_COLOR="1", TERM="dumb"),
                       text=True, capture_output=True, timeout=timeout)
    check(p.returncode == 0, f"command failed {args}: {p.stdout[-1400:]} {p.stderr[-700:]}")
    return p.stdout


def tty(script: Path, selection: bytes, timeout: float = 135) -> str:
    # Drive the real Toolbox TTY, not a synthetic bash function call.
    fd, child = pty.openpty()
    proc = subprocess.Popen(["bash", str(script)], stdin=child, stdout=child, stderr=child,
                            cwd=ROOT, env=dict(os.environ, NO_COLOR="1", TERM="dumb"))
    os.close(child)
    output = bytearray()
    try:
        os.write(fd, selection)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            ready, _, _ = select.select([fd], [], [], 0.25)
            if ready:
                try:
                    output.extend(os.read(fd, 65536))
                except OSError:
                    break
            if proc.poll() is not None:
                break
        check(proc.poll() is not None, "Toolbox TTY hung; aborted without claiming success")
        check(proc.wait(timeout=2) == 0, "Toolbox TTY command rejected: " + output.decode("utf-8", "replace")[-1800:])
        return output.decode("utf-8", "replace")
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=3)
        os.close(fd)


def main() -> None:
    check(os.environ.get("GITHUB_ACTIONS") == "true", "not a GitHub-hosted runner")
    check(os.environ.get("P07_UX2_DISPOSABLE_RUNNER") == "YES", "isolated-only opt-in missing")
    check(os.geteuid() == 0, "root required for exact production-path rehearsal")
    check(not MOD.exists() and not MOD.is_symlink(), "Refusing existing P07 module root")
    check(not Path("/etc/vf-node").exists(), "Refusing any existing node configuration")
    check(len(sys.argv) == 2, "pass the immutable GitHub PR exact source SHA")
    ref = sys.argv[1]
    from importlib.util import spec_from_file_location, module_from_spec
    builder_path = ROOT / "scripts/prepare_p07_m01_m02_ux2_candidate.py"
    spec = spec_from_file_location("p07_m01_m02_builder", builder_path)
    assert spec and spec.loader
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    toolbox = mod.generate(ref)
    orig = (ROOT / "installers/p07-toolbox.sh").read_text(encoding="utf-8")
    check("M05_BUILD_EXPECTED=" in toolbox and
          toolbox.split("VF_SERVER_OPS_PUBLIC=", 1)[1] == orig.split("VF_SERVER_OPS_PUBLIC=", 1)[1],
          "M03/M04/M05 source changed in candidate")
    m01_src = ROOT / "packages/p07-network-node/0.1.0-ux2"
    check(sha(m01_src / "MANIFEST.sha256") == M01_NEW_MANIFEST_SHA, "UX2 M01 manifest source mismatch")
    check(sha(ROOT / "experiments/p07-vps-audit-v21-ux2.sh") == M02_NEW_SHA, "UX2 M02 source mismatch")
    check(sha(ROOT / "experiments/p07-vps-audit-v21-ux1.sh") == M02_OLD_SHA, "official UX1 identity mismatch")

    with tempfile.TemporaryDirectory(prefix="p07-ux2-exact-matrix-") as tmp:
        script = Path(tmp) / "p07-candidate-toolbox.sh"
        script.write_text(toolbox, encoding="utf-8")
        run(["bash", "-n", str(script)])
        # Other three modules are protected by immutable sentinels: never invoke their installers.
        MOD.mkdir(mode=0o755, parents=True, exist_ok=False)
        try:
            sentinel = {}
            for m in ("m03", "m04", "m05"):
                p = MOD / m / "identity"
                p.parent.mkdir()
                p.write_text(m + "-UNTAMPERED", encoding="ascii")
                sentinel[m] = sha(p)
            m01_root = MOD / "m01"
            m01_root.mkdir()
            (m01_root / "releases").mkdir()
            shutil.copytree(ROOT / "packages/p07-network-node/0.1.0-ux1",
                            m01_root / "releases" / M01_OLD)
            (m01_root / "current").symlink_to("releases/" + M01_OLD)
            m02_root = MOD / "m02"
            (m02_root / "releases" / M02_OLD).mkdir(parents=True)
            old_script = m02_root / "releases" / M02_OLD / "vps-audit.sh"
            shutil.copy2(ROOT / "experiments/p07-vps-audit-v21-ux1.sh", old_script)
            (old_script.parent / "MANIFEST.sha256").write_text(
                f"{M02_OLD_SHA}  vps-audit.sh\n", encoding="ascii")
            (m02_root / "current").symlink_to("releases/" + M02_OLD)

            # No write for declined upgrades, no automatic test, no cross-module mutation.
            tty(script, b"1\nn\n0\n", 25)
            tty(script, b"2\nn\n0\n", 25)
            check(os.readlink(m01_root / "current") == "releases/" + M01_OLD,
                  "M01 no must leave old current unchanged")
            check(os.readlink(m02_root / "current") == "releases/" + M02_OLD,
                  "M02 no must leave old current unchanged")

            # Corrupt published-M02 expected digest; no switch must happen.
            bad_script = Path(tmp) / "p07-wrong-hash.sh"
            bad_script.write_text(toolbox.replace(M02_NEW_SHA, "0" * 64, 1), encoding="utf-8")
            tty(bad_script, b"2\ny\n0\n", 45)
            check(os.readlink(m02_root / "current") == "releases/" + M02_OLD,
                  "bad hash changed M02 pointer")

            good1 = tty(script, b"1\ny\n0\n0\n")
            check(os.readlink(m01_root / "current") == "releases/" + M01_NEW,
                  "M01 old->new did not change only m01 pointer")
            check("原作者" in good1 or (m01_root / "current" / "vf-node.sh").is_file(),
                  "M01 UX2 UI not installed")
            good2 = tty(script, b"2\ny\n0\n0\n")
            check(os.readlink(m02_root / "current") == "releases/" + M02_NEW,
                  "M02 old->new did not change only m02 pointer")
            check("YABS" in good2 or (m02_root / "current" / "vps-audit.sh").is_file(),
                  "M02 UX2 UI not installed")
            check(sha(m02_root / "current" / "vps-audit.sh") == M02_NEW_SHA,
                  "M02 installed bytes not exact candidate source")
            # Current target can be re-entered without swapping versions again.
            tty(script, b"1\n0\n0\n", 25)
            tty(script, b"2\n0\n0\n", 25)
            check(os.readlink(m01_root / "current") == "releases/" + M01_NEW, "M01 no-op changed target")
            check(os.readlink(m02_root / "current") == "releases/" + M02_NEW, "M02 no-op changed target")

            run(["bash", str(script), "--rollback-m01", M01_OLD, "P07-M01:" + M01_OLD])
            run(["bash", str(script), "--rollback-m02", M02_OLD, "P07-M02:" + M02_OLD])
            check(os.readlink(m01_root / "current") == "releases/" + M01_OLD, "M01 rollback failed")
            check(os.readlink(m02_root / "current") == "releases/" + M02_OLD, "M02 rollback failed")
            for m, digest in sentinel.items():
                check(sha(MOD / m / "identity") == digest, f"other module {m} changed")
            print("P07_M01_M02_REAL_UX1_TO_UX2_ATOMIC_ROLLBACK=PASS")
            print("P07_M01_M02_CANCEL_AND_BAD_HASH=PASS")
            print("P07_M03_M04_M05_ISOLATION=PASS")
            print("M05_OWNER_ACCEPTANCE_UNCHANGED=YES")
            print("FORMAL_RELEASE=NO DISTRIBUTION=NO PRODUCTION=NO")
        finally:
            # The check above forbids pre-existing module data on this disposable runner.
            shutil.rmtree(MOD)


if __name__ == "__main__":
    main()
