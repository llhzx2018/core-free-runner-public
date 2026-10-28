from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import stat
from dataclasses import dataclass
from pathlib import Path


KEY_FILES = {"wp-config.php", ".htaccess", ".user.ini"}
DEFAULT_DISCOVERY_HOME = "/home"
DEFAULT_CLOUDPANEL_DB = "/home/clp/htdocs/app/data/db.sq3"
DEFAULT_NGINX_SITES_DIR = "/etc/nginx/sites-enabled"
DEFAULT_MAX_TRACKED_FILES = 50_000
DEFAULT_MAX_HASH_BYTES = 1024 * 1024 * 1024
DEFAULT_MAX_DISCOVERY_DEPTH = 5
DEFAULT_MAX_DISCOVERY_DIRS = 20_000


class ScanBudgetExceededError(RuntimeError):
    def __init__(self, resource: str, limit: int, current: int, requested: int, path: Path):
        super().__init__(f"scan budget exceeded: {resource}")
        self.resource = resource
        self.limit = int(limit)
        self.current = int(current)
        self.requested = int(requested)
        self.path = str(path)


class NoWordPressSitesError(ValueError):
    def __init__(self, cloudpanel_site_count: int = 0, source: str = "unknown"):
        super().__init__("no WordPress sites discovered")
        self.cloudpanel_site_count = int(cloudpanel_site_count)
        self.discovery_source = str(source)


class UnsupportedWordPressLayoutError(ValueError):
    pass


class DiscoveryBudgetExceededError(RuntimeError):
    pass


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
        raise UnsupportedWordPressLayoutError(
            f"WordPress wp-config.php must be a regular non-symlink file: {marker}"
        )


def stable_meta(path: Path, budget: ScanBudget | None = None) -> dict:
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


def cloudpanel_db_path() -> Path:
    return Path(os.environ.get("P07_IE_CLOUDPANEL_DB", DEFAULT_CLOUDPANEL_DB)).expanduser()


def nginx_sites_dir() -> Path:
    return Path(os.environ.get("P07_IE_NGINX_SITES_DIR", DEFAULT_NGINX_SITES_DIR)).expanduser()


def _nginx_inventory() -> dict[str, dict]:
    """Inventory-compatible read-only Nginx map used by Slot 3 and System Care."""
    directory = nginx_sites_dir()
    by_domain: dict[str, dict] = {}
    if not directory.is_dir():
        return by_domain
    for conf in sorted(directory.glob("*.conf")):
        try:
            text = conf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        names: list[str] = []
        for match in re.finditer(r"(?m)^\s*server_name\s+([^;]+);", text):
            names.extend(name for name in re.split(r"\s+", match.group(1).strip()) if name and name != "_")
        root_match = re.search(r"(?m)^\s*root\s+([^;]+);", text)
        document_root: Path | None = None
        if root_match:
            value = root_match.group(1).strip().strip('"\'')
            if value.startswith("/") and "$" not in value:
                document_root = Path(value)
        primary = next((name for name in names if not name.startswith("*.")), conf.stem)
        record = {"domain": primary, "domains": sorted(set(names)) or [primary], "document_root": document_root}
        for name in record["domains"]:
            by_domain.setdefault(name, record)
        by_domain.setdefault(primary, record)
    return by_domain


def _cloudpanel_inventory() -> tuple[str, list[dict]]:
    """Return known CloudPanel sites, preferring the same DB schema used by Slot 3 Inventory."""
    vhosts = _nginx_inventory()
    db = cloudpanel_db_path()
    if db.is_file():
        try:
            conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        except sqlite3.Error:
            conn = None
        if conn is not None:
            try:
                columns = {row[1] for row in conn.execute('PRAGMA table_info("site")')}
                if {"domain_name", "user"}.issubset(columns):
                    has_type = "type" in columns
                    sql = 'SELECT domain_name, user, type FROM "site" ORDER BY domain_name' if has_type else 'SELECT domain_name, user, NULL FROM "site" ORDER BY domain_name'
                    rows = []
                    for domain, user, site_type in conn.execute(sql):
                        if domain in (None, "") or user in (None, ""):
                            continue
                        domain = str(domain); user = str(user)
                        vhost = vhosts.get(domain)
                        rows.append({
                            "domain": domain,
                            "user": user,
                            "type": str(site_type or "UNKNOWN"),
                            "document_root": vhost.get("document_root") if vhost else None,
                        })
                    return "cloudpanel_db", rows
            except sqlite3.Error:
                pass
            finally:
                conn.close()

    rows: list[dict] = []
    seen: set[str] = set()
    for record in vhosts.values():
        domain = str(record["domain"])
        if domain in seen:
            continue
        seen.add(domain)
        document_root = record.get("document_root")
        user = None
        if isinstance(document_root, Path):
            match = re.match(r"^/home/([^/]+)/", str(document_root))
            if match:
                user = match.group(1)
        rows.append({"domain": domain, "user": user, "type": "UNKNOWN", "document_root": document_root})
    return "nginx_vhost", sorted(rows, key=lambda item: item["domain"])


def _within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _regular_marker_state(root: Path) -> str:
    marker = root / "wp-config.php"
    try:
        st = marker.lstat()
    except FileNotFoundError:
        return "missing"
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        return "unsafe"
    return "regular"


def _has_wordpress_core(root: Path, related_docroots: list[Path]) -> bool:
    if (root / "wp-settings.php").is_file() or (root / "wp-includes/version.php").is_file() or (root / "wp-content").is_dir():
        return True
    for docroot in related_docroots:
        try:
            resolved = docroot.resolve(strict=True)
        except FileNotFoundError:
            continue
        if not _within(resolved, root):
            continue
        if (resolved / "wp-settings.php").is_file() or (resolved / "wp-includes/version.php").is_file() or (resolved / "wp-content").is_dir():
            return True
    return False


