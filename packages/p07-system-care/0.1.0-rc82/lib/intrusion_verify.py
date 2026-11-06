#!/usr/bin/env python3
"""Owner-triggered, read-only provenance checks. Never executes PHP or changes baselines."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import stat
import sys
import urllib.parse
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path

from intrusion_state import read_json
from intrusion_evidence import load_events_consistent, status_doc

MAX_EVENTS = 5000
MAX_UNIQUE = 80
MAX_SITE = 12
MAX_FILE = 8 * 1024 * 1024
MAX_HTTP = 7 * 1024 * 1024
GIT_ORG = "llhzx2018"
SOURCE = {
    "vf-ops": ("S01-C02", "vf-tools-ops", "vf-ops.php"),
    "vf-tool-m3u8": ("S01-C03", "vf-tools-m3u8", "vf-tool-m3u8.php"),
}


def clean_label(value: object) -> str:
    return "".join(" " if ord(c) < 32 or 127 <= ord(c) <= 159 else c
                   for c in str(value or "-"))[:180]


def safe_relative(value: object) -> str | None:
    if not isinstance(value, str) or not value or len(value) > 500:
        return None
    if "\\" in value or "\x00" in value or value.startswith("/"):
        return None
    segments = value.split("/")
    if any(s in {"", ".", ".."} for s in segments):
        return None
    return value


def guarded_read(root: Path, rel: str, cap: int = MAX_FILE) -> bytes:
    name = safe_relative(rel)
    if not name:
        raise ValueError("unsafe relative path")
    # Reject redirects through symlink parents and the file itself.
    path = root / name
    if path.resolve(strict=True) != path:
        raise ValueError("symlink path refused")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > cap:
            raise ValueError("unsafe file type or size")
        pieces = []
        size = 0
        while True:
            data = os.read(fd, min(1024 * 1024, cap + 1 - size))
            if not data:
                break
            size += len(data)
            if size > cap:
                raise ValueError("read size exceeded")
            pieces.append(data)
        after = os.fstat(fd)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
            raise ValueError("file changed during read")
        return b"".join(pieces)
    finally:
        os.close(fd)


class OriginRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parts = urllib.parse.urlsplit(newurl)
        host = (parts.hostname or "").lower()
        allowed = host in {"api.wordpress.org", "raw.githubusercontent.com", "github.com",
                           "api.github.com", "objects.githubusercontent.com",
                           "release-assets.githubusercontent.com"}
        if parts.scheme != "https" or not allowed:
            raise ValueError("unexpected release source redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def https_get(url: str, cap: int = MAX_HTTP) -> bytes:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in {
        "api.wordpress.org", "raw.githubusercontent.com", "github.com", "api.github.com"
    }:
        raise ValueError("untrusted origin")
    opener = urllib.request.build_opener(OriginRedirect)
    request = urllib.request.Request(url, headers={"User-Agent": "VF-P07-ReadOnly-Provenance/1.0"})
    with opener.open(request, timeout=8) as response:
        declared = response.headers.get("Content-Length")
        if declared and int(declared) > cap:
            raise ValueError("reference file exceeds resource budget")
        payload = response.read(cap + 1)
        if len(payload) > cap:
            raise ValueError("reference file exceeds resource budget")
        return payload


def get_wordpress_version(root: Path) -> tuple[str, str]:
    data = guarded_read(root, "wp-includes/version.php", 128 * 1024).decode("utf-8", "replace")
    ver = re.findall(r"""(?m)^\s*\$wp_version\s*=\s*['"]([0-9]+\.[0-9]+(?:\.[0-9]+)?)['"]\s*;""", data)
    loc = re.findall(r"""(?m)^\s*\$wp_local_package\s*=\s*['"]([a-zA-Z_]{2,12})['"]\s*;""", data)
    if len(ver) != 1 or len(loc) > 1:
        raise ValueError("WordPress version metadata unavailable")
    locale = loc[0] if loc else "en_US"
    if not re.fullmatch(r"[a-z]{2}_[A-Z]{2}", locale):
        raise ValueError("WordPress locale unavailable")
    return ver[0], locale


def official_core_checksums(version: str, locale: str, fetch=https_get) -> dict[str, str]:
    qs = urllib.parse.urlencode({"version": version, "locale": locale})
    doc = json.loads(fetch("https://api.wordpress.org/core/checksums/1.0/?" + qs, 2 * 1024 * 1024))
    values = doc.get("checksums")
    if not isinstance(values, dict) or len(values) < 200:
        raise ValueError("official WordPress checksums unavailable")
    valid = {str(k): str(v).lower() for k, v in values.items()
             if isinstance(k, str) and isinstance(v, str) and re.fullmatch(r"[0-9a-fA-F]{32}", v)}
    if len(valid) != len(values):
        raise ValueError("invalid official checksum response")
    return valid


