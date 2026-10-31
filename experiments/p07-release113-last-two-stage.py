#!/usr/bin/env python3
"""Owner-authorized P07 release113 staging for only two untouched sites.

Safe continuation after the nine-site partial PREPARE_FAILED child. This does
not resume the child, modify source business data, touch the blocked unzip
site, rewrite any existing DB, freeze source, or cut over DNS.
"""
from __future__ import annotations
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

ORIGINAL = "pull-20261028T103425Z-98050c76"
NINE_CHILD = "pull-20261031T094144Z-d045fa5a"
DOMAINS = ("updates.kewaro.com", "www3.m3u8.one")
NINE_DOMAINS = (
    "infra.kewaro.com", "lib.kewaro.com", "press.kewaro.com",
    "seo.kewaro.com", "start.kewaro.com", "textbox.kewaro.com",
    "unzip.kewaro.com", *DOMAINS,
)
ROOT = Path("/opt/vf-server-ops")
STATES = Path("/var/lib/vf-server-ops/server-migrations")
ORIGINAL_FILE = STATES / ORIGINAL / "state.json"
NINE_FILE = STATES / NINE_CHILD / "state.json"
RECOVERY_DIR = Path("/var/lib/vf-server-ops/operator-recovery")
LOCK = Path("/run/lock/p07-legacy-nine-staging.lock")
RUNTIME_BLOB = "a48aa44b96b0a554ae9170d289c46d5cfb56d937"
ENGINE_BLOB = "71fb59ad7d005b88e39cbeed4b3302c7f313bd06"
SCHEMA = "vf-server-ops.server-migration.target-pull.v1"


class Stop(ValueError):
    pass


def require(ok, reason):
    if not ok:
        raise Stop(reason)


def gitblob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def private_bytes(path: Path) -> bytes:
    meta = path.lstat()
    require(stat.S_ISREG(meta.st_mode), "EVIDENCE_IS_NOT_REGULAR")
    require(meta.st_uid == 0 and not meta.st_mode & 0o022, "EVIDENCE_PERMISSIONS_UNSAFE")
    return path.read_bytes()


def read_state(path: Path, migration_id: str) -> tuple[dict, bytes]:
    raw = private_bytes(path)
    state = json.loads(raw)
    require(type(state) is dict
            and state.get("schema") == SCHEMA
            and state.get("migration_id") == migration_id,
            "MIGRATION_ID_OR_SCHEMA_CHANGED")
    return state, raw


def verify_runtime() -> None:
    require(os.geteuid() == 0, "CP2_ROOT_REQUIRED")
    r = subprocess.run(["vfops", "--build-id"], capture_output=True,
                       text=True, check=False, timeout=10)
    require(r.returncode == 0 and r.stdout.strip() == "0.1.0-release113",
            "BUILD113_REQUIRED")
    require((ROOT / "BUILD_ID").read_text().strip() == "0.1.0-release113",
            "RUNTIME_BUILD_MISMATCH")
    require(gitblob(private_bytes(ROOT / ".runtime-manifest.gitblob"))
            == RUNTIME_BLOB, "RUNTIME_MANIFEST_DRIFT")
    require(gitblob(private_bytes(ROOT / "lib/server_migration_pull.py"))
            == ENGINE_BLOB, "RUNTIME_ENGINE_DRIFT")


