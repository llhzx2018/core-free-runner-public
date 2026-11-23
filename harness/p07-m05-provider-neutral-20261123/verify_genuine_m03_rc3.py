"""M05 admission proof from genuine public M03 147rc3 artifact, no VPS writes."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat
import sys
import tempfile
import zipfile

archive, source = (Path(arg).resolve() for arg in sys.argv[1:])
sys.path.insert(0, str(source / "lib"))
import m05_owner_trial_guard as guard

def sha1blob(data: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\x00" + data
    ).hexdigest()

with zipfile.ZipFile(archive) as z, tempfile.TemporaryDirectory(
    prefix="p07-m03-genuine-rc3-"
) as temp:
    prefix = "dist/p07/0.1.0/overlay/"
    entries = {}
    for name in z.namelist():
        if name.startswith(prefix) and not name.endswith("/"):
            name = name[len(prefix):]
            entries[name] = z.read(prefix + name)
    marker = entries.pop("RUNTIME.gitblob", None)
    assert marker is not None
    assert sha1blob(marker) == "06c79cf8595de625cc84d6a849d9e88fe01c4520"
    assert entries["BUILD_ID"].decode("ascii").strip() == "0.1.0-release147-rc3"
    runtime = Path(temp) / "vf-server-ops-ownertrial147rc3"
    runtime.mkdir(mode=0o755)
    for name in guard.REQUIRED_DIRS:
        (runtime / name).mkdir(mode=0o755)
    for path, data in entries.items():
        assert path == "BUILD_ID" or path.startswith(("bin/", "components/", "lib/")), path
        target = runtime / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (runtime / "VERSION").write_text("0.1.0\n", encoding="ascii")
    (runtime / ".runtime-manifest.gitblob").write_bytes(marker)
    assert guard.verified_p07_trial_runtime(runtime), "genuine M03 rc3 rejected"
    target = runtime / "BUILD_ID"
    original = target.read_bytes()
    target.write_bytes(b"0.1.0-release147-rc2\n")
    assert not guard.verified_p07_trial_runtime(runtime), "modified build accepted"
    target.write_bytes(original)
    assert guard.verified_p07_trial_runtime(runtime)
    (runtime / "lib" / "unexpected.py").write_bytes(b"print(123)\n")
    # An extra executable in lib/ must invalidate the apparent P07 runtime,
    # even though the embedded manifest still matches the official ZIP.
    assert not guard.verified_p07_trial_runtime(runtime), (
        "unlisted runnable application hidden inside P07 directory"
    )
print("P07_M05_GENUINE_PUBLISHED_M03_147RC3_RUNTIME_ACCEPTED=PASS")
print("P07_M05_M03_RUNTIME_TAMPERED_BUILD_REJECTED=PASS")