def installed_version(root: Path, slug: str, file: str) -> str:
    s = guarded_read(root, f"wp-content/plugins/{slug}/{file}", 128 * 1024)
    header = s[:8192].decode("utf-8", "replace")
    found = re.findall(r"(?mi)^\s*\*?\s*Version:\s*([0-9]+(?:\.[0-9]+){2,3})\s*$", header)
    if len(found) != 1:
        raise ValueError("plugin version cannot be confirmed")
    return found[0]


def official_plugin_package(slug: str, installed: str, fetch=https_get) -> zipfile.ZipFile:
    component, repo, _ = SOURCE[slug]
    endpoint = f"https://raw.githubusercontent.com/{GIT_ORG}/core-updates/main/projects/{component}.json"
    channel = json.loads(fetch(endpoint, 64 * 1024))
    if not (channel.get("component_id") == component
            and channel.get("package_slug") == slug
            and channel.get("repository") == f"{GIT_ORG}/{repo}"
            and channel.get("target_version") == installed
            and channel.get("release_tag") == "v" + installed):
        raise ValueError("installed version does not match the trusted current distribution")
    asset = channel.get("asset_name")
    expected = channel.get("asset_sha256")
    length = channel.get("asset_bytes")
    if (not isinstance(asset, str) or
            not re.fullmatch(r"[A-Za-z0-9_.-]+\.zip", asset) or
            not isinstance(expected, str) or
            not re.fullmatch(r"[0-9a-f]{64}", expected) or
            not isinstance(length, int) or not (100 < length <= MAX_HTTP)):
        raise ValueError("invalid distribution identity")
    url = f"https://github.com/{GIT_ORG}/{repo}/releases/download/v{installed}/{urllib.parse.quote(asset)}"
    raw = fetch(url, MAX_HTTP)
    if len(raw) != length or hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("downloaded formal release asset identity mismatch")
    zf = zipfile.ZipFile(io.BytesIO(raw))
    if len(zf.infolist()) > 4000:
        zf.close()
        raise ValueError("plugin release archive exceeds file budget")
    return zf


def zip_sha256(zf: zipfile.ZipFile, slug: str, inner: str) -> str:
    # Accept canonical package name or physical WordPress directory only.
    repo = SOURCE[slug][1]
    candidates = [z for z in zf.infolist()
                  if z.filename in {f"{slug}/{inner}", f"{repo}/{inner}"} and not z.is_dir()]
    if len(candidates) != 1 or candidates[0].file_size > MAX_FILE:
        raise ValueError("package file missing/ambiguous/too large")
    h = hashlib.sha256()
    with zf.open(candidates[0]) as fp:
        consumed = 0
        while True:
            data = fp.read(min(1024 * 1024, MAX_FILE + 1 - consumed))
            if not data:
                break
            consumed += len(data)
            if consumed > MAX_FILE:
                raise ValueError("expanded file size exceeded")
            h.update(data)
    return h.hexdigest()


