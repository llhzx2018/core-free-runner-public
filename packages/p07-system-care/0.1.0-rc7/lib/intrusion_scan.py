from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path


KEY_FILES = {"wp-config.php", ".htaccess", ".user.ini"}
DEFAULT_DISCOVERY_HOME = "/home"
DEFAULT_MAX_TRACKED_FILES = 50_000
DEFAULT_MAX_HASH_BYTES = 1024 * 1024 * 1024


class ScanBudgetExceededError(RuntimeError):
    def __init__(self, resource: str, limit: int, current: int, requested: int, path: Path):
        super().__init__(f"scan budget exceeded: {resource}")
        self.resource = resource
        self.limit = int(limit)
        self.current = int(current)
        self.requested = int(requested)
        self.path = str(path)


@dataclass
class ScanBudget:
    max_files: int = DEFAULT_MAX_TRACKED_FILES
    max_bytes: int = DEFAULT_MAX_HASH_BYTES
    files_hashed: int = 0
    bytes_hashed: int = 0

    def reserve(self, path: Path, size: int) -> None:
        size = int(size)
        if self.files_hashed + 1 > self.max_files:
            raise ScanBudgetExceededError("tracked_files", self.max_files, self.files_hashed, 1, path)
        if self.bytes_hashed + size > self.max_bytes:
            raise ScanBudgetExceededError("hash_bytes", self.max_bytes, self.bytes_hashed, size, path)
        self.files_hashed += 1
        self.bytes_hashed += size

    def snapshot(self) -> dict:
        return {
            "max_tracked_files": self.max_files,
            "max_hash_bytes": self.max_bytes,
            "files_hashed": self.files_hashed,
            "bytes_hashed": self.bytes_hashed,
        }


def require_regular_marker(root: Path) -> None:
    marker = root / "wp-config.php"
    st = marker.lstat()
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        raise ValueError(f"WordPress marker must be a regular non-symlink file: {marker}")


def stable_meta(path: Path, budget: ScanBudget | None = None) -> dict:
    """Hash one regular file through a no-follow fd and reject in-scan mutation."""
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError(f"tracked path is not a regular file: {path}")
        if budget is not None:
            budget.reserve(path, int(before.st_size))
        h = hashlib.sha256()
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
        after = os.fstat(fd)
        identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        if identity_before != identity_after:
            raise RuntimeError(f"tracked file changed during scan: {path}")
        return {"sha256": h.hexdigest(), "size": int(after.st_size), "mtime": int(after.st_mtime)}
    finally:
        os.close(fd)


def tracked(rel: str) -> bool:
    name = rel.rsplit("/", 1)[-1]
    return rel.lower().endswith(".php") or name in KEY_FILES


def uploads_php(rel: str) -> bool:
    rel = rel.lower()
    return rel.endswith(".php") and (rel.startswith("wp-content/uploads/") or "/wp-content/uploads/" in rel)


def collect(root: Path, budget: ScanBudget | None = None) -> dict[str, dict]:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"WordPress root missing: {root}")
    require_regular_marker(root)
    rows: dict[str, dict] = {}
    for current, dirs, files in os.walk(root, followlinks=False):
        base = Path(current)
        dirs[:] = [name for name in dirs if not (base / name).is_symlink()]
        for name in files:
            path = base / name
            if path.is_symlink():
                continue
            try:
                resolved = path.resolve(strict=True)
                rel = resolved.relative_to(root).as_posix()
            except (FileNotFoundError, ValueError):
                continue
            if not tracked(rel):
                continue
            rows[rel] = stable_meta(resolved, budget=budget)
    return rows


def discovery_home() -> Path:
    return Path(os.environ.get("P07_IE_DISCOVERY_HOME", DEFAULT_DISCOVERY_HOME)).expanduser()


def discover(explicit: list[str]) -> list[Path]:
    raw = [Path(value) for value in explicit]
    if not raw:
        home = discovery_home()
        if not home.is_dir():
            return []
        home_resolved = home.resolve(strict=True)
        seen = set()
        for pattern in ("*/htdocs/*/wp-config.php", "*/htdocs/*/*/wp-config.php"):
            for marker in home.glob(pattern):
                try:
                    marker_st = marker.lstat()
                except FileNotFoundError:
                    continue
                if stat.S_ISLNK(marker_st.st_mode) or not stat.S_ISREG(marker_st.st_mode):
                    raise ValueError(f"discovered WordPress marker is not a regular file: {marker}")
                try:
                    root = marker.parent.resolve(strict=True)
                    root.relative_to(home_resolved)
                except (FileNotFoundError, ValueError) as exc:
                    raise ValueError(f"discovered WordPress root escapes discovery home: {marker.parent}") from exc
                require_regular_marker(root)
                seen.add(str(root))
        raw = [Path(value) for value in sorted(seen)]
    unique: dict[str, Path] = {}
    for item in raw:
        root = item.resolve(strict=True)
        require_regular_marker(root)
        unique[str(root)] = root
    return [unique[key] for key in sorted(unique)]


def event_id(row: dict) -> str:
    text = "\0".join(str(row.get(k, "")) for k in ("site_root", "type", "relative_path", "old_sha256", "new_sha256"))
    return hashlib.sha256(text.encode()).hexdigest()[:24]


def unbaselined_site_event(root: Path, detected_at: str) -> dict:
    """Surface newly discovered WordPress roots without silently trusting/baselining their contents."""
    row = {
        "site_root": str(root),
        "site": root.name,
        "type": "UNBASELINED_WORDPRESS_SITE",
        "severity": "ATTENTION",
        "evidence_scope": "SITE_TOPOLOGY",
        "relative_path": ".",
        "old_sha256": None,
        "new_sha256": None,
        "size": None,
        "mtime": None,
        "mtime_trust": "NOT_APPLICABLE",
        "first_detected_at": detected_at,
    }
    row["event_id"] = event_id(row)
    return row


def diff(root: Path, old: dict[str, dict], new: dict[str, dict], detected_at: str) -> list[dict]:
    rows = []
    for rel in sorted(set(old) | set(new)):
        before, after = old.get(rel), new.get(rel)
        if before is None and after is not None:
            kind = "UPLOADS_PHP" if uploads_php(rel) else "NEW_PHP"
        elif before is not None and after is None:
            kind = "DELETED_TRACKED_FILE"
        elif before and after and before.get("sha256") != after.get("sha256"):
            kind = "KEY_FILE_CHANGED" if rel.rsplit("/", 1)[-1] in KEY_FILES else "MODIFIED_PHP"
        else:
            continue
        row = {
            "site_root": str(root), "site": root.name, "type": kind,
            "severity": "HIGH" if kind in {"UPLOADS_PHP", "KEY_FILE_CHANGED"} else "ATTENTION",
            "relative_path": rel, "old_sha256": (before or {}).get("sha256"),
            "new_sha256": (after or {}).get("sha256"), "size": (after or {}).get("size"),
            "mtime": (after or {}).get("mtime"),
            "mtime_trust": "UNTRUSTED_HINT_ONLY",
            "first_detected_at": detected_at,
        }
        row["event_id"] = event_id(row)
        rows.append(row)
    return rows
