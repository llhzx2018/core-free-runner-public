#!/usr/bin/env python3
"""P07-M05 新服务器初始化: public-safe standalone ZIP installer.

No private product source. Installs only an immutable SHA256-pinned M05
artifact in /opt/vfops-modules/m05. Never invokes M03/M04 or CloudPanel.
No file from this installer is packaged for public distribution by default.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import uuid
import zipfile

MODULE = "P07-M05"
BASE = Path("/opt/vfops-modules")
PREFIX = "p07-m05/"
MAX_ZIP = 48 * 1024 * 1024
MAX_FILES = 400
MAX_ITEM = 8 * 1024 * 1024
BINS = {"bin/vfops-init-entry", "bin/vfops-init-ui", "bin/vfops-init-core"}
META = {"MODULE_ID", "MODULE_BUILD_ID", "VERSION", "BUILD_ID"}
MANIFEST = "MODULE_MANIFEST.json"


class Unsafe(Exception):
    pass


def deny(message="独立安装校验失败"):
    raise Unsafe(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_directory(path: Path) -> None:
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        deny("安装目录不安全")
    path.mkdir(mode=0o755, exist_ok=True)
    if path.is_symlink() or not path.is_dir():
        deny("安装目录不可用")


def read_verified_archive(archive: Path, checksum: str) -> tuple[str, dict[str, bytes]]:
    if not re.fullmatch(r"[a-f0-9]{64}", checksum):
        deny("SHA-256 格式错误")
    if (archive.is_symlink() or not archive.is_file()
            or archive.stat().st_size > MAX_ZIP or digest(archive.read_bytes()) != checksum):
        deny("ZIP 不存在、不安全或 SHA-256 不匹配")
    result: dict[str, bytes] = {}
    with zipfile.ZipFile(archive) as packed:
        members = packed.infolist()
        if not 1 <= len(members) <= MAX_FILES:
            deny("ZIP 文件数量异常")
        total = 0
        for info in members:
            if info.is_dir() or not info.filename.startswith(PREFIX):
                deny("ZIP 出现外部模块路径")
            name = info.filename[len(PREFIX):]
            rel = PurePosixPath(name)
            if (not name or not name.isascii() or rel.is_absolute()
                    or ".." in rel.parts or "." in rel.parts or "\\" in name
                    or "//" in name or name.startswith(".")
                    or not (name.startswith(("bin/", "lib/")) or name in META | {MANIFEST})):
                deny("ZIP 内包含不允许的路径")
            mode = info.external_attr >> 16
            if stat.S_IFMT(mode) != stat.S_IFREG:
                deny("ZIP 内出现非普通文件")
            if name in result or info.file_size <= 0 or info.file_size > MAX_ITEM:
                deny("ZIP 内有重复或过大文件")
            total += info.file_size
            if total > MAX_ZIP:
                deny("解压体积超限")
            result[name] = packed.read(info)
    try:
        raw = result.pop(MANIFEST)
        manifest = json.loads(raw)
        build = manifest.get("module_build_id")
        files = manifest.get("files")
        if (manifest.get("schema") != "vf.p07.module-bundle.v1"
                or manifest.get("module_id") != MODULE
                or manifest.get("module_name") != "新服务器初始化"
                or manifest.get("entrypoint") != "bin/vfops-init-entry"
                or manifest.get("installation_isolation") != "P07-M05_ONLY"
                or not isinstance(build, str)
                or not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", build)
                or not isinstance(files, dict)
                or set(files) != set(result)
                or not BINS.issubset(result)
                or result.get("MODULE_ID") != b"P07-M05\n"
                or result.get("MODULE_BUILD_ID") != (build + "\n").encode()):
            deny("模块身份不匹配")
        for name, expected in files.items():
            if not isinstance(expected, str) or digest(result[name]) != expected:
                deny("模块文件清单异常")
        if any(name.startswith("bin/") and name not in BINS for name in result):
            deny("模块出现意外执行程序")
        result[MANIFEST] = raw
    except (KeyError, TypeError, UnicodeError, ValueError):
        deny("模块 JSON 清单有误")
    return build, result


def verify_existing(root: Path, build: str, expected: dict[str, bytes]) -> None:
    if root.is_symlink() or not root.is_dir():
        deny("已有版本目录异常")
    paths = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    if paths != set(expected):
        deny("已有模块文件数量变化")
    for name, data in expected.items():
        file = root / name
        if file.is_symlink() or not file.is_file() or digest(file.read_bytes()) != digest(data):
            deny("已有模块文件发生变化")
    if (root / "MODULE_BUILD_ID").read_text(encoding="utf-8").strip() != build:
        deny("已有模块构建身份不同")


def install(archive: Path, checksum: str) -> str:
    if os.geteuid() != 0:
        deny("独立模块安装需要 root")
    build, files = read_verified_archive(archive, checksum)
    safe_directory(BASE)
    home = BASE / "m05"
    safe_directory(home)
    releases = home / "releases"
    safe_directory(releases)
    current = home / "current"
    lock_path = home / ".install.lock"
    if lock_path.is_symlink() or (lock_path.exists() and not lock_path.is_file()):
        deny("模块锁文件异常")
    fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if current.is_symlink():
            old = os.readlink(current)
            if (not re.fullmatch(r"releases/[A-Za-z0-9._-]{1,64}", old)
                    or (home / old).is_symlink() or not (home / old).is_dir()):
                deny("已有模块当前版本不安全")
        elif current.exists():
            deny("已有 current 不是模块软链接")
        target = releases / build
        if target.exists() or target.is_symlink():
            if not current.is_symlink() or os.readlink(current) != "releases/" + build:
                deny("版本已存在，不能覆盖；须单独执行回滚")
            verify_existing(target, build, files)
            return build
        stage = home / (".stage-" + uuid.uuid4().hex)
        switch = home / (".current-" + uuid.uuid4().hex)
        try:
            stage.mkdir(mode=0o700)
            for name, data in sorted(files.items()):
                item = stage / name
                item.parent.mkdir(parents=True, exist_ok=True)
                with item.open("xb") as output:
                    output.write(data)
                item.chmod(0o755 if name in BINS else 0o644)
            for binary in BINS:
                check = subprocess.run(["bash", "-n", str(stage / binary)],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                       timeout=15, check=False)
                if check.returncode:
                    deny("M05 Shell 执行文件语法错误")
            version = subprocess.run(["bash", str(stage / "bin/vfops-init-entry"), "--version"],
                                     capture_output=True, text=True, timeout=15, check=False)
            if (version.returncode != 0 or version.stdout.strip()
                    != "P07-M05 新服务器初始化 " + build):
                deny("模块运行版本回读失败")
            stage.chmod(0o755)
            os.replace(stage, target)
            os.symlink("releases/" + build, switch)
            os.replace(switch, current)
        finally:
            if switch.is_symlink():
                switch.unlink()
            if stage.exists():
                shutil.rmtree(stage)
    return build


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P07-M05 新服务器初始化 · 独立模块安装")
    parser.add_argument("command", choices=["install"])
    parser.add_argument("archive", type=Path)
    parser.add_argument("sha256")
    args = parser.parse_args(argv)
    try:
        build = install(args.archive, args.sha256)
        print(f"P07-M05 新服务器初始化：{build} 已准备好；其他模块未安装或更新。")
        return 0
    except (Unsafe, OSError, ValueError, KeyError, zipfile.BadZipFile,
            subprocess.SubprocessError) as error:
        print(f"P07-M05 新服务器初始化：{error}；独立安装已停止。", file=sys.stderr)
        return 13


if __name__ == "__main__":
    raise SystemExit(main())