def source_result(event: dict, baseline_sites: dict, cache: dict, fetch=https_get) -> tuple[str, str]:
    root_text, rel = event.get("site_root"), safe_relative(event.get("relative_path"))
    if not isinstance(root_text, str) or root_text not in baseline_sites or not rel:
        return "未核验", "事件路径无法验证"
    root = Path(root_text)
    try:
        home = Path(os.environ.get("P07_IE_DISCOVERY_HOME", "/home")).resolve(strict=True)
        if root.resolve(strict=True) != root or not root.is_relative_to(home):
            return "未核验", "路径不属于安全识别的站点"
        # Always require a regular WordPress marker (never read or print secrets).
        marker = root / "wp-config.php"
        if marker.is_symlink() or not marker.is_file():
            return "未核验", "站点类型无法确认"
        parts = rel.split("/")
        if parts[0] in {"wp-admin", "wp-includes"} or rel in {
            "wp-load.php", "wp-settings.php", "wp-login.php", "wp-cron.php", "wp-blog-header.php"
        }:
            key = ("wp", root_text)
            if key not in cache:
                try:
                    version, locale = get_wordpress_version(root)
                    cache[key] = (version, locale, official_core_checksums(version, locale, fetch))
                except Exception as exc:
                    cache[key] = exc
            ref = cache[key]
            if isinstance(ref, Exception):
                return "未核验", "官方 WordPress 校验值不可用或版本无法确认"
            version, locale, checksums = ref
            if rel not in checksums:
                return "未核验", f"官方 {version}/{locale} 校验表不含此文件"
            actual = hashlib.md5(guarded_read(root, rel)).hexdigest()
            if actual == checksums[rel]:
                return "一致", f"与 WordPress.org {version}/{locale} 核心发布文件一致（非安全证明）"
            return "不一致", f"与 WordPress.org {version}/{locale} 核心发布文件不同"
        if len(parts) >= 4 and parts[:2] == ["wp-content", "plugins"] and parts[2] in SOURCE:
            slug = parts[2]
            key = ("plugin", root_text, slug)
            if key not in cache:
                try:
                    _, _, mainfile = SOURCE[slug]
                    version = installed_version(root, slug, mainfile)
                    cache[key] = (version, official_plugin_package(slug, version, fetch))
                except Exception as exc:
                    cache[key] = exc
            ref = cache[key]
            if isinstance(ref, Exception):
                return "未核验", "安装版本与当前正式包不符，或正式制品暂不可用"
            version, zf = ref
            inner = "/".join(parts[3:])
            original = zip_sha256(zf, slug, inner)
            current = hashlib.sha256(guarded_read(root, rel)).hexdigest()
            if original == current:
                return "一致", f"与 VF 正式发布包 {version} 的文件一致（非安全证明）"
            return "不一致", f"与 VF 正式发布包 {version} 的文件不同"
        if rel.startswith("wp-content/wflogs/"):
            return "未核验", "Wordfence 动态数据，无固定可信发布文件"
        return "未核验", "暂无受信任的自动校验来源"
    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError):
        return "未核验", "文件读取或来源校验失败；没有修改任何文件"


def audit(state_dir: Path, fetch=https_get) -> str:
    status = status_doc(state_dir)
    if status.get("status") not in {"ATTENTION", "NORMAL"} or not status.get("enabled"):
        return "来源核验已停止：网站安全状态不完整，不能使用不可靠历史记录。"
    scan = read_json(state_dir / "scan_state.json")
    events = load_events_consistent(state_dir / "events.json", scan)
    if len(events) > MAX_EVENTS:
        return "来源核验已停止：历史记录超过读取预算。"
    baseline = read_json(state_dir / "baseline.json")
    baseline_sites = baseline.get("sites")
    if not isinstance(baseline_sites, dict):
        return "来源核验已停止：网站参考状态不可读取。"
    grouped = {}
    for event in events:
        key = (str(event.get("site_root")), str(event.get("relative_path")))
        grouped.setdefault(key, event)
    cache = {}
    counter = Counter()
    lines = ["WordPress 网站安全 · 只读来源校验", "说明       仅对照已发布参考文件，不运行网站 PHP，不改文件、数据库或历史状态"]
    try:
        ordered = sorted(grouped.items(), key=lambda e: (e[0][0], e[0][1]))
        shown = 0
        for (root, rel), event in ordered[:MAX_UNIQUE]:
            if shown >= MAX_UNIQUE:
                break
            shown += 1
            outcome, reason = source_result(event, baseline_sites, cache, fetch)
            counter[outcome] += 1
            lines.append(f"[{outcome}] {clean_label(event.get('site'))}: {clean_label(rel)}")
            lines.append("       " + clean_label(reason))
        hidden = len(ordered) - shown
        if hidden:
            lines.append(f"其余       {hidden} 个文件未核验（达到本次读取上限）")
        lines.extend([
            "",
            f"汇总       一致 {counter['一致']} · 不一致 {counter['不一致']} · 未核验 {counter['未核验'] + hidden}（不同文件数）",
            "注意       一致≠网站安全；不一致≠已遭入侵；历史变更仍保留",
            "重要       不自动清除异常、不更新参考状态；尚未核验项目仍需人工调查",
        ])
        return "\n".join(lines)
    finally:
        for value in cache.values():
            if isinstance(value, tuple) and len(value) == 2 and isinstance(value[1], zipfile.ZipFile):
                value[1].close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", default=os.environ.get(
        "P07_IE_STATE_DIR", "/var/lib/vf-system-care/intrusion-evidence"))
    args = parser.parse_args()
    try:
        print(audit(Path(args.state_dir)))
        return 0
    except Exception:
        print("来源核验未能完成：历史状态不可读取，未修改服务器与记录。")
        return 20


if __name__ == "__main__":
    raise SystemExit(main())
