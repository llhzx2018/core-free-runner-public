#!/usr/bin/env python3
"""Build three *unpublished* P07 UX candidate ZIPs from verified module files.

No GitHub Release, tag, public route, installer, VPS, or Production operation.
Packages have complete module-file inventories, but are NOT certified for
real installation/upgrade/rollback until the separate Formal Release gate.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FIXED_TIME = (2026, 11, 18, 0, 0, 0)
SHA256_LINE = re.compile(r"([0-9a-f]{64})  ([A-Za-z0-9_.\-/]+)")
GITBLOB_LINE = re.compile(r"([0-9a-f]{40})  ([A-Za-z0-9_.\-/]+)")
MODULES = (
    ("P07-M01", "网络代理节点（V2Ray）", "0.1.0-ux3"),
    ("P07-M02", "服务器性能检测（VPS 验机）", "2.1.1-ux3"),
    ("P07-M04", "服务器维护与安全", "0.1.0-ux5"),
)

def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def blob(b: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(b)).encode() + b"\0" + b).hexdigest()

def safe_path(name: str) -> None:
    p = PurePosixPath(name)
    if (not name or name.startswith("/") or name.endswith("/") or
            ".." in p.parts or "." in p.parts or "\\" in name or
            p.is_absolute() or len(p.parts) > 6):
        raise ValueError("unsafe package member")

def bytes_from(base: Path, rel: str) -> bytes:
    safe_path(rel)
    target = base / rel
    if not target.is_file() or target.is_symlink():
        raise ValueError("missing or linked module file: " + rel)
    return target.read_bytes()

def verified_inventory(base: Path, manifest: str, pattern: re.Pattern, digest) -> dict[str, bytes]:
    lines = bytes_from(base, manifest).decode("utf-8").splitlines()
    if not lines or len(lines) > 100:
        raise ValueError("unexpected module inventory size")
    files: dict[str, bytes] = {}
    for line in lines:
        match = pattern.fullmatch(line)
        if not match:
            raise ValueError("invalid published module manifest entry")
        expected, path = match.groups()
        if path in files:
            raise ValueError("duplicate module member")
        data = bytes_from(base, path)
        if digest(data) != expected:
            raise ValueError("published module manifest SHA mismatch")
        files[path] = data
    return files

def metadata(module: str, version: str, source: str, entry: bytes) -> bytes:
    return (json.dumps({
        "schema": "vf.p07.prepublish-ux-bundle.v1",
        "module": module, "candidate_version": version,
        "source": source, "entry_git_blob": blob(entry),
        "status": "DEVELOPMENT_STAGING_ONLY",
        "formal_release": False, "production_run": False,
        "owner_machine_touched": False,
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()

def make_m01() -> dict[str, bytes]:
    base = ROOT / "packages/p07-network-node/0.1.0-ux2"
    files = verified_inventory(base, "MANIFEST.sha256", SHA256_LINE, sha256)
    new = bytes_from(ROOT, "packages/p07-network-node/0.1.0-ux3/vf-node.sh")
    files["vf-node.sh"] = new
    files["VERSION"] = b"0.1.0-ux3\n"
    identity = files["SOURCE_IDENTITY"].decode()
    if "P07_NETWORK_NODE_VERSION=0.1.0-ux2" not in identity:
        raise ValueError("source M01 release identity mismatch")
    identity = identity.replace("P07_NETWORK_NODE_VERSION=0.1.0-ux2",
                                "P07_NETWORK_NODE_VERSION=0.1.0-ux3", 1)
    identity += "CANDIDATE_SOURCE_ONLY=YES\nDERIVED_FROM_RELEASED_UX2=YES\n"
    files["SOURCE_IDENTITY"] = identity.encode()
    files["MANIFEST.sha256"] = "".join(
        f"{sha256(data)}  {name}\n" for name, data in sorted(files.items())).encode()
    files["PREPUBLISH_METADATA.json"] = metadata(
        "P07-M01", "0.1.0-ux3", "released UX2 + isolated UX3 owner-facing entry", new)
    return files

def make_m02() -> dict[str, bytes]:
    new = bytes_from(ROOT, "experiments/p07-vps-audit-v21-ux3.sh")
    if b'BUILD_ID="2.1.1-ux3"' not in new:
        raise ValueError("M02 actual script version mismatch")
    return {"vps-audit.sh": new, "VERSION": b"2.1.1-ux3\n",
            "PREPUBLISH_METADATA.json": metadata("P07-M02", "2.1.1-ux3",
                                                 "released UX2 + isolated UX3 source", new)}

def make_m04() -> dict[str, bytes]:
    base = ROOT / "packages/p07-system-care/0.1.0-ux4"
    files = verified_inventory(base, "MANIFEST.gitblob", GITBLOB_LINE, blob)
    new = bytes_from(ROOT, "packages/p07-system-care/0.1.0-ux5/vf-system-care.sh")
    files["vf-system-care.sh"] = new
    files["VERSION"] = b"0.1.0-ux5\n"
    files["MANIFEST.gitblob"] = "".join(
        f"{blob(data)}  {name}\n" for name, data in sorted(files.items())).encode()
    files["PREPUBLISH_METADATA.json"] = metadata(
        "P07-M04", "0.1.0-ux5", "released UX4 + isolated UX5 owner-facing entry", new)
    return files

def write_zip(out: Path, files: dict[str, bytes]) -> str:
    if not files or "PREPUBLISH_METADATA.json" not in files:
        raise ValueError("incomplete module candidate")
    files = dict(files)
    files["SHA256SUMS"] = "".join(
        f"{sha256(data)}  {name}\n" for name, data in sorted(files.items())).encode()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            safe_path(name)
            info = zipfile.ZipInfo(name, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = ((0o100755 if name.endswith(".sh") else 0o100644) << 16)
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return sha256(out.read_bytes())

def verify_zip(path: Path, expected_module: str, expected_version: str) -> None:
    with zipfile.ZipFile(path) as z:
        files = {}
        for info in z.infolist():
            safe_path(info.filename)
            if info.filename in files or info.is_dir() or (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("duplicate or linked ZIP member")
            files[info.filename] = z.read(info.filename)
    sums = files.pop("SHA256SUMS").decode().splitlines()
    verified = {}
    for line in sums:
        match = SHA256_LINE.fullmatch(line)
        if not match:
            raise ValueError("malformed candidate SHA256SUMS")
        digest, name = match.groups()
        if name in verified or sha256(files[name]) != digest:
            raise ValueError("candidate tamper or duplicate")
        verified[name] = True
    if set(files) != set(verified):
        raise ValueError("unchecked candidate file")
    metadata = json.loads(files["PREPUBLISH_METADATA.json"])
    if (metadata["module"], metadata["candidate_version"]) != (expected_module, expected_version):
        raise ValueError("module/version mismatch")
    if metadata["formal_release"] or metadata["production_run"]:
        raise ValueError("unapproved release metadata")
    entry = {"P07-M01": "vf-node.sh", "P07-M02": "vps-audit.sh",
             "P07-M04": "vf-system-care.sh"}[expected_module]
    if blob(files[entry]) != metadata["entry_git_blob"]:
        raise ValueError("candidate runtime mismatch")

def main() -> None:
    parser = argparse.ArgumentParser(description="P07 UX development-only reproducible staging")
    parser.add_argument("--output-dir", type=Path, required=True)
    opts = parser.parse_args()
    dest = opts.output_dir.resolve()
    if dest == ROOT or ROOT in dest.parents:
        raise ValueError("must stage outside source repository")
    dest.mkdir(parents=True, exist_ok=True)
    if any(dest.iterdir()):
        raise ValueError("candidate output directory must be empty")
    hashes = []
    for (module, display, version), build in zip(MODULES, (make_m01, make_m02, make_m04)):
        name = f"{module}-{version}-UX-DEV-ONLY.zip"
        target = dest / name
        digest = write_zip(target, build())
        verify_zip(target, module, version)
        hashes.append((digest, name))
        print(f"{module} {display}: ZIP_VERIFIED_DEV_ONLY {digest}")
    (dest / "SHA256SUMS").write_text(
        "".join(f"{digest}  {name}\n" for digest, name in hashes))
    print("P07_UX_UNPUBLISHED_THREE_MODULE_PACKAGE_CANDIDATES=PASS")
    print("P07_FORMAL_RELEASE_DISTRIBUTION_PRODUCTION=NOT_RUN")

if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        sys.exit("P07_UX_STAGING_BLOCKED: " + str(exc))
