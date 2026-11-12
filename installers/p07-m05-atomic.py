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


def verify_saved_release(root: Path, build: str) -> None:
    """Verify an inactive installed M05 version without consulting M03/M04.

    Local manifest is the install-time record. No current-version mutation,
    file repairs, code execution or scanning other module directories.
    """
    if (not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", build)
            or root.is_symlink() or not root.is_dir()):
        deny("回滚目标目录或版本身份无效")
    marker = root / MANIFEST
    if marker.is_symlink() or not marker.is_file():
        deny("回滚目标缺失完整性清单")
    try:
        record = json.loads(marker.read_text(encoding="utf-8"))
        if (record.get("schema") != "vf.p07.module-bundle.v1"
                or record.get("module_id") != MODULE
                or record.get("module_name") != "新服务器初始化"
                or record.get("installation_isolation") != "P07-M05_ONLY"
                or record.get("entrypoint") != "bin/vfops-init-entry"
                or record.get("module_build_id") != build):
            deny("回滚目标不是已登记的本模块")
        files = record.get("files")
        if not isinstance(files, dict) or not 20 <= len(files) <= MAX_FILES:
            deny("回滚目标文件清单异常")
        if not BINS.issubset(files) or not META.issubset(files):
            deny("回滚目标运行文件缺失")
        if (root / "MODULE_ID").read_bytes() != b"P07-M05\\n" or
                (root / "MODULE_BUILD_ID").read_bytes() != (build + "\\n").encode()):
            deny("回滚目标内部身份不匹配")
        actual = set()
        for item in root.rglob("*"):
            name = item.relative_to(root).as_posix()
            if item.is_symlink():
                deny("回滚目标包含软链接")
            if item.is_dir():
                continue
            if not item.is_file():
                deny("回滚目标包含不支持的文件")
            actual.add(name)
        if actual != set(files) | {MANIFEST}:
            deny("回滚目标文件数量不一致")
        for name, expected in files.items():
            rel = PurePosixPath(name)
            if (not isinstance(name, str) or not name.isascii()
                    or rel.is_absolute() or ".." in rel.parts
                    or "\\\\" in name or "//" in name or name.startswith(".")
                    or not (name.startswith(("bin/", "lib/")) or name in META)):
                deny("回滚目标文件路径异常")
            if name.startswith("bin/") and name not in BINS:
                deny("回滚目标包含非授权可执行文件")
            if not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected):
                deny("回滚目标文件摘要异常")
            item = root / name
            if not item.is_file() or item.is_symlink() or digest(item.read_bytes()) != expected:
                deny("回滚目标文件不完整")
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        deny("回滚目标无法验证")


def atomic_switch(home: Path, current: Path, build: str) -> None:
    next_link = home / (".current-" + uuid.uuid4().hex)
    try:
        if next_link.exists() or next_link.is_symlink():
            deny("模块临时指针冲突")
        os.symlink("releases/" + build, next_link)
        os.replace(next_link, current)
    finally:
        if next_link.is_symlink():
            next_link.unlink()


def rollback(build: str, confirmation: str) -> str:
    """Explicit M05-only rollback to a verified immutable existing release."""
    if os.geteuid() != 0:
        deny("独立回滚需要 root")
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", build):
        deny("回滚版本号不合法")
    if confirmation != MODULE + ":" + build:
        deny("回滚确认不匹配")
    home = BASE / "m05"
    releases = home / "releases"
    current = home / "current"
    # Never create an uninstalled module while processing rollback.
    for folder in (BASE, home, releases):
        if folder.is_symlink() or not folder.is_dir():
            deny("没有可安全恢复的 M05 独立安装")
    lock_path = home / ".install.lock"
    if lock_path.is_symlink() or (lock_path.exists() and not lock_path.is_file()):
        deny("模块回滚锁异常")
    fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not current.is_symlink():
            deny("回滚前不存在原子版本指针")
        old = os.readlink(current)
        if (not re.fullmatch(r"releases/[A-Za-z0-9._-]{1,64}", old)
                or (home / old).is_symlink() or not (home / old).is_dir()):
            deny("原版本指针或目录异常")
        target = releases / build
        verify_saved_release(target, build)
        if old != "releases/" + build:
            atomic_switch(home, current, build)
    return build


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
            # Only a full SHA256-matched incoming ZIP may resume a previously
            # staged-but-not-switched release; never overwrite target files.
            verify_existing(target, build, files)
            if not current.is_symlink() or os.readlink(current) != "releases/" + build:
                atomic_switch(home, current, build)
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
    parser = argparse.ArgumentParser(description="P07-M05 新服务器初始化 · 独立安装/回滚")
    operation = parser.add_subparsers(dest="command", required=True)
    install_cmd = operation.add_parser("install", help="安装 SHA-256 验证的独立 ZIP")
    install_cmd.add_argument("archive", type=Path)
    install_cmd.add_argument("sha256")
    rollback_cmd = operation.add_parser("rollback", help="只回滚本模块的既存版本")
    rollback_cmd.add_argument("build")
    rollback_cmd.add_argument("--confirm", required=True, help="P07-M05:<构建号>")
    args = parser.parse_args(argv)
    try:
        if args.command == "install":
            build = install(args.archive, args.sha256)
            print(f"P07-M05 新服务器初始化：{build} 已准备好；其他模块未安装或更新。")
        else:
            build = rollback(args.build, args.confirm)
            print(f"P07-M05 新服务器初始化：仅本模块已恢复为 {build}；其他模块未改动。")
        return 0
    except (Unsafe, OSError, ValueError, KeyError, zipfile.BadZipFile,
            subprocess.SubprocessError) as error:
        print(f"P07-M05 新服务器初始化：{error}；独立安装已停止。", file=sys.stderr)
        return 13


if __name__ == "__main__":
    raise SystemExit(main())
