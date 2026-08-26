#!/usr/bin/env python3
from __future__ import annotations

import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath


def fail(message: str) -> None:
    print(f"ZIP_SAFETY_FAIL: {message}", file=sys.stderr)
    raise SystemExit(3)


def extract(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as source:
        entries = source.infolist()
        if not entries:
            fail("empty archive")
        if len(entries) > 10000:
            fail("too many entries")
        total = 0
        for entry in entries:
            normalized = entry.filename.replace("\\", "/")
            path = PurePosixPath(normalized)
            if path.is_absolute() or ".." in path.parts:
                fail(f"unsafe path: {normalized}")
            mode = (entry.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode):
                fail(f"symlink entry forbidden: {normalized}")
            total += entry.file_size
            if entry.file_size > 256 * 1024 * 1024 or total > 1024 * 1024 * 1024:
                fail("archive size limit exceeded")
        source.extractall(destination)
    print(f"ZIP_SAFETY_PASS entries={len(entries)} bytes={total}")


def main() -> None:
    if len(sys.argv) != 3:
        fail("usage: safe_extract.py <archive.zip> <destination>")
    extract(Path(sys.argv[1]), Path(sys.argv[2]))


if __name__ == "__main__":
    main()