def prove_original_and_child(parent: dict, child: dict) -> list[dict]:
    require(parent.get("status") == "PREPARE_FAILED"
            and parent.get("last_sql_guard_failure") is None
            and len(parent.get("sites", [])) == 17
            and parent["sites"][7].get("domain") == "ilovem3u8.kewaro.com",
            "ORIGINAL_PARENT_LEGACY_SCOPE_DRIFT")
    require(child.get("status") == "PREPARE_FAILED"
            and child.get("partial_parent_migration_id") == ORIGINAL
            and child.get("cutover_prohibited") is True
            and isinstance(child.get("last_sql_guard_failure"), dict)
            and child["last_sql_guard_failure"].get("reason") == "CONDITIONAL_DDL",
            "NINE_CHILD_GUARD_DRIFT")
    for key in ("source_runtime_frozen", "target_runtime_activated",
                "dns_changed_by_p07", "source_delete_allowed",
                "existing_target_overwrite_allowed"):
        require(parent.get(key) is False and child.get(key) is False,
                "SOURCE_OR_TARGET_SAFETY_DRIFT")
    require(child.get("source_server_identity") == parent.get("source_server_identity")
            and isinstance(parent.get("source_server_identity"), str)
            and len(parent["source_server_identity"]) >= 8
            and child.get("target_server_identity") == parent.get("target_server_identity")
            and child.get("source") == parent.get("source"),
            "MIGRATION_SOURCE_TARGET_IDENTITY_DRIFT")
    sites = child.get("sites")
    require(type(sites) is list and len(sites) == 9
            and tuple(x.get("domain") for x in sites if isinstance(x, dict))
            == NINE_DOMAINS, "NINE_CHILD_SITE_ORDER_DRIFT")
    require(all(type(row) is dict for row in sites), "NINE_CHILD_SITE_INVALID")
    require(all(x.get("stage_status") == "PULLED_STAGED" for x in sites[:6])
            and sites[6].get("stage_status") == "PENDING"
            and all(x.get("stage_status") == "PENDING" for x in sites[7:]),
            "STAGED_PREFIX_OR_UNZIP_BOUNDARY_CHANGED")
    require(not sites[7].get("mysql_prepare_count")
            and not sites[8].get("mysql_prepare_count"),
            "LAST_TWO_ALREADY_STARTED")
    from_parent = parent["sites"][15:]
    from_child = sites[7:]
    require(tuple(x.get("domain") for x in from_parent) == DOMAINS
            and tuple(x.get("domain") for x in from_child) == DOMAINS,
            "ORIGINAL_LAST_TWO_SCOPE_CHANGED")
    for a, b in zip(from_parent, from_child):
        for key in ("domain", "site_user", "site_root",
                    "document_root", "runtime", "mysql_databases"):
            require(a.get(key) == b.get(key), "LAST_TWO_IDENTITY_DRIFT")
        require(a.get("stage_status") in (None, "PENDING"),
                "ORIGINAL_LAST_TWO_ALREADY_STARTED")
        require(type(a.get("site_user")) is str
                and re.fullmatch(r"[A-Za-z0-9_-]+", a["site_user"]),
                "LAST_TWO_USER_UNPROVEN")
        require(type(a.get("mysql_databases")) is list
                and len(a["mysql_databases"]) <= 1
                and all(type(db) is str and re.fullmatch(r"[A-Za-z0-9_-]+", db)
                        for db in a["mysql_databases"]),
                "LAST_TWO_DB_UNPROVEN")
        require(type(a.get("site_root")) is str
                and type(a.get("document_root")) is str,
                "LAST_TWO_ROOT_UNPROVEN")
    return from_child


def ensure_no_duplicate_child() -> None:
    require(STATES.is_dir() and not STATES.is_symlink(),
            "STATES_DIRECTORY_UNAVAILABLE")
    for directory in STATES.iterdir():
        if not directory.is_dir() or directory.is_symlink():
            continue
        p = directory / "state.json"
        if not p.exists():
            continue
        require(p.is_file() and not p.is_symlink(),
                "MIGRATION_STATE_FILE_UNSAFE")
        state = json.loads(p.read_text())
        require(type(state) is dict, "MIGRATION_STATE_UNREADABLE")
        if state.get("partial_parent_migration_id") in {NINE_CHILD, ORIGINAL}:
            require(state.get("migration_id") == NINE_CHILD
                    and state.get("partial_parent_migration_id") == ORIGINAL,
                    "NINE_CHILD_ALREADY_HAS_DESCENDANT")


def ensure_target_unoccupied(sites: list[dict]) -> None:
    import inventory
    info = inventory.build_manifest(Path("/"))
    require(info.get("discovery_source") == "cloudpanel_db+vhost",
            "TARGET_INVENTORY_UNPROVEN")
    rows = info.get("sites")
    require(type(rows) is list, "TARGET_SITES_UNPROVEN")
    existing_domains = {str(x.get("domain", "")).lower()
                        for x in rows if type(x) is dict}
    existing_users = {str(x.get("site_user", ""))
                      for x in rows if type(x) is dict}
    existing_db = {str(d) for x in rows if type(x) is dict
                   for d in (x.get("mysql_databases") or [])}
    for row in sites:
        require(row["domain"].lower() not in existing_domains
                and row["site_user"] not in existing_users
                and not (Path("/home") / row["site_user"]).exists()
                and all(db not in existing_db
                        and not (Path("/var/lib/mysql") / db).exists()
                        for db in row["mysql_databases"]),
                "TARGET_HAS_ALREADY_STAGED_SITE_OR_DB")


