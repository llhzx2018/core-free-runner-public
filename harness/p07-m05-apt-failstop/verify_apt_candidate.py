"""Upgrade the isolated M05 install and run the shipped UI failure-gate tests."""
import hashlib
from pathlib import Path
import os
import runpy
import shutil
import subprocess
import sys
import tempfile

atomic, official, candidate, test = (Path(p).resolve() for p in sys.argv[1:])

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

engine = runpy.run_path(str(atomic))
install, rollback = engine["install"], engine["rollback"]
with tempfile.TemporaryDirectory(prefix="p07-m05-apt-proof-") as tmp:
    base = Path(tmp)/"modules"
    base.mkdir()
    canaries = {base / name: name.encode() for name in ("m01","m02","m03","m04")}
    for path, data in canaries.items():
        path.write_bytes(data)
    install.__globals__["BASE"] = base
    current = base / "m05/current"
    old = install(official, digest(official))
    invalid = Path(tmp) / "damaged.zip"
    invalid.write_bytes(candidate.read_bytes() + b"bad")
    try:
        install(invalid, digest(candidate))
    except engine["Unsafe"]:
        pass
    else:
        raise AssertionError("Corrupt candidate installed")
    assert current.readlink() == Path("releases") / old
    new = install(candidate, digest(candidate))
    assert current.readlink() == Path("releases") / new
    sandbox = Path(tmp) / "test-root"
    (sandbox / "tests").mkdir(parents=True)
    for item in ("bin", "lib"):
        (sandbox / item).symlink_to(current / item, target_is_directory=True)
    copied = sandbox / "tests" / test.name
    shutil.copyfile(test, copied)
    subprocess.run([sys.executable, "-B", str(copied), "-q"],
                   cwd=sandbox, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                   check=True, timeout=75)
    assert rollback(old, "P07-M05:" + old) == old
    assert current.readlink() == Path("releases") / old
    assert all(path.read_bytes() == data for path, data in canaries.items())
print("M05_INSTALLED_APT_FAILSTOP_AND_UPGRADE_ROLLBACK_PASSED")
