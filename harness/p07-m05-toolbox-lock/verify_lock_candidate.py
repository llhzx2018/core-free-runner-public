"""Exercise the published M05 installer and both guard versions in a test root."""
import hashlib
import importlib
from pathlib import Path
import os
import runpy
import sys
import tempfile
from unittest import mock


atomic_path, official, candidate = map(Path, sys.argv[1:])
installer = runpy.run_path(str(atomic_path))
install = installer["install"]
rollback = installer["rollback"]
error = installer["Unsafe"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_current(current, opt, data_directory=False):
    guard_path = str(current / "lib")
    sys.path.insert(0, guard_path)
    for module in ("m05_environment_guard", "m05_toolbox_backup_guard"):
        sys.modules.pop(module, None)
    guard = importlib.import_module("m05_environment_guard")
    sys.path.remove(guard_path)

    class MinimalHost(guard.HostProbe):
        def exists(self, path):
            return data_directory and path == "/var/lib/mysql"

        def children(self, path):
            return super().children(str(opt)) if path == "/opt" else ()

        def which(self, program):
            return program if program in ("ss", "ps", "systemctl", "dpkg-query") else None

        def run(self, cmd):
            return 0, {"ss": "LISTEN 0 128 0.0.0.0:22 0.0.0.0:*",
                       "ps": "systemd\nsshd\n", "systemctl": "ssh.service enabled\n",
                       "dpkg-query": "bash\tii\n"}[cmd[0]]

    real_lstat = Path.lstat

    def relocated(path):
        if path == Path("/opt") or path == Path("/opt/vf-server-ops.upgrade.lock"):
            path = opt / path.relative_to("/opt")
        return real_lstat(path)

    with mock.patch.object(Path, "lstat", relocated):
        return guard.inspect(MinimalHost())


assert os.getuid() == 0
with tempfile.TemporaryDirectory(prefix="p07-m05-lock-test-") as tmp:
    opt = Path(tmp) / "opt"
    opt.mkdir(mode=0o755)
    base = opt / "vfops-modules"
    base.mkdir()
    canaries = []
    for module in ("m01", "m02", "m04", "m03"):
        marker = base / module
        marker.write_text(module, encoding="ascii")
        canaries.append(marker)
    lock = opt / "vf-server-ops.upgrade.lock"
    lock.touch(mode=0o644)
    lock_inode = lock.lstat().st_ino
    before = {path: sha(path) for path in canaries}
    install.__globals__["BASE"] = base
    current = base / "m05/current"
    old = install(official, sha(official))
    initial = inspect_current(current, opt)
    assert initial.status == "OCCUPIED" and any(lock.name in x for x in initial.reasons)
    corrupt = opt / "corrupt.zip"
    corrupt.write_bytes(candidate.read_bytes() + b"damaged")
    try:
        install(corrupt, sha(candidate))
    except error:
        pass
    else:
        raise AssertionError("Damaged package was installed")
    assert current.readlink() == Path("releases") / old
    corrupt.unlink()
    new = install(candidate, sha(candidate))
    assert current.readlink() == Path("releases") / new
    assert inspect_current(current, opt).status == "CLEAN"
    assert inspect_current(current, opt, data_directory=True).status == "OCCUPIED"
    lock.chmod(0o666)
    assert inspect_current(current, opt).status == "OCCUPIED"
    lock.chmod(0o644)
    assert lock.lstat().st_ino == lock_inode and lock.read_bytes() == b""
    assert rollback(old, "P07-M05:" + old) == old
    assert current.readlink() == Path("releases") / old
    assert before == {path: sha(path) for path in canaries}
print("M05_OFFICIAL_BLOCK_REPRODUCED_AND_CANDIDATE_REGRESSION_PASSED")
print("M05_REAL_UPGRADE_CORRUPT_REJECTION_ROLLBACK_AND_MODULE_ISOLATION_PASSED")