def snapshot(name: str, original: bytes) -> None:
    require(RECOVERY_DIR.exists() and RECOVERY_DIR.is_dir()
            and not RECOVERY_DIR.is_symlink(), "RECOVERY_DIR_MISSING_OR_UNSAFE")
    p = RECOVERY_DIR / (name + ".before-last-two.json")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(str(p), flags, 0o600)
    except FileExistsError:
        require(private_bytes(p) == original,
                "EARLIER_SNAPSHOT_DIFFERS")
        return
    with os.fdopen(fd, "wb") as f:
        f.write(original)
        f.flush()
        os.fsync(f.fileno())
    require(private_bytes(p) == original, "SNAPSHOT_VERIFY_FAILED")


def main() -> int:
    require(sys.argv[1:] == ["--stage-last-two"],
            "EXPLICIT_STAGE_LAST_TWO_REQUIRED")
    os.umask(0o077)
    verify_runtime()
    sys.path.insert(0, str(ROOT / "lib"))
    import server_migration_pull as engine
    require(engine.SCHEMA == SCHEMA, "MIGRATION_ENGINE_SCHEMA_DRIFT")
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(str(LOCK), flags, 0o600)
    meta = os.fstat(fd)
    require(stat.S_ISREG(meta.st_mode) and meta.st_uid == 0
            and not meta.st_mode & 0o022, "UNSAFE_MIGRATION_LOCK")
    with os.fdopen(fd, "r+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Stop("MIGRATION_LOCK_ALREADY_HELD") from None
        parent, parent_bytes = read_state(ORIGINAL_FILE, ORIGINAL)
        child, child_bytes = read_state(NINE_FILE, NINE_CHILD)
        last_two = prove_original_and_child(parent, child)
        ensure_no_duplicate_child()
        ensure_target_unoccupied(last_two)
        snapshot(ORIGINAL, parent_bytes)
        snapshot(NINE_CHILD, child_bytes)
        require(private_bytes(ORIGINAL_FILE) == parent_bytes
                and private_bytes(NINE_FILE) == child_bytes,
                "MIGRATION_STATE_CHANGED_BEFORE_WRITE")
        print("P07_LAST_TWO_BOUNDARY=PASS", flush=True)
        print("DOMAIN_SCOPE=updates.kewaro.com,www3.m3u8.one", flush=True)
        print("SOURCE_FREEZE=FORBIDDEN", flush=True)
        print("CUTOVER_DNS=FORBIDDEN", flush=True)
        print("NO_EXISTING_TARGET_OVERWRITE=YES", flush=True)
        try:
            descendant = engine.prepare_migration(
                parent["source"], list(DOMAINS), "PREPARE_PULL_MIGRATION",
                remainder_parent=NINE_CHILD,
                expected_source_identity=parent["source_server_identity"],
                expected_remainder_sites=[dict(row) for row in last_two],
            )
        except Exception as exc:
            print("STAGING_STOPPED_NO_RETRY=YES", flush=True)
            print("BLOCKER_CLASS=" + type(exc).__name__, flush=True)
            if isinstance(exc, engine.PullMigrationError):
                print("BLOCKER=" + str(exc)[:400], flush=True)
            print("INSPECT_NEW_CHILD_BEFORE_ANY_RETRY=YES", flush=True)
            raise Stop("STAGING_LAST_TWO_INCOMPLETE") from None
        require(private_bytes(ORIGINAL_FILE) == parent_bytes
                and private_bytes(NINE_FILE) == child_bytes,
                "PARENT_OR_NINE_CHILD_MODIFIED")
        require(descendant.get("partial_parent_migration_id") == NINE_CHILD
                and descendant.get("cutover_prohibited") is True
                and descendant.get("source_runtime_frozen") is False
                and descendant.get("dns_changed_by_p07") is False
                and descendant.get("existing_target_overwrite_allowed") is False
                and descendant.get("status") == "PREPARED"
                and tuple(x.get("domain") for x in descendant.get("sites", []))
                == DOMAINS, "NEW_CHILD_INCOMPLETE")
        print("NEW_CHILD_ID=" + descendant["migration_id"], flush=True)
        print("NEW_CHILD_STATUS=PREPARED", flush=True)
        print("CUTOVER_ALLOWED=NO", flush=True)
        print("PARENTS_UNMODIFIED=YES", flush=True)
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Stop, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print("BLOCKED=" + (str(exc) if type(exc) is Stop
                            else type(exc).__name__), file=sys.stderr)
        raise SystemExit(13) from None
