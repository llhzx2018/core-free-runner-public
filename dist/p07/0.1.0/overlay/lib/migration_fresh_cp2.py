#!/usr/bin/env python3
"""Fresh CP2 receiver entry: inventory -> all-DB SQL screen -> original prepare.

Never resumes a partially migrated CP2, changes DNS, freezes the old server,
performs a cutover, or bypasses the existing SQL import / rollback guards.
Preview uses an explicitly acknowledged temporary old-source probe helper and
private SQL dumps; it is NOT a read-only/source-no-write operation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any

import server_migration_pull as pull

DATABASE_SITES = frozenset({
    "ilovem3u8.kewaro.com", "unzip.kewaro.com", "www3.m3u8.one"
})
CONFIRM_PREVIEW = "ALLOW_TEMP_SOURCE_PREFLIGHT"
CONFIRM_PREPARE = "PREPARE_FRESH_CP2_17_SITES"
SCHEMA = "P07_FRESH_CP2_17_SITE_PREFLIGHT_V1"


class FreshBlocked(RuntimeError):
    pass


def need(ok: bool, code: str) -> None:
    if not ok:
        raise FreshBlocked(code)


def inventory_scope(plan: dict[str, Any]) -> tuple[list[str], list[tuple[str, str]]]:
    """Verify all 17 sites and original three-DB ownership before writes."""
    need(isinstance(plan, dict) and plan.get("status") == "READY"
         and plan.get("schema") == pull.SCHEMA,
         "FRESH_SOURCE_INVENTORY_INVALID")
    rows = plan.get("sites")
    need(type(rows) is list and len(rows) == 17,
         "FRESH_SOURCE_REQUIRES_EXACTLY_17_SITES")
    domains, users, databases = set(), set(), set()
    names: list[str] = []
    db_sites: list[tuple[str, str]] = []
    for site in rows:
        need(type(site) is dict, "FRESH_SITE_METADATA_INVALID")
        domain, user, dbs = (site.get("domain"), site.get("site_user"),
                             site.get("mysql_databases"))
        root = site.get("site_root")
        need(type(domain) is str and re.fullmatch(r"[a-zA-Z0-9.-]{1,253}", domain)
             and domain.lower() not in domains
             and type(user) is str
             and re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_-]{0,63}", user)
             and user not in users
             and type(root) is str and root.startswith("/home/" + user + "/")
             and ".." not in Path(root).parts
             and type(dbs) is list and len(dbs) <= 1,
             "FRESH_SOURCE_SITE_SCOPE_CHANGED")
        domains.add(domain.lower())
        names.append(domain.lower())
        users.add(user)
        if dbs:
            db = dbs[0]
            need(type(db) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", db)
                 and db not in databases,
                 "FRESH_SOURCE_DATABASE_SCOPE_INVALID")
            databases.add(db)
            db_sites.append((domain.lower(), db))
    need({domain for domain, _db in db_sites} == DATABASE_SITES
         and len(databases) == 3,
         "FRESH_THREE_DATABASE_OWNERS_CHANGED")
    need(type(plan.get("external_assets")) is list
         and type(plan.get("sqlite_assets")) is list
         and type(plan.get("runtime_assets")) is dict,
         "FRESH_SOURCE_RESOURCE_INVENTORY_INCOMPLETE")
    need(type(plan.get("source_server_identity")) is str
         and plan["source_server_identity"] not in ("", "UNKNOWN"),
         "FRESH_SOURCE_IDENTITY_UNVERIFIED")
    return sorted(names), sorted(db_sites)


def clean_target(plan: dict[str, Any]) -> dict[str, Any]:
    """No target site or former migration; neither inventory nor state is altered."""
    need(os.geteuid() == 0, "FRESH_CP2_ROOT_REQUIRED")
    state = pull.STATE_ROOT
    if os.path.lexists(state):
        need(not state.is_symlink() and state.is_dir(),
             "FRESH_CP2_MIGRATION_STATE_ROOT_UNSAFE")
        need(not any(state.iterdir()), "FRESH_CP2_OLD_MIGRATION_STATE_PRESENT")
    target = pull.target_preflight_local(plan)
    need(type(target) is dict and target.get("status") == "READY"
         and target.get("target_identity")
         != plan.get("source_server_identity"),
         "FRESH_CP2_SOURCE_TARGET_IDENTITY_CONFLICT")
    current = pull.inventory.build_manifest(Path("/"))
    sites = current.get("sites") if isinstance(current, dict) else None
    need(type(sites) is list and not sites,
         "FRESH_CP2_EXISTING_SITES_PRESENT")
    return target


def screen_source_databases(source: dict[str, Any],
                            db_sites: list[tuple[str, str]]) -> int:
    """Pre-screen all DB dumps before target import/site creation.

    Exported SQL is transient in an owned old-VPS probe directory and a private
    local TemporaryDirectory. Any error is a hard stop. No SQL is imported.
    Source can continue writing, so this NEVER proves final row parity.
    """
    token = "probe-" + os.urandom(16).hex()
    runtime = f"/var/lib/vf-server-ops/pull-source/{token}/runtime"
    root = str(Path(runtime).parent)
    staged = False
    cleanup_verified = False
    try:
        staged = True  # attempt cleanup even if staging partially failed
        pull.stage_source_runtime(source, token)
        with tempfile.TemporaryDirectory(prefix="p07-fresh-sql-") as location:
            os.chmod(location, 0o700)
            for domain, db in db_sites:
                tag = hashlib.sha256((domain + ":" + db).encode()).hexdigest()[:20]
                remote = f"{root}/sql/{tag}.sql.gz"
                local = Path(location) / f"{tag}.sql.gz"
                info = {"source": source, "source_runtime_path": runtime}
                pull.source_export_database(info, db, remote)
                pull.pull_path(source, remote, local)
                need(not local.is_symlink() and local.is_file(),
                     "FRESH_SOURCE_SQL_COPY_UNAVAILABLE")
                # Use existing guarded verifiers; never silently sanitize SQL.
                try:
                    pull.sql_diff_probe.require_nonempty_source_schema(local)
                    pull.sql_diff_probe.require_source_import_utf8_integrity(local)
                    counts = pull.sql_diff_probe.dynamic_guard_syntax_counts(local)
                    risky = any(counts.get(k, 0) for k in (
                        "recognized_unsafe", "double_quoted_if", "other_unknown_set"
                    ))
                    need(not risky and not pull.verify_engine.sql_unproven_side_effects(local),
                         "FRESH_SOURCE_SQL_UNPROVEN_SIDE_EFFECTS")
                except pull.sql_diff_probe.AdvisoryDiagnosticUnavailable:
                    raise FreshBlocked("FRESH_SOURCE_SQL_ENCODING_OR_SCHEMA_UNPROVEN") from None
                except pull.verify_engine.RestoreVerifyError:
                    raise FreshBlocked("FRESH_SOURCE_SQL_EFFECTS_UNVERIFIED") from None
        return len(db_sites)
    finally:
        if staged:
            try:
                pull.cleanup_probe_runtime(source, runtime)
                response = pull.source_remote(
                    source, f"test ! -e {pull.shlex.quote(root)} && test ! -L {pull.shlex.quote(root)}",
                    timeout=30, check=False)
                cleanup_verified = response.returncode == 0
            except Exception:
                cleanup_verified = False
            if not cleanup_verified:
                # A live source-temp residue needs supervised recovery,
                # never an untracked blind retry.
                raise FreshBlocked("FRESH_SOURCE_TEMP_CLEANUP_UNVERIFIED") from None


def run(mode: str, source: dict[str, Any], confirmation: str) -> dict[str, Any]:
    need(mode in {"preview", "prepare"}, "FRESH_MODE_INVALID")
    need(confirmation == (CONFIRM_PREVIEW if mode == "preview" else CONFIRM_PREPARE),
         "FRESH_EXPLICIT_CONFIRMATION_REQUIRED")
    need(os.geteuid() == 0, "FRESH_CP2_ROOT_REQUIRED")
    # A temporary helper is staged on SOURCE only after explicit confirmation.
    plan = pull.source_probe(source, [])
    domains, db_sites = inventory_scope(plan)
    target = clean_target(plan)
    checked = screen_source_databases(source, db_sites)
    report = {
        "schema": SCHEMA,
        "status": "PREFLIGHT_PASS_NOT_CUTOVER_READY",
        "source_site_count": 17,
        "source_domains": domains,  # human-visible domains, no private paths
        "source_db_count": checked,
        "target_empty_verified": True,
        "source_inventory_sha256": hashlib.sha256("\n".join(domains).encode()).hexdigest(),
        "source_live_writes_fenced": False,
        "source_final_data_parity_verified": False,
        "dns_changed": False,
        "old_source_deleted": False,
        "cutover_allowed": False,
    }
    if mode == "preview":
        return report
    # Normal existing P07 guarded first-copy engine remains the ONLY writer.
    # It performs its own repeated probe and target preflight and can still
    # fail if the continuously running source changes in the meantime.
    result = pull.prepare_migration(source, domains, "PREPARE_PULL_MIGRATION")
    return {
        "schema": SCHEMA,
        "status": "FRESH_FIRST_COPY_COMPLETED_NOT_CUTOVER_READY"
                  if result.get("status") == "PREPARED" else "FRESH_FIRST_COPY_NOT_PREPARED",
        "site_count": len(result.get("sites", [])),
        "source_db_preflight_count": checked,
        "cutover_allowed": False,
        "dns_changed": False,
        "old_source_deleted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fresh CP2 17-site first-copy; no cutover")
    parser.add_argument("mode", choices=("preview", "prepare"))
    parser.add_argument("--source-ip", required=True)
    parser.add_argument("--source-host")
    parser.add_argument("--ssh-user", default="root")
    parser.add_argument("--ssh-port", type=int, default=22)
    parser.add_argument("--identity-file")
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()
    # No custom SSH executable or --managed-identity-file; preserve owner keys.
    args.managed_identity_file = False
    args.ssh = "ssh"
    try:
        source = pull.source_from_args(args)
        result = run(args.mode, source, args.confirm)
    except (FreshBlocked, pull.PullMigrationError, OSError) as exc:
        # No exception text can contain SQL, host IP or SSH key paths.
        label = str(exc) if type(exc) is FreshBlocked else "FRESH_SOURCE_OR_CP2_OPERATION_FAILED"
        print(json.dumps({"status": "BLOCKED", "reason": label,
                          "cutover_allowed": False}, sort_keys=True))
        return 13
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
