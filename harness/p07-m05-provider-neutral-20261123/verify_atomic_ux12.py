"""Test genuine official UX12 to isolated M05 candidate without touching Owner VPS."""
import hashlib
from pathlib import Path
import os
import runpy
import shutil
import subprocess
import sys
import tempfile

atomic, official, candidate, test = (Path(arg).resolve() for arg in sys.argv[1:])

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

engine = runpy.run_path(str(atomic))
install = engine["install"]
rollback = engine["rollback"]
Unsafe = engine["Unsafe"]
before = "0.1.0-m05-ux12-apt-failstop"
after = "0.1.0-m05-ux13-provider-neutral"

with tempfile.TemporaryDirectory(prefix="p07-m05-generic-atomic-") as temp:
    root = Path(temp) / "modules"
    root.mkdir()
    canaries = {root / x: ("KEEP_" + x).encode("ascii") for x in
                ("m01", "m02", "m03", "m04")}
    for target, payload in canaries.items():
        target.write_bytes(payload)
    install.__globals__["BASE"] = root
    current = root / "m05/current"
    assert install(official, digest(official)) == before
    assert current.is_symlink() and current.readlink() == Path("releases") / before

    bad = Path(temp) / "broken.zip"
    bad.write_bytes(candidate.read_bytes() + b"modified")
    try:
        install(bad, digest(candidate))
    except Unsafe:
        pass
    else:
        raise AssertionError("Corrupted candidate was accepted")
    assert current.readlink() == Path("releases") / before
    assert install(candidate, digest(candidate)) == after
    assert current.readlink() == Path("releases") / after
    installed = root / "m05/releases" / after
    assert (installed / "lib/m05_owner_trial_guard.py").is_file()
    assert (installed / "lib/m05_passive_image_helpers.py").is_file()
    assert (installed / "MODULE_BUILD_ID").read_text().strip() == after
    assert all(p.read_bytes() == data for p, data in canaries.items())

    sandbox = Path(temp) / "sandbox"
    (sandbox / "tests").mkdir(parents=True)
    for item in ("bin", "lib"):
        (sandbox / item).symlink_to(installed / item, target_is_directory=True)
    shutil.copyfile(test, sandbox / "tests" / test.name)
    subprocess.run(
        [sys.executable, "-B", str(sandbox / "tests" / test.name), "-q"],
        cwd=sandbox, env={**os.environ, "NO_COLOR": "1", "PYTHONDONTWRITEBYTECODE": "1"},
        timeout=95, check=True,
    )
    assert rollback(before, "P07-M05:" + before) == before
    assert current.readlink() == Path("releases") / before
    assert all(p.read_bytes() == data for p, data in canaries.items())
    assert (root / "m05/releases" / after).exists()
print("M05_GENUINE_UX12_ATOMIC_UPGRADE_BAD_BUNDLE_ROLLBACK=PASS")
print("M05_OTHER_FOUR_MODULES_UNCHANGED=PASS")
