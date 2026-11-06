#!/usr/bin/env python3
"""A generated single-file Atomic package must never queue an infinite EX lock."""
from __future__ import annotations
import importlib.util
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("p01_atomic_builder_v2", root / "p01-build-release-v2.py")
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
source = {"VERSION.txt": b"2.47.499\n", "app/thing.php": b"<?php return 1;\n"}
target = {"VERSION.txt": b"2.47.500\n", "app/thing.php": b"<?php return 2;\n"}
repair = module.build_repair(source, target, "")
assert "$global=VfMaintenanceBarrier::globalExclusive(true);" in repair
assert "$global=VfMaintenanceBarrier::globalExclusive();" not in repair
assert "vf_request_global_barrier_release()" in repair
for required in ("recoverInterrupted(", "snapshotDb(", "restoreDb(", "restoreFiles(",
                 "source-meta.json", "p01-atomic-transaction.json",
                 "self::verifySource", "self::verifyTarget", "finally {if(isset($global))$global->release();}"):
    assert required in repair, f"Safety clause omitted: {required}"
with tempfile.TemporaryDirectory(prefix="p01-builder-proof-") as folder:
    filename = Path(folder)/"repair.php"
    filename.write_text(repair, encoding="utf-8")
    lint=subprocess.run(["php","-l",str(filename)],check=True,capture_output=True,text=True)
    assert "No syntax errors" in lint.stdout
    check=subprocess.run(["php",str(filename),"--self-test"],check=True,capture_output=True,text=True)
    assert '"ok":true' in check.stdout
print("P01_ATOMIC_BUILDER_NONQUEUED_EX=PASS")