def _validate_wordpress_root(root: Path, home_resolved: Path, related_docroots: list[Path]) -> Path | None:
    state = _regular_marker_state(root)
    if state == "missing":
        return None
    if state == "unsafe":
        raise UnsupportedWordPressLayoutError(f"unsafe WordPress wp-config.php: {root / 'wp-config.php'}")
    try:
        resolved = root.resolve(strict=True)
        resolved.relative_to(home_resolved)
    except (FileNotFoundError, ValueError) as exc:
        raise UnsupportedWordPressLayoutError(f"WordPress root escapes protected CloudPanel home: {root}") from exc
    require_regular_marker(resolved)
    if not _has_wordpress_core(resolved, related_docroots):
        return None
    return resolved


def _bounded_site_marker_search(site_base: Path, max_depth: int = DEFAULT_MAX_DISCOVERY_DEPTH) -> list[Path]:
    """Search only inside one CloudPanel-owned site tree; never arbitrary /home."""
    try:
        base = site_base.resolve(strict=True)
    except FileNotFoundError:
        return []
    found: list[Path] = []
    base_depth = len(base.parts)
    visited = 0
    for current, dirs, files in os.walk(base, followlinks=False):
        current_path = Path(current)
        depth = len(current_path.parts) - base_depth
        visited += 1
        if visited > DEFAULT_MAX_DISCOVERY_DIRS:
            raise DiscoveryBudgetExceededError(f"site discovery directory budget exceeded: {site_base}")
        if depth >= max_depth:
            dirs[:] = []
        else:
            dirs[:] = [name for name in dirs if not (current_path / name).is_symlink()]
        if "wp-config.php" in files or (current_path / "wp-config.php").is_symlink():
            found.append(current_path)
    return found


def discovery_report(explicit: list[str] | None = None) -> dict:
    explicit = explicit or []
    home = discovery_home()
    if not home.is_dir():
        return {"source": "no_home", "cloudpanel_site_count": 0, "wordpress_roots": []}
    home_resolved = home.resolve(strict=True)

    if explicit:
        roots: dict[str, Path] = {}
        for value in explicit:
            root = Path(value).resolve(strict=True)
            require_regular_marker(root)
            roots[str(root)] = root
        return {"source": "explicit", "cloudpanel_site_count": len(roots), "wordpress_roots": [roots[key] for key in sorted(roots)]}

    source, sites = _cloudpanel_inventory()
    roots: dict[str, Path] = {}
    for site in sites:
        domain = str(site.get("domain") or "")
        user = site.get("user")
        document_root = site.get("document_root")
        candidates: list[Path] = []
        related_docroots: list[Path] = []
        site_base: Path | None = None

        if user:
            user_root = home_resolved / str(user)
            try:
                user_resolved = user_root.resolve(strict=True)
                user_resolved.relative_to(home_resolved)
            except (FileNotFoundError, ValueError):
                user_resolved = None
            if user_resolved is not None and user_resolved.parent == home_resolved:
                htdocs = user_resolved / "htdocs"
                if htdocs.is_dir():
                    site_base = htdocs / domain
                    candidates.append(site_base)

        if isinstance(document_root, Path):
            related_docroots.append(document_root)
            candidates.append(document_root)
            # WordPress permits wp-config.php one level above the web root. Keep this
            # inside the same CloudPanel site boundary; never widen to shared htdocs.
            if site_base is not None:
                try:
                    doc_resolved = document_root.resolve(strict=True)
                    base_resolved = site_base.resolve(strict=True)
                    if _within(doc_resolved, base_resolved) and doc_resolved != base_resolved:
                        parent = doc_resolved.parent
                        if _within(parent, base_resolved):
                            candidates.append(parent)
                except FileNotFoundError:
                    pass

        if site_base is not None:
            candidates.extend(_bounded_site_marker_search(site_base))

        seen_candidates: set[str] = set()
        for candidate in candidates:
            key = str(candidate)
            if key in seen_candidates:
                continue
            seen_candidates.add(key)
            resolved = _validate_wordpress_root(candidate, home_resolved, related_docroots)
            if resolved is not None:
                roots[str(resolved)] = resolved

    if not sites:
        # Compatibility fallback only when CloudPanel inventory itself yields no sites.
        for pattern in ("*/htdocs/*/wp-config.php", "*/htdocs/*/*/wp-config.php"):
            for marker in home.glob(pattern):
                resolved = _validate_wordpress_root(marker.parent, home_resolved, [])
                if resolved is not None:
                    roots[str(resolved)] = resolved
        if roots:
            source = "bounded_fallback"

    return {
        "source": source,
        "cloudpanel_site_count": len(sites),
        "wordpress_roots": [roots[key] for key in sorted(roots)],
    }


def discover(explicit: list[str]) -> list[Path]:
    report = discovery_report(explicit)
    roots = list(report["wordpress_roots"])
    if not roots:
        raise NoWordPressSitesError(report["cloudpanel_site_count"], report["source"])
    return roots


def event_id(row: dict) -> str:
    text = "\0".join(str(row.get(k, "")) for k in ("site_root", "type", "relative_path", "old_sha256", "new_sha256"))
    return hashlib.sha256(text.encode()).hexdigest()[:24]


def unbaselined_site_event(root: Path, detected_at: str) -> dict:
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
