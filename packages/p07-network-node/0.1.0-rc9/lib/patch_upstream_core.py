#!/usr/bin/env python3
"""Patch the exact pinned xyz690/v2ray snapshot to use a reproducible Core asset.

This does not change the VMess/mKCP/dtls profile logic. It only replaces the
mutable latest-release download functions inside src/download-v2ray.sh.
"""
from __future__ import annotations

import pathlib
import re
import sys


def replace_function(text: str, name: str, replacement: str) -> str:
    pattern = re.compile(rf"(?ms)^{re.escape(name)}\(\) \{{\n.*?^\}}\n")
    updated, count = pattern.subn(replacement.rstrip() + "\n", text, count=1)
    if count != 1:
        raise RuntimeError(f"expected exactly one {name}() function, got {count}")
    return updated


def main() -> int:
    if len(sys.argv) != 6:
        print(
            "usage: patch_upstream_core.py DOWNLOAD_SH VERSION AMD64_SHA ARM64_SHA EXPECTED_UPSTREAM_COMMIT",
            file=sys.stderr,
        )
        return 2

    path = pathlib.Path(sys.argv[1])
    version, amd64_sha, arm64_sha, expected_commit = sys.argv[2:]

    if not re.fullmatch(r"v[0-9]+(?:\.[0-9]+){2}", version):
        raise RuntimeError("invalid pinned Core version")
    for value in (amd64_sha, arm64_sha, expected_commit):
        if not re.fullmatch(r"[0-9a-f]{40,64}", value):
            raise RuntimeError("invalid immutable identity")

    original = path.read_text(encoding="utf-8")
    required_markers = (
        'v2ray_repos_url="https://api.github.com/repos/v2fly/v2ray-core/releases/latest',
        'wget --no-check-certificate -O "$v2ray_tmp_file"',
    )
    for marker in required_markers:
        if marker not in original:
            raise RuntimeError(f"upstream drift: required marker missing: {marker}")

    get_latest = f'''_get_latest_version() {{
\tv2ray_latest_ver="{version}"
}}
'''

    download = f'''_download_v2ray_file() {{
\t[[ ! $v2ray_latest_ver ]] && _get_latest_version
\tv2ray_tmp_file="/tmp/v2ray.zip"
\tcase "$v2ray_bit" in
\t\t64)
\t\t\tv2ray_asset="v2ray-linux-64.zip"
\t\t\tv2ray_expected_sha256="{amd64_sha}"
\t\t\t;;
\t\tarm64-v8a)
\t\t\tv2ray_asset="v2ray-linux-arm64-v8a.zip"
\t\t\tv2ray_expected_sha256="{arm64_sha}"
\t\t\t;;
\t\t*)
\t\t\techo -e "\\n $red P07 固定 Core 暂不支持当前架构: $v2ray_bit $none\\n"
\t\t\texit 1
\t\t\t;;
\tesac
\tv2ray_download_link="https://github.com/v2fly/v2ray-core/releases/download/$v2ray_latest_ver/$v2ray_asset"

\tif ! curl --fail --location --silent --show-error --proto '=https' --tlsv1.2 \\
\t\t--output "$v2ray_tmp_file" "$v2ray_download_link"; then
\t\techo -e "\\n $red 下载固定 V2Ray Core 失败，请检查 VPS 网络后重试。$none\\n"
\t\texit 1
\tfi

\tif ! printf '%s  %s\\n' "$v2ray_expected_sha256" "$v2ray_tmp_file" | sha256sum -c - >/dev/null; then
\t\techo -e "\\n $red V2Ray Core SHA256 校验失败，已停止安装。$none\\n"
\t\trm -f "$v2ray_tmp_file"
\t\texit 1
\tfi

\tunzip -o "$v2ray_tmp_file" -d "/usr/bin/v2ray/"
\tchmod +x /usr/bin/v2ray/v2ray
\tif ! grep -Fq 'alias v2ray=' /root/.bashrc 2>/dev/null; then
\t\techo "alias v2ray=$_v2ray_sh" >>/root/.bashrc
\tfi
}}
'''

    patched = replace_function(original, "_get_latest_version", get_latest)
    patched = replace_function(patched, "_download_v2ray_file", download)

    forbidden = ("releases/latest", "--no-check-certificate")
    for marker in forbidden:
        if marker in patched:
            raise RuntimeError(f"unsafe mutable download marker remains after patch: {marker}")

    audit_banner = (
        f"# P07_CORE_PIN_PATCHED=1\n"
        f"# P07_UPSTREAM_COMMIT={expected_commit}\n"
        f"# P07_V2RAY_CORE_VERSION={version}\n"
    )
    path.write_text(audit_banner + patched, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
