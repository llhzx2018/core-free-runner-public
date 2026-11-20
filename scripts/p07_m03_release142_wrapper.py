#!/usr/bin/env python3
"""Exact pinned public P07-M03 release142 wrapper from existing 141 wrapper.

No network or release writes. Same application and trusted-version policy;
only version/ZIP/hash/manifest/installer identity and asset ID may change.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import re
import sys

SHA = re.compile(r"[0-9a-f]{64}\Z")
BLOB = re.compile(r"[0-9a-f]{40}\Z")


def replace_once(text: str, original: str, new: str) -> str:
    if text.count(original) != 1:
        raise ValueError("WRAPPER_SOURCE_NOT_EXACT_141")
    return text.replace(original, new, 1)


def generate(source: Path, target: Path, zip_sha: str, manifest_blob: str,
             installer_blob: str, asset_id: str) -> None:
    if (not SHA.fullmatch(zip_sha) or not BLOB.fullmatch(manifest_blob)
            or not BLOB.fullmatch(installer_blob)
            or not re.fullmatch(r"[0-9]{1,12}", asset_id)):
        raise ValueError("WRAPPER_TARGET_ID_INVALID")
    if target.exists() or target.is_symlink() or source.resolve() == target.resolve():
        raise ValueError("WRAPPER_TARGET_NOT_ABSENT")
    content = source.read_text(encoding="utf-8")
    known = (
      ("BUILD='0.1.0-release141'", "BUILD='0.1.0-release142'"),
      ('if (manifest.parent/"BUILD_ID").read_text().strip()!="0.1.0-release141": raise ValueError("build")',
       'if (manifest.parent/"BUILD_ID").read_text().strip()!="0.1.0-release142": raise ValueError("build")'),
      ('p07-m03-release141.XXXXXXXX','p07-m03-release142.XXXXXXXX'),
      ("RELEASE='p07-m03-v0.1.0-release141-limited-20261119'",
       "RELEASE='p07-m03-v0.1.0-release142-20261120'"),
      ("ZIP_NAME='P07-M03-0.1.0-release141.zip'",
       "ZIP_NAME='P07-M03-0.1.0-release142.zip'"),
      ("ZIP_SHA256='22c23818bc7268e6d3d95bc2552f42a5a3c12e97e387fdc542d59934c658b6d1'",
       f"ZIP_SHA256='{zip_sha}'"),
      ("RUNTIME_BLOB='6a3a949064ffb8fe1df56e7bc555173b5ca9cf3b'",
       f"RUNTIME_BLOB='{manifest_blob}'"),
      ("INSTALLER_BLOB='e2994e434fb7fb8c9f2cc33d986e5b269300acc0'",
       f"INSTALLER_BLOB='{installer_blob}'"),
      ('ASSET_API_URL="https://api.github.com/repos/llhzx2018/core-free-runner-public/releases/assets/767910493"',
       f'ASSET_API_URL="https://api.github.com/repos/llhzx2018/core-free-runner-public/releases/assets/{asset_id}"'),
    )
    for old, new in known:
        content = replace_once(content, old, new)
    anchor = '    "0.1.0-release141":"6a3a949064ffb8fe1df56e7bc555173b5ca9cf3b",'
    content = replace_once(
        content, anchor,
        anchor + '\n    "0.1.0-release142":"' + manifest_blob + '",'
    )
    content = replace_once(
        content,
        "# P07-M03 网站与数据 / D04 服务器迁移：非切换 release141。",
        "# P07-M03 网站与数据 / D04 服务器迁移：非切换 release142。"
    )
    if "rm -rf -- \"$m03_previous\"" in content:
        raise ValueError("WRAPPER_BACKUP_DESTRUCTION")
    if not all(x in content for x in (
        'verified_m03_build "$m03_previous"',
        'mv -nT -- "$m03_previous" "$m03_archive"',
        'flock -x "$m03_lock_fd"',
        "m03_rotation=1",
        'P07_NO_EXEC=1 bash "$tmp/files/installers/p07-final.sh"',
    )):
        raise ValueError("WRAPPER_RECOVERY_GUARD_MISSING")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--base-wrapper", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--zip-sha256", required=True)
    ap.add_argument("--runtime-blob", required=True)
    ap.add_argument("--installer-blob", required=True)
    ap.add_argument("--asset-id", required=True)
    v=ap.parse_args()
    try:
        generate(v.base_wrapper,v.out,v.zip_sha256,v.runtime_blob,
                 v.installer_blob,v.asset_id)
    except (ValueError,OSError,UnicodeError):
        print("P07_M03_142_WRAPPER_GENERATION=BLOCKED")
        return 13
    print("P07_M03_142_WRAPPER_GENERATION=PASS")
    return 0


if __name__=="__main__":
    sys.exit(main())
