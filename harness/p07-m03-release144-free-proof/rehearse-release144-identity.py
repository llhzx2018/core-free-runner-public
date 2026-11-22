#!/usr/bin/env python3
"""Rehearse the next P07-M03 build identity in an isolated workspace.

This release-only transform adjusts BUILD_ID, the runtime Git Blob manifest,
and the embedded installer pins. It cannot alter business runtime files.
No GitHub writes or private-source references are performed by this program.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile

RC_BUILD = "0.1.0-release144-rc4"
FORMAL_BUILD = "0.1.0-release144"
RC_SHA256 = "de1d1bbd2c3b09c8d3d031fb24944da35ab8e27b8e557ae0c43cb3a2cbedfd7e"
OVERLAY = "dist/p07/0.1.0/overlay/"
MANIFEST = OVERLAY + "RUNTIME.gitblob"
MARKER = OVERLAY + "BUILD_ID"
INSTALLER = "installers/p07-final.sh"
ALLOW_CHANGE = frozenset({MANIFEST, MARKER, INSTALLER})


class FormalBuildBlocked(ValueError):
    pass


def git_blob(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def trusted_zip(source: Path) -> dict[str, bytes]:
    if not source.is_file() or source.is_symlink():
        raise FormalBuildBlocked("SOURCE_NOT_REGULAR")
    if digest(source.read_bytes()) != RC_SHA256:
        raise FormalBuildBlocked("RC_SOURCE_SHA_MISMATCH")
    files = {}
    cumulative = 0
    try:
        with zipfile.ZipFile(source) as archive:
            if not 50 <= len(archive.infolist()) <= 240:
                raise FormalBuildBlocked("PACKAGE_FILE_COUNT")
            for info in archive.infolist():
                name = info.filename
                rel = PurePosixPath(name)
                if (name in files or not name.isascii() or len(name) > 240
                        or name.startswith("-") or ".." in rel.parts
                        or "\\" in name or info.is_dir()
                        or stat.S_IFMT(info.external_attr >> 16) != stat.S_IFREG
                        or info.file_size > 64 * 1024 * 1024):
                    raise FormalBuildBlocked("UNSAFE_PACKAGE_MEMBER")
                if not re.fullmatch(
                    r"(?:dist/p07/0[.]1[.]0/overlay/(?:bin|lib|components)/[A-Za-z0-9_./-]+"
                    r"|dist/p07/0[.]1[.]0/overlay/(?:BUILD_ID|RUNTIME[.]gitblob)"
                    r"|dist/p07/0[.]1[.]0-rc2/P07_VF_SERVER_OPS_0[.]1[.]0-rc2[.]tar[.]gz"
                    r"|installers/p07-final[.]sh)", name
                ):
                    raise FormalBuildBlocked("UNDECLARED_PACKAGE_MEMBER")
                cumulative += info.file_size
                if cumulative > 110 * 1024 * 1024:
                    raise FormalBuildBlocked("PACKAGE_BOMB_LIMIT")
                files[name] = archive.read(info)
    except (OSError, zipfile.BadZipFile, RuntimeError, ValueError):
        raise FormalBuildBlocked("UNTRUSTED_PACKAGE") from None
    if files.get(MARKER) != (RC_BUILD + "\n").encode():
        raise FormalBuildBlocked("RC_BUILD_ID_MISMATCH")
    return files


def validate_manifest(files: dict[str, bytes]) -> list[str]:
    try:
        lines = files[MANIFEST].decode("ascii").splitlines()
    except (KeyError, UnicodeError):
        raise FormalBuildBlocked("MANIFEST_INVALID") from None
    if not 50 <= len(lines) <= 240:
        raise FormalBuildBlocked("MANIFEST_COUNT")
    rels = []
    for line in lines:
        m = re.fullmatch(r"([a-f0-9]{40})  ((?:bin|lib|components)/[A-Za-z0-9_./-]+|BUILD_ID)", line)
        if m is None:
            raise FormalBuildBlocked("MANIFEST_ENTRY")
        expected, rel = m.groups()
        if rel in rels or ".." in PurePosixPath(rel).parts:
            raise FormalBuildBlocked("MANIFEST_DUPLICATE")
        if git_blob(files.get(OVERLAY + rel, b"")) != expected:
            raise FormalBuildBlocked("MANIFEST_BLOB_MISMATCH")
        rels.append(rel)
    other = {OVERLAY + rel for rel in rels} | {
        MANIFEST, INSTALLER, "dist/p07/0.1.0-rc2/P07_VF_SERVER_OPS_0.1.0-rc2.tar.gz",
    }
    if set(files) != other:
        raise FormalBuildBlocked("FILE_CLOSURE_MISMATCH")
    if not {"BUILD_ID", "bin/vfops-migrate-ui",
            "components/p07-m03-migration-readiness.sh",
            "lib/migration_preparation_checklist.py",
            "lib/migration_target_inventory_guard.py",
            "lib/server_migration_pull.py"}.issubset(rels):
        raise FormalBuildBlocked("D04_RUNTIME_CLOSURE_MISSING")
    return rels


def replace_once(txt: str, original: str, new: str) -> str:
    if txt.count(original) != 1:
        raise FormalBuildBlocked("INSTALLER_IDENTITY_AMBIGUOUS")
    return txt.replace(original, new, 1)


def promote(source: Path, target: Path) -> dict[str, str | int]:
    if target.exists() or target.is_symlink() or target.resolve() == source.resolve():
        raise FormalBuildBlocked("DESTINATION_MUST_BE_ABSENT")
    files = trusted_zip(source)
    rels = validate_manifest(files)
    old_manifest = git_blob(files[MANIFEST])
    files[MARKER] = (FORMAL_BUILD + "\n").encode()
    files[MANIFEST] = ("\n".join(
        git_blob(files[OVERLAY + rel]) + "  " + rel for rel in rels
    ) + "\n").encode("ascii")
    new_manifest = git_blob(files[MANIFEST])
    try:
        script = files[INSTALLER].decode("utf-8")
    except UnicodeError:
        raise FormalBuildBlocked("INSTALLER_ENCODING_INVALID") from None
    script = replace_once(script,
                          'EXPECTED_BUILD_ID="' + RC_BUILD + '"',
                          'EXPECTED_BUILD_ID="' + FORMAL_BUILD + '"')
    script = replace_once(script,
                          'RUNTIME_MANIFEST_BLOB="' + old_manifest + '"',
                          'RUNTIME_MANIFEST_BLOB="' + new_manifest + '"')
    files[INSTALLER] = script.encode("utf-8")
    if validate_manifest(files) != rels:
        raise FormalBuildBlocked("FINAL_MANIFEST_REJECTED")
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9, allowZip64=False) as archive:
        for name, raw in sorted(files.items()):
            entry = zipfile.ZipInfo(name, (2026, 11, 20, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, raw, compress_type=zipfile.ZIP_DEFLATED,
                             compresslevel=9)
    final_files = trusted_zip_final(target)
    if set(final_files) != set(files) or any(
            final_files[k] != v for k, v in files.items()):
        raise FormalBuildBlocked("FINAL_ARCHIVE_MISMATCH")
    return {"sha256": digest(target.read_bytes()), "size": target.stat().st_size,
            "runtime_manifest_blob": new_manifest,
            "installer_blob": git_blob(files[INSTALLER]),
            "manifest_members": len(rels)}


def trusted_zip_final(path: Path) -> dict[str, bytes]:
    # Final ZIP is freshly created, but always parse/read its compressed bytes.
    files = {}
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if info.filename in files:
                raise FormalBuildBlocked("FINAL_DUPLICATE_FILE")
            files[info.filename] = archive.read(info)
    return files


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rc", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ns = ap.parse_args()
    try:
        receipt = promote(ns.rc, ns.out)
    except (FormalBuildBlocked, OSError, UnicodeError, ValueError) as exc:
        code = str(exc) if isinstance(exc, FormalBuildBlocked) else "FILESYSTEM_ERROR"
        print("P07_M03_REHEARSAL144_BUILD=BLOCKED:" + code)
        return 13
    print("P07_M03_REHEARSAL144_BUILD=PASS")
    for key, value in receipt.items():
        print(f"P07_M03_REHEARSAL144_{key.upper()}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
