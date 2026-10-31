#!/usr/bin/env python3
"""P07 one-shot www3 isolated database RESTORE PROBE on CP2.

This is NOT cutover, promotion, or any existing target DB import. The only
business-adjacent write is creation/import into one cryptographically unique
scratch database registered to the already staged www3 site. It is never
retried or deleted automatically; original site config and DBs stay intact.
Protected source copy and private result record remain on CP2.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import stat
import subprocess
import sys

MID = "pull-20261031T095604Z-edae3c44"
PARENT = "pull-20261031T094144Z-d045fa5a"
DOMAIN = "www3.m3u8.one"
STATE = Path("/var/lib/vf-server-ops/server-migrations") / MID / "state.json"
SOURCE_RUNTIME = f"/var/lib/vf-server-ops/pull-source/{MID}/runtime"
SCRATCH_ROOT = STATE.parent / "recovery-scratch-www3"
PROBE_MAX_BYTES = 1024 * 1024 * 1024

REMOTE_EXPORT = r'''
import hashlib, os, re, sys
from pathlib import Path
import cloudpanel, inventory
domain, database, mid, token = sys.argv[1:]
root = Path("/var/lib/vf-server-ops/pull-source") / mid / "data"
if not (root.is_dir() and not root.is_symlink() and
        re.fullmatch(r"[a-f0-9]{24}", token)):
    sys.exit(13)
sites = [x for x in inventory.build_manifest(Path("/")).get("sites", [])
         if isinstance(x, dict) and x.get("domain") == domain]
if len(sites) != 1 or (sites[0].get("mysql_databases") or []) != [database]:
    sys.exit(14)
outdir = root / ("scratch-" + token)
outdir.mkdir(mode=0o700, exist_ok=False)
outdir.chmod(0o700)
dump = outdir / "source.sql.gz"
try:
    cloudpanel.export_database(database, dump, clpctl="clpctl")
except (cloudpanel.CloudPanelError, ValueError):
    sys.exit(15)
if not dump.is_file() or dump.is_symlink() or dump.stat().st_size == 0:
    sys.exit(16)
dump.chmod(0o600)
print("SOURCE_EXPORT_READY=YES")
'''

class Stop(RuntimeError):
    pass


def output(k: str, v: object) -> None:
    print(f"{k}={v}", flush=True)


def state_preflight(engine, inventory):
    x = STATE.lstat()
    if (not stat.S_ISREG(x.st_mode) or x.st_uid != 0
            or x.st_mode & 0o077):
        raise Stop("CHILD_STATE_NOT_PRIVATE")
    s = json.loads(STATE.read_text())
    sites = s.get("sites")
    if not (
        s.get("migration_id") == MID
        and s.get("partial_parent_migration_id") == PARENT
        and s.get("status") == "PREPARE_FAILED"
        and s.get("cutover_prohibited") is True
        and s.get("source_runtime_frozen") is False
        and s.get("dns_changed_by_p07") is False
        and s.get("source_runtime_path") == SOURCE_RUNTIME
        and isinstance(sites, list)
        and len(sites) == 2
        and sites[0].get("domain") == "updates.kewaro.com"
        and sites[0].get("stage_status") == "PULLED_STAGED"
        and sites[1].get("domain") == DOMAIN
        and sites[1].get("stage_status") == "PENDING"
    ):
        raise Stop("CHILD_RECOVERY_BOUNDARY_CHANGED")
    dbs = sites[1].get("mysql_databases")
    if (type(dbs) is not list or len(dbs) != 1
            or type(dbs[0]) is not str
            or not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", dbs[0])):
        raise Stop("ORIGINAL_DATABASE_UNPROVEN")
    if engine.target_identity() != s.get("target_server_identity"):
        raise Stop("TARGET_IDENTITY_CHANGED")
    if not engine.cloudpanel_database_server_ready_local():
        raise Stop("TARGET_DATABASE_SERVICE_UNAVAILABLE")
    engine.require_mariadb_target()
    if not (shutil.which("mariadb") and shutil.which("gzip")):
        raise Stop("TARGET_CLIENT_MISSING")
    manifest = inventory.build_manifest(Path("/"))
    if manifest.get("discovery_source") != "cloudpanel_db+vhost":
        raise Stop("TARGET_INVENTORY_UNPROVEN")
    rows = [x for x in manifest.get("sites", [])
            if isinstance(x, dict) and x.get("domain") == DOMAIN]
    if len(rows) != 1:
        raise Stop("TARGET_SITE_NOT_UNIQUE")
    if rows[0].get("site_user") != sites[1].get("site_user"):
        raise Stop("TARGET_SITE_OWNER_CHANGED")
    if rows[0].get("mysql_databases") != []:
        raise Stop("TARGET_DATABASE_ALREADY_REGISTERED")
    root = Path(str(sites[1].get("site_root", "")))
    if not str(root).startswith("/home/") or not root.is_dir():
        raise Stop("TARGET_WEBSITE_ROOT_MISSING")
    if shutil.disk_usage("/").free < 2 * 1024 * 1024 * 1024:
        raise Stop("SCRATCH_DISK_SPACE_LOW")
    if SCRATCH_ROOT.exists() or SCRATCH_ROOT.is_symlink():
        raise Stop("SCRATCH_ALREADY_ATTEMPTED_DO_NOT_RETRY")
    return s, dbs[0]


def sha256_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def inspect_archive(path):
    count = 0
    ddl_seen = 0
    use_db = False
    unsafe = False
    with gzip.open(path, "rb") as f:
        while True:
            line = f.readline(min(1024 * 1024, PROBE_MAX_BYTES - count + 1))
            if not line:
                break
            count += len(line)
            if count > PROBE_MAX_BYTES:
                raise Stop("SQL_UNCOMPRESSED_LIMIT_EXCEEDED")
            stripped = line.lstrip()
            if re.match(rb"^CREATE\s+TABLE\b", stripped, re.I):
                ddl_seen += 1
            if re.match(rb"^(?:USE|CREATE\s+DATABASE|DROP\s+DATABASE|ALTER\s+DATABASE)\b", stripped, re.I):
                use_db = True
            if re.match(rb"^(?:GRANT|REVOKE|INSTALL\s+PLUGIN|SET\s+(?:GLOBAL|PERSIST))\b", stripped, re.I):
                unsafe = True
    if ddl_seen == 0:
        raise Stop("SOURCE_SQL_NO_TABLES")
    if use_db or unsafe:
        raise Stop("SOURCE_SQL_CROSS_DATABASE_OR_PRIVILEGED_DIRECTIVE")
    return count, ddl_seen


def isolated_import(user, password, database, dump, work):
    config = work / "mysql-client.cnf"
    # Password comes from token_urlsafe; no shell injection/escaping needed.
    config.write_text("[client]\nuser=" + user + "\npassword=" + password +
                      "\nhost=localhost\n", encoding="utf-8")
    config.chmod(0o600)
    error_log = work / "import.stderr"
    args = ["mariadb", "--defaults-extra-file=" + str(config),
            "--binary-mode", "--default-character-set=utf8mb4", database]
    try:
        with error_log.open("wb") as err:
            os.chmod(error_log, 0o600)
            unzip = subprocess.Popen(["gzip", "-dc", str(dump)], stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL)
            try:
                result = subprocess.run(args, stdin=unzip.stdout,
                                        stdout=subprocess.DEVNULL, stderr=err,
                                        timeout=1800, check=False)
            finally:
                if unzip.stdout:
                    unzip.stdout.close()
                try:
                    unzip.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    unzip.kill()
                    unzip.wait()
        return (result.returncode == 0 and unzip.returncode == 0)
    except (OSError, subprocess.SubprocessError):
        return False
    finally:
        config.unlink(missing_ok=True)


def run():
    if sys.argv[1:] != ["--restore-www3-to-new-isolated-db"]:
        raise Stop("EXPLICIT_ISOLATED_RESTORE_ARGUMENT_REQUIRED")
    if os.geteuid() != 0:
        raise Stop("ROOT_CP2_REQUIRED")
    sys.path.insert(0, "/opt/vf-server-ops/lib")
    import server_migration_pull as engine
    import cloudpanel, inventory

    s, origin_db = state_preflight(engine, inventory)
    token = secrets.token_hex(12)
    scratch_db = "p07scratch_" + token[:12]
    scratch_user = "p07stage_" + token[:12]
    scratch_pass = secrets.token_urlsafe(32)
    SCRATCH_ROOT.mkdir(mode=0o700, parents=False, exist_ok=False)
    SCRATCH_ROOT.chmod(0o700)
    record = SCRATCH_ROOT / "status.json"
    source_dump = SCRATCH_ROOT / "source.sql.gz"
    result_state = {"original_site": DOMAIN, "migration_id": MID,
                    "scratch_database": scratch_db, "scratch_user": scratch_user,
                    "status": "SOURCE_EXPORT_IN_PROGRESS",
                    "site_config_modified": False, "dns_changed": False,
                    "source_frozen": False, "existing_target_database_modified": False,
                    "cutover_allowed": False}
    def save():
        target = record.with_suffix(".tmp")
        fd = os.open(target, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f: json.dump(result_state, f, sort_keys=True)
        os.replace(target, record)
    save()
    output("BOUNDARY", "NEW_SCRATCH_DATABASE_ONLY")
    output("OLD_SERVER_FROZEN", "NO")
    output("DNS_CHANGED", "NO")
    remote_dir = f"/var/lib/vf-server-ops/pull-source/{MID}/data/scratch-{token}"
    remote_dump = remote_dir + "/source.sql.gz"
    args = ["env", f"PYTHONPATH={SOURCE_RUNTIME}/lib", "python3", "-c",
            REMOTE_EXPORT, DOMAIN, origin_db, MID, token]
    try:
        proc = engine.source_remote(s["source"], shlex.join(args), timeout=1800,
                                    check=False)
        if proc.returncode != 0 or proc.stdout.strip() != "SOURCE_EXPORT_READY=YES":
            raise Stop("OLD_SERVER_DATABASE_EXPORT_FAILED")
        result_state["status"] = "SOURCE_EXPORTED"
        save()
        engine.pull_path(s["source"], remote_dump, source_dump)
        source_dump.chmod(0o600)
        actual_bytes, source_tables = inspect_archive(source_dump)
        result_state.update({"status": "SOURCE_COPY_PROTECTED",
                             "source_dump_sha256": sha256_file(source_dump),
                             "source_uncompressed_bytes": actual_bytes,
                             "source_create_table_lines": source_tables})
        remote_hash = engine.source_remote(
            s["source"], "sha256sum -- " + shlex.quote(remote_dump),
            timeout=90, check=False)
        if (remote_hash.returncode != 0 or
                not re.fullmatch(r"[0-9a-f]{64}", remote_hash.stdout.split()[0]) or
                remote_hash.stdout.split()[0] != result_state["source_dump_sha256"]):
            raise Stop("SOURCE_TRANSFER_INTEGRITY_UNVERIFIED")
        save()
        output("SOURCE_ARCHIVE_TRANSFER", "SHA256_PASS")
        # Only now create a unique unbound scratch DB. The site app remains
        # pointed at the old/unchanged configuration.
        result_state["status"] = "SCRATCH_DB_CREATION_STARTED"
        save()
        try:
            cloudpanel.add_database(DOMAIN, scratch_db, scratch_user,
                                    scratch_pass, clpctl="clpctl")
        except (cloudpanel.CloudPanelError, ValueError):
            raise Stop("ISOLATED_DATABASE_CREATE_FAILED")
        result_state["status"] = "ISOLATED_DATABASE_CREATED"
        result_state["credential_file"] = "scratch-credentials.json"
        creds = SCRATCH_ROOT / "scratch-credentials.json"
        fd = os.open(creds, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump({"database": scratch_db, "user": scratch_user,
                       "password": scratch_pass}, f)
        save()
        output("ISOLATED_DATABASE_CREATED", "YES")
        result_state["status"] = "ISOLATED_IMPORT_STARTED"
        save()
        ok = isolated_import(scratch_user, scratch_pass, scratch_db,
                             source_dump, SCRATCH_ROOT)
        if not ok:
            raise Stop("ISOLATED_IMPORT_FAILED_NO_RETRY")
        result_state["status"] = "ISOLATED_IMPORT_COMPLETED_NOT_VERIFIED"
        save()
        output("ISOLATED_RESTORE", "IMPORTED_NOT_VERIFIED")
        output("NEXT_GATE", "INDEPENDENT_SOURCE_TARGET_ROW_AND_SCHEMA_PARITY")
    except Stop as exc:
        result_state["status"] = "BLOCKED"
        result_state["blocker"] = str(exc)
        save()
        output("BLOCKED", str(exc))
        return 13
    except Exception:
        result_state["status"] = "BLOCKED"
        result_state["blocker"] = "UNCLASSIFIED_FAILURE"
        save()
        output("BLOCKED", "UNCLASSIFIED_FAILURE")
        return 13
    finally:
        cleanup = ("rm -f -- " + shlex.quote(remote_dump) + "; "
                   "rmdir -- " + shlex.quote(remote_dir))
        try:
            engine.source_remote(s["source"], cleanup, timeout=120, check=False)
        except Exception:
            output("SOURCE_TEMP_CLEANUP", "NOT_CONFIRMED")
        output("CP2_STATE_FILE", str(record))
        output("SITE_CONFIG_MODIFIED", "NO")
        output("CUTOVER_ALLOWED", "NO")
        output("AUTOMATIC_RETRY", "NO")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except (Stop, OSError, ValueError, json.JSONDecodeError) as exc:
        print("BLOCKED=" + (str(exc) if isinstance(exc, Stop) else "PREFLIGHT_OR_STATE_ERROR"))
        raise SystemExit(13) from None
