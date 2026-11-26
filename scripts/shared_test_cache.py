"""Cache only pinned public VF engine bytes; never cache product source or data."""
from __future__ import annotations
import base64
import fcntl
import hashlib
import json
import os
import re
import stat
import tempfile
import urllib.request
from pathlib import Path

REPO = "llhzx2018/core-free-runner-public"
LIMIT = 131072
FILES = {"shared_test_execution.py", "shared_test_result.py"}
HEX = re.compile(r"[0-9a-f]{40}\Z")

def blob_id(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + bytes([0]) + data).hexdigest()

def safe_dir(path: Path) -> None:
    st = path.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) != 0o700:
        raise ValueError("CACHE_DIRECTORY_UNSAFE")

def read_verified(path: Path, expected: str) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        st = os.fstat(stream.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or st.st_nlink != 1 or stat.S_IMODE(st.st_mode) != 0o600 or st.st_size > LIMIT:
            raise ValueError("CACHE_FILE_UNSAFE")
        data = stream.read(LIMIT + 1)
    if len(data) > LIMIT or blob_id(data) != expected:
        raise ValueError("CACHE_IDENTITY_MISMATCH")
    return data

def fetch_public(commit: str, name: str, expected: str) -> bytes:
    # Both endpoints are anonymous reads of the same public immutable object.
    # No private product token or data is transmitted.
    urls = (
        ("raw", f"https://raw.githubusercontent.com/{REPO}/{commit}/scripts/{name}"),
        ("blob", f"https://api.github.com/repos/{REPO}/git/blobs/{expected}"),
    )
    for kind, url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "VF-Shared-Engine/1", "Accept": "application/vnd.github+json" if kind == "blob" else "application/octet-stream"})
            with urllib.request.urlopen(req, timeout=20) as response:
                data = response.read(2 * LIMIT + 1)
            if len(data) > 2 * LIMIT:
                continue
            if kind == "blob":
                item = json.loads(data)
                if item.get("sha") != expected or item.get("encoding") != "base64":
                    continue
                data = base64.b64decode("".join(item["content"].split()), validate=True)
            if len(data) <= LIMIT and blob_id(data) == expected:
                return data
        except (OSError, ValueError, KeyError, TypeError):
            continue
    raise RuntimeError("PUBLIC_ENGINE_FETCH_OR_IDENTITY_FAILED")

def materialize(cache_parent: Path, destination: Path, *, commit: str,
                blobs: dict[str, str], fetch=fetch_public) -> dict:
    """Existing trusted owner-only queue parent; destination is run-owned.
    Validate on every hit, fail closed on corruption. No global imports from
    mutable cache: only verified bytes copied into the disposable workspace.
    """
    if not HEX.fullmatch(commit) or set(blobs) != FILES or any(not HEX.fullmatch(x) for x in blobs.values()):
        raise ValueError("CACHE_PIN_INVALID")
    safe_dir(cache_parent)
    safe_dir(destination)
    root = cache_parent / "public-engine-cache"
    root.mkdir(mode=0o700, exist_ok=True)
    safe_dir(root)
    lock = os.open(root / ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        st = os.fstat(lock)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or st.st_nlink != 1 or stat.S_IMODE(st.st_mode) != 0o600:
            raise ValueError("CACHE_LOCK_UNSAFE")
        fcntl.flock(lock, fcntl.LOCK_EX)
        version = root / commit
        version.mkdir(mode=0o700, exist_ok=True)
        safe_dir(version)
        hits = misses = 0
        for name, expected in sorted(blobs.items()):
            target = version / name
            try:
                data = read_verified(target, expected)
                hits += 1
            except FileNotFoundError:
                data = fetch(commit, name, expected)
                if not isinstance(data, bytes) or len(data) > LIMIT or blob_id(data) != expected:
                    raise ValueError("DOWNLOAD_IDENTITY_MISMATCH")
                with tempfile.NamedTemporaryFile(dir=version, prefix=".pending-", delete=False) as tmp:
                    pending = Path(tmp.name)
                    try:
                        tmp.write(data)
                        tmp.flush()
                        os.fsync(tmp.fileno())
                        os.link(pending, target, follow_symlinks=False)
                    finally:
                        pending.unlink()
                misses += 1
            fd = os.open(destination / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "wb") as out:
                out.write(data)
        return {"commit": commit, "hits": hits, "misses": misses}
    finally:
        os.close(lock)
