#!/usr/bin/env python3
"""P07-M05 新服务器初始化: bounded, Owner-confirmed Python-cache quarantine.

This helper neither installs code nor changes CloudPanel, database, another
module, DNS or the current version pointer. It only moves a verified
lib/__pycache__ *directory*, with no symlinks or unknown contents, out of an
otherwise byte-identical installed M05 release. No deletion, no auto repair.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import uuid

HOME = Path("/opt/vfops-modules/m05")
BASE = HOME.parent
RELEASES = HOME / "releases"
CURRENT = HOME / "current"
LOCK = HOME / ".install.lock"
CACHE_DIR = "lib/__pycache__"
ALLOWED_BUILDS = frozenset({
    "0.1.0-m05-candidate2",
    "0.1.0-m05-existing-safe1",
    "0.1.0-m05-clean-host-guard1",
    "0.1.0-m05-pycache-safe1",
})
METADATA = {"VERSION", "BUILD_ID", "MODULE_ID", "MODULE_BUILD_ID"}
BINARIES = {"bin/vfops-init-entry", "bin/vfops-init-ui", "bin/vfops-init-core"}
CACHE_PATTERN = re.compile(
    r"lib/__pycache__/([A-Za-z_][A-Za-z0-9_]*)"
    r"\.cpython-[0-9]{2,3}(?:\.opt-[0-2])?\.pyc"
)


class Unsafe(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def fail(reason: str) -> None:
    raise Unsafe(reason)


def safe_dir(path: Path) -> None:
    if path.is_symlink() or not path.is_dir():
        fail("MODULE_DIRECTORY_UNSAFE")
    if path.stat().st_uid != 0:
        fail("MODULE_NOT_ROOT_OWNED")


def state() -> tuple[str, int]:
    """Read-only verified scan; no execution of M05 code or bytecode."""
    safe_dir(BASE)
    safe_dir(HOME)
    safe_dir(RELEASES)
    if not CURRENT.is_symlink():
        fail("CURRENT_NOT_MODULE_SYMLINK")
    link = os.readlink(CURRENT)
    if not re.fullmatch(r"releases/[A-Za-z0-9._-]{1,64}", link):
        fail("CURRENT_LINK_UNSAFE")
    build = link.partition("/")[2]
    if build not in ALLOWED_BUILDS:
        fail("UNSUPPORTED_LOCAL_BUILD")
    release = RELEASES / build
    safe_dir(release)
    manifest_file = release / "MODULE_MANIFEST.json"
    if manifest_file.is_symlink() or not manifest_file.is_file():
        fail("MODULE_MANIFEST_MISSING")
    try:
        data = json.loads(manifest_file.read_text("utf-8"))
    except (ValueError, UnicodeError):
        fail("MODULE_MANIFEST_INVALID")
    if not isinstance(data, dict):
        fail("MODULE_MANIFEST_INVALID")
    if (data.get("schema") != "vf.p07.module-bundle.v1"
            or data.get("module_id") != "P07-M05"
            or data.get("module_name") != "新服务器初始化"
            or data.get("module_build_id") != build
            or data.get("entrypoint") != "bin/vfops-init-entry"
            or data.get("installation_isolation") != "P07-M05_ONLY"):
        fail("MODULE_IDENTITY_MISMATCH")
    files = data.get("files")
    if not isinstance(files, dict) or not 20 <= len(files) <= 400:
        fail("MODULE_FILE_MANIFEST_INVALID")
    if not BINARIES.issubset(files) or not METADATA.issubset(files):
        fail("MODULE_REQUIRED_FILE_MISSING")
    declared = set(files)
    expected_dirs: set[str] = set()
    for name, expected in files.items():
        if not isinstance(name, str) or not isinstance(expected, str):
            fail("MODULE_FILE_MANIFEST_INVALID")
        path = PurePosixPath(name)
        if (not name.isascii() or path.is_absolute() or "\\" in name
                or ".." in path.parts or "." in path.parts
                or "//" in name or name.startswith(".")
                or not re.fullmatch(r"[a-f0-9]{64}", expected)
                or not (name.startswith(("lib/", "bin/")) or name in METADATA)):
            fail("MODULE_FILE_MANIFEST_INVALID")
        for parent in path.parents:
            if str(parent) != ".":
                expected_dirs.add(str(parent))
        file = release / name
        if file.is_symlink() or not file.is_file():
            fail("MODULE_FILE_TYPE_MISMATCH")
        if hashlib.sha256(file.read_bytes()).hexdigest() != expected:
            fail("MODULE_CODE_DIGEST_MISMATCH")
    if (release / "MODULE_ID").read_bytes() != b"P07-M05\n":
        fail("MODULE_IDENTITY_MISMATCH")
    if (release / "MODULE_BUILD_ID").read_bytes() != (build + "\n").encode():
        fail("MODULE_IDENTITY_MISMATCH")

    seen_files: set[str] = set()
    seen_dirs: set[str] = set()
    caches: set[str] = set()
    cache_size = 0
    for item in release.rglob("*"):
        rel = item.relative_to(release).as_posix()
        if item.is_symlink():
            fail("MODULE_UNEXPECTED_SYMLINK")
        if item.is_dir():
            seen_dirs.add(rel)
            continue
        if not item.is_file():
            fail("MODULE_UNEXPECTED_FILE_TYPE")
        seen_files.add(rel)
        if rel in declared or rel == "MODULE_MANIFEST.json":
            continue
        match = CACHE_PATTERN.fullmatch(rel)
        if (not match or "lib/" + match.group(1) + ".py" not in declared):
            fail("MODULE_UNLISTED_RUNTIME_FILE")
        info = item.stat()
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or info.st_uid != 0 or info.st_size > 1_048_576):
            fail("CACHE_FILE_UNSAFE")
        caches.add(rel)
        cache_size += info.st_size
        if len(caches) > 400 or cache_size > 24 * 1024 * 1024:
            fail("CACHE_LIMIT_EXCEEDED")
    if seen_files != declared | {"MODULE_MANIFEST.json"} | caches:
        fail("MODULE_UNLISTED_RUNTIME_FILE")
    if caches:
        if seen_dirs != expected_dirs | {CACHE_DIR}:
            fail("MODULE_UNKNOWN_DIRECTORY")
        cache_root = release / CACHE_DIR
        if cache_root.is_symlink() or not cache_root.is_dir():
            fail("CACHE_DIRECTORY_UNSAFE")
    elif seen_dirs != expected_dirs:
        fail("MODULE_UNKNOWN_DIRECTORY")
    return build, len(caches)


def inspect() -> int:
    try:
        build, count = state()
    except (Unsafe, OSError, UnicodeError, ValueError, TypeError) as exc:
        code = exc.reason if isinstance(exc, Unsafe) else "UNVERIFIED_FILE_STATE"
        print("P07_M05_REPAIR_STATUS=BLOCKED")
        print("P07_M05_REPAIR_REASON=" + code)
        return 13
    if count:
        print("P07_M05_REPAIR_STATUS=CACHE_ONLY")
        print("P07_M05_REPAIR_BUILD=" + build)
        print("P07_M05_REPAIR_PYC_COUNT=" + str(count))
    else:
        print("P07_M05_REPAIR_STATUS=ALREADY_CLEAN")
    return 0


def recover(build: str, confirm: str) -> int:
    if os.geteuid() != 0 or build not in ALLOWED_BUILDS:
        fail("RECOVERY_REQUIRES_ROOT_AND_SUPPORTED_BUILD")
    if confirm != "P07-M05:CACHE:" + build:
        fail("RECOVERY_EXPLICIT_CONFIRMATION_MISSING")
    safe_dir(BASE)
    safe_dir(HOME)
    safe_dir(RELEASES)
    if LOCK.is_symlink() or (LOCK.exists() and not LOCK.is_file()):
        fail("MODULE_INSTALL_LOCK_UNSAFE")
    handle = os.open(LOCK, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(handle, "w") as guard:
        fcntl.flock(guard, fcntl.LOCK_EX)
        actual, count = state()
        if actual != build or count == 0:
            fail("RECOVERY_TARGET_CHANGED")
        source = RELEASES / build / CACHE_DIR
        quarantine = HOME / ".cache-quarantine"
        if quarantine.is_symlink() or (quarantine.exists() and not quarantine.is_dir()):
            fail("CACHE_QUARANTINE_DIRECTORY_UNSAFE")
        quarantine.mkdir(mode=0o700, exist_ok=True)
        quarantine.chmod(0o700)
        target = quarantine / ("pycache-" + build + "-" + uuid.uuid4().hex)
        # Recheck under the same install lock; moves only generated cache,
        # preserves all byte-verified source files and M05 version pointer.
        if not source.is_dir() or source.is_symlink() or target.exists():
            fail("CACHE_DIRECTORY_CHANGED")
        source.rename(target)
        verified, remaining = state()
        if verified != build or remaining:
            fail("RECOVERY_POSTCHECK_FAILED")
    print("P07_M05_CACHE_QUARANTINED=YES")
    print("P07_M05_REPAIR_BUILD=" + build)
    print("P07_M05_CACHE_FILES_PRESERVED=" + str(count))
    print("P07_M05_MODULE_POINTER_UNCHANGED=YES")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P07-M05 新服务器初始化 · 缓存误拦截安全检查")
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("inspect")
    op = sub.add_parser("recover")
    op.add_argument("--build", required=True)
    op.add_argument("--confirm", required=True)
    args = parser.parse_args(argv)
    if args.mode == "inspect":
        return inspect()
    try:
        return recover(args.build, args.confirm)
    except (Unsafe, OSError, UnicodeError, ValueError, TypeError) as exc:
        code = exc.reason if isinstance(exc, Unsafe) else "RECOVERY_UNVERIFIED"
        print("P07_M05_CACHE_RECOVERY=BLOCKED", file=sys.stderr)
        print("P07_M05_RECOVERY_REASON=" + code, file=sys.stderr)
        return 13


if __name__ == "__main__":
    raise SystemExit(main())
