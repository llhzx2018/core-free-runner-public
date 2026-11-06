#!/usr/bin/env python3
"""P07 release113 / one-time OWNER-authorized legacy nine-site staging.

Requires existing release113 runtime, preserves the failed 17-site parent,
refuses any existing child, binds exact nine site IDs + source fingerprints,
and delegates actual migration to the published fail-closed engine.
NO cutover, old-server freeze, DNS, retry or destructive cleanup.
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

PARENT_ID = "pull-20261028T103425Z-98050c76"
DOMAINS = (
    "infra.kewaro.com", "lib.kewaro.com", "press.kewaro.com",
    "seo.kewaro.com", "start.kewaro.com", "textbox.kewaro.com",
    "unzip.kewaro.com", "updates.kewaro.com", "www3.m3u8.one",
)
ROOT = Path("/opt/vf-server-ops")
STATES = Path("/var/lib/vf-server-ops/server-migrations")
PARENT_FILE = STATES / PARENT_ID / "state.json"
BACKUP_MANIFEST = Path(
    "/var/backups/vf-server-ops/"
    "ilovem3u8.kewaro.com_20261030T095348Z/manifest.json"
)
RUNTIME_MANIFEST_BLOB = "a48aa44b96b0a554ae9170d289c46d5cfb56d937"
SOURCE_BLOB = "71fb59ad7d005b88e39cbeed4b3302c7f313bd06"
RECOVERY_DIR = Path("/var/lib/vf-server-ops/operator-recovery")
LOCK_FILE = Path("/run/lock/p07-legacy-nine-staging.lock")


class Stop(ValueError):
    pass


def need(condition: bool, reason: str) -> None:
    if not condition:
        raise Stop(reason)


def git_blob(data: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    ).hexdigest()


def regular_root_owned(path: Path) -> bytes:
    meta = path.lstat()
    need(stat.S_ISREG(meta.st_mode), "EVIDENCE_NOT_REGULAR")
    need(meta.st_uid == 0 and not meta.st_mode & 0o022, "EVIDENCE_NOT_PRIVATE")
    return path.read_bytes()


def verify_runtime() -> None:
    need(os.geteuid() == 0, "REQUIRES_CP2_ROOT")
    need(ROOT.is_dir(), "RELEASE113_RUNTIME_NOT_FOUND")
    version = subprocess.run(
        ["vfops", "--build-id"], capture_output=True, text=True,
        timeout=10, check=False,
    )
    need(version.returncode == 0 and
         version.stdout.strip() == "0.1.0-release113",
         "RELEASE113_BUILD_REQUIRED")
    need((ROOT / "BUILD_ID").read_text().strip() == "0.1.0-release113",
         "RUNTIME_ROOT_BUILD_UNPROVEN")
    installed = regular_root_owned(ROOT / ".runtime-manifest.gitblob")
    need(git_blob(installed) == RUNTIME_MANIFEST_BLOB,
         "RELEASE113_RUNTIME_MANIFEST_DRIFT")
    need(git_blob(regular_root_owned(ROOT / "lib/server_migration_pull.py"))
         == SOURCE_BLOB, "RELEASE113_MIGRATION_CODE_DRIFT")


def validate_parent(parent: dict) -> list[dict]:
    need(type(parent) is dict and
         parent.get("schema") == "vf-server-ops.server-migration.target-pull.v1"
         and parent.get("migration_id") == PARENT_ID
         and parent.get("status") == "PREPARE_FAILED",
         "LEGACY_PARENT_ID_OR_STATUS_CHANGED")
    for key in (
        "source_runtime_frozen", "target_runtime_activated",
        "dns_changed_by_p07", "source_delete_allowed",
        "existing_target_overwrite_allowed",
    ):
        need(parent.get(key) is False, "PARENT_RUNTIME_BOUNDARY_UNPROVEN")
    need(not parent.get("partial_parent_migration_id"),
         "PARENT_IS_ALREADY_PARTIAL_CHILD")
    need(parent.get("last_sql_guard_failure") is None,
         "THIS_ENTRY_IS_FOR_LEGACY_MISSING_SQL_GUARD_ONLY")
    source = parent.get("source")
    identity = parent.get("source_server_identity")
    need(type(source) is dict and source.get("ssh_user") == "root"
         and bool(source.get("host")) and bool(source.get("ip"))
         and bool(source.get("ssh_port")) and
         type(identity) is str and 8 <= len(identity) <= 256,
         "PARENT_SOURCE_IDENTITY_UNPROVEN")
    sites = parent.get("sites")
    need(type(sites) is list and len(sites) == 17 and
         type(sites[7]) is dict and
         sites[7].get("domain") == "ilovem3u8.kewaro.com",
         "PARENT_SITE8_BOUNDARY_UNPROVEN")
    need(all(type(row) is dict for row in sites),
         "PARENT_SITE_RECORDS_INVALID")
    selected = sites[8:]
    need(tuple(row.get("domain") for row in selected) == DOMAINS,
         "REMAINDER_DOMAIN_ORDER_DRIFT")
    all_domains = [str(row.get("domain", "")).lower() for row in sites]
    all_users = [row.get("site_user") for row in sites]
    need(len(set(all_domains)) == 17 and len(set(all_users)) == 17,
         "PARENT_DUPLICATE_SITE_OR_USER")
    for row in selected:
        need(row.get("stage_status") in (None, "PENDING") and
             not row.get("mysql_prepare_count"),
             "REMAINDER_ALREADY_STARTED")
        user = row.get("site_user")
        need(type(user) is str and
             re.fullmatch(r"[A-Za-z0-9_-]+", user) is not None,
             "REMAINDER_USER_INVALID")
        dbs = row.get("mysql_databases")
        need(type(dbs) is list and
             all(type(db) is str and
                 re.fullmatch(r"[A-Za-z0-9_-]+", db) is not None for db in dbs),
             "REMAINDER_DB_IDENTITY_UNPROVEN")
        need(type(row.get("site_root")) is str and
             type(row.get("document_root")) is str,
             "REMAINDER_PATH_IDENTITY_UNPROVEN")
    return selected


def existing_children() -> list[str]:
    children = []
    for directory in STATES.iterdir():
        if not directory.is_dir() or directory.is_symlink():
            continue
        file = directory / "state.json"
        if not file.exists():
            continue
        if file.is_symlink() or not file.is_file():
            raise Stop("UNSAFE_MIGRATION_STATE_LINK")
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise Stop("OTHER_MIGRATION_STATE_UNREADABLE") from None
        if (isinstance(data, dict) and
                data.get("partial_parent_migration_id") == PARENT_ID):
            children.append(str(data.get("migration_id") or directory.name))
    return children


def require_target_empty(sites: list[dict]) -> None:
    import inventory
    manifest = inventory.build_manifest(Path("/"))
    need(manifest.get("discovery_source") == "cloudpanel_db+vhost",
         "TARGET_INVENTORY_INCOMPLETE")
    rows = manifest.get("sites")
    need(type(rows) is list, "TARGET_INVENTORY_MISSING_SITES")
    target_domains = {
        str(s.get("domain", "")).lower() for s in rows if type(s) is dict
    }
    target_users = {
        str(s.get("site_user", "")) for s in rows if type(s) is dict
    }
    target_dbs = {
        str(db) for s in rows if type(s) is dict
        for db in (s.get("mysql_databases") or [])
    }
    for site in sites:
        user = site["site_user"]
        need(site["domain"].lower() not in target_domains and
             user not in target_users and
             not (Path("/home") / user).exists() and
             all(db not in target_dbs and
                 not (Path("/var/lib/mysql") / db).exists()
                 for db in site["mysql_databases"]),
             "TARGET_ALREADY_HAS_REMAINDER_ASSET")


def preserve_parent(original: bytes) -> None:
    RECOVERY_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    need(not RECOVERY_DIR.is_symlink(), "RECOVERY_DIRECTORY_UNSAFE")
    RECOVERY_DIR.chmod(0o700)
    dest = RECOVERY_DIR / (PARENT_ID + ".before-nine.json")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(str(dest), flags, 0o600)
    except FileExistsError:
        existing = regular_root_owned(dest)
        need(existing == original, "RECOVERY_PARENT_SNAPSHOT_DIFFERS")
        return
    with os.fdopen(fd, "wb") as stream:
        stream.write(original)
        stream.flush()
        os.fsync(stream.fileno())
    need(regular_root_owned(dest) == original, "PARENT_SNAPSHOT_VERIFY_FAILED")


def main() -> int:
    need(sys.argv[1:] == ["--stage-nine"], "EXPLICIT_STAGE_NINE_ARG_REQUIRED")
    os.umask(0o077)
    verify_runtime()
    sys.path.insert(0, str(ROOT / "lib"))
    import server_migration_pull as engine
    need(engine.SCHEMA == "vf-server-ops.server-migration.target-pull.v1",
         "ENGINE_SCHEMA_DRIFT")
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(str(LOCK_FILE), flags, 0o600)
    details = os.fstat(fd)
    need(stat.S_ISREG(details.st_mode) and details.st_uid == 0
         and not details.st_mode & 0o022, "UNSAFE_MIGRATION_LOCK")
    with os.fdopen(fd, "r+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Stop("ANOTHER_NINE_SITE_STAGE_RUNNING") from None
        original = regular_root_owned(PARENT_FILE)
        parent = json.loads(original)
        sites = validate_parent(parent)
        need(not existing_children(), "REMAINDER_CHILD_ALREADY_EXISTS")
        need(BACKUP_MANIFEST.is_file() and
             not BACKUP_MANIFEST.is_symlink(),
             "SITE8_TARGET_RECOVERY_MANIFEST_MISSING")
        require_target_empty(sites)
        preserve_parent(original)
        need(regular_root_owned(PARENT_FILE) == original,
             "PARENT_CHANGED_BEFORE_STAGE")
        print("BOUNDARY_VERIFIED=release113+legacy-parent+exact-nine", flush=True)
        print("TARGET_REMAINDER_EMPTY=YES", flush=True)
        print("PARENT_SNAPSHOT_PRIVATE=YES", flush=True)
        print("OPERATION=STAGING_NINE_SITES_ONLY", flush=True)
        print("SOURCE_HELPER_TEMPORARY_FILES=YES", flush=True)
        print("CUTOVER_DNS_SOURCE_FREEZE=FORBIDDEN", flush=True)
        try:
            child = engine.prepare_migration(
                parent["source"], list(DOMAINS), "PREPARE_PULL_MIGRATION",
                remainder_parent=PARENT_ID,
                expected_source_identity=parent["source_server_identity"],
                expected_remainder_sites=[dict(row) for row in sites],
            )
        except Exception as exc:
            print("STAGING_STOPPED_NO_AUTOMATIC_RETRY=YES", flush=True)
            print("BLOCKER_CLASS=" + type(exc).__name__, flush=True)
            if isinstance(exc, engine.PullMigrationError):
                print("BLOCKER=" + str(exc)[:300], flush=True)
            found = existing_children()
            print("CHILD_IDS=" + (",".join(found) if found else "NONE"),
                  flush=True)
            raise Stop("STAGING_INCOMPLETE_REQUIRES_EXISTING_CHILD_INSPECTION") from None
        need(regular_root_owned(PARENT_FILE) == original,
             "PARENT_STATE_CHANGED_DURING_STAGE")
        need(child.get("partial_parent_migration_id") == PARENT_ID and
             child.get("cutover_prohibited") is True and
             child.get("existing_target_overwrite_allowed") is False and
             child.get("source_runtime_frozen") is False and
             child.get("dns_changed_by_p07") is False and
             child.get("status") == "PREPARED" and
             tuple(row.get("domain") for row in child.get("sites", []))
             == DOMAINS,
             "CHILD_STAGE_RESULT_NOT_SAFE_OR_INCOMPLETE")
        print("CHILD_MIGRATION_ID=" + str(child["migration_id"]), flush=True)
        print("CHILD_STAGE=PREPARED", flush=True)
        print("CHILD_CUTOVER_ALLOWED=NO", flush=True)
        print("PARENT_UNCHANGED=YES", flush=True)
        print("STAGING_READY_FOR_OWNER_INSPECTION=YES", flush=True)
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Stop, OSError, json.JSONDecodeError,
            subprocess.TimeoutExpired) as exc:
        print("BLOCKED=" + (str(exc) if isinstance(exc, Stop)
                            else type(exc).__name__), file=sys.stderr)
        raise SystemExit(13) from None
