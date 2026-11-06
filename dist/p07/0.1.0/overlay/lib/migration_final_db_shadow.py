"""P07 final MySQL shadow database creation (stage only; never activates).

A frozen SOURCE dump may be restored into a brand-new, uniquely named
CloudPanel database, while the original target database and app mapping stay
unchanged. No existing database is ever retried, reset, dropped or overwritten.

This module deliberately has NO cutover CLI and NO application-config switch.
A separately tested transactional activation/rollback and consolidated 17-site
final verification must exist before the existing cutover hard stop is lifted.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path
import tempfile
from typing import Any

import app_config
import cloudpanel
import server_migration as legacy
import site_lifecycle
import sql_diff_evidence
import verify


class ShadowBlocked(RuntimeError):
    """Only sanitized fixed-code failures leave this module."""


def _block(reason: str) -> None:
    raise ShadowBlocked(reason)


def original_database_owner(state: dict[str, Any], site: dict[str, Any]) -> str:
    """Return the original import task, not the new consolidated transaction.

    A parent/child/tail recovery can contain DBs owned by three different
    private target-transaction namespaces. Never silently assume the new 17-site
    migration id owns an existing database. An explicit owner map must be
    exhaustive for all DB-bearing domains and every referenced marker must
    independently prove its own ownership when read.
    """
    current = str(state.get("migration_id") or "")
    if not legacy.SAFE_ID_RE.fullmatch(current):
        _block("SHADOW_MIGRATION_ID_INVALID")
    site_domain = str(site.get("domain") or "")
    mapping = state.get("original_db_migration_owners")
    if mapping is None:
        return current
    inventory = state.get("sites")
    if not isinstance(inventory, list) or not isinstance(mapping, dict):
        _block("SHADOW_ORIGINAL_DB_OWNER_MAP_UNVERIFIED")
    expected = set()
    for row in inventory:
        if not isinstance(row, dict) or not isinstance(row.get("mysql_databases"), list):
            _block("SHADOW_ORIGINAL_DB_OWNER_MAP_UNVERIFIED")
        dbs = row["mysql_databases"]
        if len(dbs) > 1:
            _block("SHADOW_ORIGINAL_DB_OWNER_MAP_UNVERIFIED")
        if dbs:
            domain = str(row.get("domain") or "")
            if not domain or domain in expected:
                _block("SHADOW_ORIGINAL_DB_OWNER_MAP_UNVERIFIED")
            expected.add(domain)
    if set(mapping) != expected or site_domain not in expected:
        _block("SHADOW_ORIGINAL_DB_OWNER_MAP_UNVERIFIED")
    for domain, mid in mapping.items():
        if (
            not isinstance(domain, str) or not isinstance(mid, str)
            or not legacy.SAFE_ID_RE.fullmatch(mid)
        ):
            _block("SHADOW_ORIGINAL_DB_OWNER_MAP_UNVERIFIED")
    return mapping[site_domain]


def shadow_identity(state: dict[str, Any], site: dict[str, Any], *, index: int = 1) -> tuple[str, str]:
    """A new distinct CloudPanel DB identity; nothing is created."""
    mid = str(state.get("migration_id", ""))
    if not legacy.SAFE_ID_RE.fullmatch(mid):
        _block("SHADOW_MIGRATION_ID_INVALID")
    domain = cloudpanel.validate_domain(str(site.get("domain") or ""))
    dbs = site.get("mysql_databases")
    if not isinstance(dbs, list) or len(dbs) != 1 or index != 1:
        _block("SHADOW_REQUIRES_SINGLE_DATABASE_SITE")
    original = cloudpanel.validate_name(str(dbs[0]), "database")
    shadow, _user, _pass = site_lifecycle.derive_database_identity(
        domain, mid + ":final-shadow", index
    )
    if shadow == original:
        _block("SHADOW_IDENTITY_COLLISION")
    inventory = state.get("sites")
    if not isinstance(inventory, list) or site not in inventory:
        _block("SHADOW_SITE_NOT_IN_MIGRATION")
    for item in inventory:
        if not isinstance(item, dict) or not isinstance(item.get("mysql_databases"), list):
            _block("SHADOW_INVENTORY_UNVERIFIED")
        if shadow in item["mysql_databases"]:
            _block("SHADOW_IDENTITY_COLLISION")
    return original, shadow


def _marker(state: dict[str, Any], site: dict[str, Any], shadow: str) -> Path:
    mid = str(state["migration_id"])
    domain = str(site["domain"])
    token = hashlib.sha256(f"{mid}:{domain}:{shadow}:final".encode()).hexdigest()[:20]
    return legacy.target_tx_root(mid) / f"final-shadow-{token}.json"


_SHADOW_SCOPE_ESCAPE_HEAD_RE = re.compile(
    r"^(?:USE\b|SOURCE\b|DELIMITER\b|\\[.]\s+|"
    r"(?:CREATE|ALTER|DROP)\s+(?:DATABASE|SCHEMA|SERVER|USER|ROLE|"
    r"TRIGGER|EVENT|PROCEDURE|FUNCTION)\b|RENAME\s+TABLE\b|"
    r"(?:LOCK|UNLOCK)\s+TABLES\b|"
    r"(?:CREATE|ALTER|DROP|TRUNCATE)\s+TABLE\s+"
    r"(?:IF\s+(?:NOT\s+)?EXISTS\s+)?"
    r"(?:\x60?[A-Za-z_][A-Za-z_0-9-]*\x60?\.)|"
    r"(?:INSERT|REPLACE)\s+INTO\s+"
    r"(?:\x60?[A-Za-z_][A-Za-z_0-9-]*\x60?\.)"
    r")", re.I,
)
_SHADOW_VERSIONED_PREFIX_RE = re.compile(r"^/\*(?:!|M!)[0-9]{5,6}\s+", re.I)


def _reject_cross_database_import_commands(path: Path) -> None:
    """Disallow SQL that could escape a fresh shadow DB on actual import.

    Exact data equivalence does not authorize executing CREATE DATABASE, USE,
    DEFINER routines, triggers, global privileges or qualified destructive
    DDL against a live CloudPanel engine. These require separate isolation
    proof, rather than a direct target server import.
    """
    opener = __import__("gzip").open if path.name.endswith(".gz") else open
    try:
        with opener(path, "rt", encoding="utf-8", errors="strict") as stream:
            for raw in stream:
                line = raw.strip()
                if not line or line.startswith(("--", "#")):
                    continue
                line = _SHADOW_VERSIONED_PREFIX_RE.sub("", line)
                if _SHADOW_SCOPE_ESCAPE_HEAD_RE.match(line):
                    _block("SHADOW_SQL_CROSS_DATABASE_SCOPE_UNPROVEN")
    except (OSError, UnicodeError, EOFError):
        _block("SHADOW_SOURCE_SQL_UNREADABLE")


def _preflight(
    state: dict[str, Any], site: dict[str, Any], source_dump: Path,
    actual_target_identity: str,
) -> tuple[str, str, dict[str, Any], Path]:
    original, shadow = shadow_identity(state, site)
    if (
        state.get("status") != "CUTOVER_RUNNING"
        or state.get("source_runtime_frozen") is not True
        or state.get("target_runtime_activated") is True
        or state.get("dns_changed_by_p07") is True
        or state.get("source_delete_allowed") is True
        or state.get("existing_target_overwrite_allowed") is True
        or state.get("cutover_prohibited") is True
        or state.get("partial_parent_migration_id")
    ):
        _block("SHADOW_SOURCE_FREEZE_OR_CUTOVER_BOUNDARY_UNPROVEN")
    if (
        not actual_target_identity
        or actual_target_identity != state.get("target_server_identity")
    ):
        _block("SHADOW_TARGET_IDENTITY_CHANGED")
    site_root = Path(str(site.get("site_root") or ""))
    if site_root.is_symlink() or not site_root.is_dir():
        _block("SHADOW_SITE_ROOT_UNVERIFIED")
    mid = str(state["migration_id"])
    # A source dump outside this migration's own private state tree may be an
    # unrelated database. Never import it into a newly created shadow DB.
    expected_root = legacy.state_dir(mid).resolve()
    try:
        if (
            source_dump.is_symlink()
            or not source_dump.is_file()
            or not source_dump.resolve().is_relative_to(expected_root)
        ):
            _block("SHADOW_SOURCE_DUMP_UNOWNED")
    except (OSError, ValueError):
        _block("SHADOW_SOURCE_DUMP_UNOWNED")
    origin_mid = original_database_owner(state, site)
    original_marker = legacy.target_db_marker(origin_mid, str(site["domain"]), original, 1)
    try:
        owned = legacy.read_target_ownership_marker(
            original_marker,
            {"domain": str(site["domain"]), "database": original,
             "created_by_migration": origin_mid},
        )
    except legacy.ServerMigrationError:
        _block("SHADOW_ORIGINAL_DATABASE_MARKER_UNSAFE")
    if not isinstance(owned, dict):
        _block("SHADOW_ORIGINAL_DATABASE_UNOWNED")
    username, password = owned.get("username"), owned.get("password")
    if not isinstance(username, str) or not isinstance(password, str) or not username or not password:
        _block("SHADOW_ORIGINAL_DATABASE_CREDENTIALS_UNPROVEN")
    if not app_config.verify_rewritten_application_database_config(
        site_root, original, username, password
    ):
        _block("SHADOW_APPLICATION_MAPPING_CHANGED")
    destination_marker = _marker(state, site, shadow)
    if os.path.lexists(destination_marker):
        _block("SHADOW_ALREADY_CREATED_REIMPORT_FORBIDDEN")
    # Validate SQL grammar before creating a database. Previously unproven
    # version-guarded SET/EXECUTE branches must never run with DB privileges.
    try:
        sql_diff_evidence.require_nonempty_source_schema(source_dump)
        _reject_cross_database_import_commands(source_dump)
        counts = sql_diff_evidence.dynamic_guard_syntax_counts(source_dump)
        if verify.sql_unproven_side_effects(source_dump) or any(
            counts.get(name, 0) for name in (
                "recognized_unsafe", "other_unknown_set", "double_quoted_if"
            )
        ):
            _block("SHADOW_SQL_GUARD_UNPROVEN")
    except (sql_diff_evidence.AdvisoryDiagnosticUnavailable, verify.RestoreVerifyError):
        _block("SHADOW_SOURCE_SQL_UNREADABLE")
    return original, shadow, owned, destination_marker


def stage_frozen_source_shadow(
    state: dict[str, Any],
    site: dict[str, Any],
    source_dump: Path,
    *,
    actual_target_identity: str,
) -> dict[str, Any]:
    """Create new isolated DB only; preserve old DB, credentials and site files.

    A failure after CloudPanel db:add leaves a private marker with status
    CREATED or IMPORTED_UNVERIFIED, and requires recovery rather than retry.
    Neither failure nor success changes the active application's mapping.
    """
    original, shadow, original_owned, marker = _preflight(
        state, site, source_dump, actual_target_identity
    )
    mid = str(state["migration_id"])
    domain = str(site["domain"])
    shadow_db, shadow_user, shadow_password = site_lifecycle.derive_database_identity(
        domain, mid + ":final-shadow", 1
    )
    if shadow_db != shadow:
        _block("SHADOW_NAME_DRIFT")
    # Reserve the recovery receipt BEFORE the external CloudPanel create call.
    # A timeout or crash can mean the database exists even when no result was
    # returned. Preserve the intent and refuse automatic retries in that case.
    payload: dict[str, Any] = {
        "schema": "vf-server-ops.final-db-shadow.v1",
        "migration_id": mid, "domain": domain,
        "original_database": original, "shadow_database": shadow,
        "shadow_username": shadow_user, "shadow_password": shadow_password,
        "source_runtime_frozen": True,
        "target_server_identity": actual_target_identity,
        "original_marker_username": original_owned["username"],
        "original_origin_migration_id": original_database_owner(state, site),
        "status": "CREATE_INTENT_RESERVED",
        "active_app_config_unchanged": True, "old_database_retained": True,
    }
    legacy.atomic_private_json(marker, payload)
    try:
        cloudpanel.add_database(domain, shadow, shadow_user, shadow_password)
    except (ValueError, cloudpanel.CloudPanelError, OSError):
        _block("SHADOW_DATABASE_CREATE_UNCERTAIN_RETAIN_INTENT")
    payload["status"] = "CREATED_UNVERIFIED"
    legacy.atomic_private_json(marker, payload)
    # No recovery path may blindly retry this import after an interruption.
    try:
        cloudpanel.import_database(shadow, source_dump)
        payload["status"] = "IMPORTED_UNVERIFIED"
        legacy.atomic_private_json(marker, payload)
        with tempfile.TemporaryDirectory(prefix="vfops-shadow-", dir=legacy.state_dir(mid)) as d:
            readback = Path(d) / "target-shadow.sql.gz"
            cloudpanel.export_database(shadow, readback)
            # Use the exact migration verifier. A structural/row match or an
            # unsafe SQL guard may never be promoted by shadow staging.
            import server_migration_pull
            mode = server_migration_pull.compare_database_dumps(source_dump, readback)
            if not mode:
                _block("SHADOW_SQL_COMPARISON_UNPROVEN")
            # Capture exact target-engine SQL while private readback exists;
            # this is compared against a NEW live export before config switch.
            try:
                actual_digest, actual_lines = verify.sql_fingerprint(readback)
            except verify.RestoreVerifyError:
                _block("SHADOW_READBACK_FINGERPRINT_UNAVAILABLE")
        payload["target_snapshot_sha256"] = actual_digest
        payload["target_snapshot_statement_count"] = actual_lines
        payload["verification_mode"] = mode
        payload["status"] = "STAGED_VERIFIED_NOT_ACTIVATED"
        legacy.atomic_private_json(marker, payload)
        return {
            "status": "STAGED_VERIFIED_NOT_ACTIVATED",
            "shadow_database": shadow,
            "verification_mode": mode,
            "old_database_retained": True,
            "app_config_modified": False,
            "cutover_allowed": False,
        }
    except (ValueError, OSError, cloudpanel.CloudPanelError, ShadowBlocked,
            legacy.ServerMigrationError, Exception) as exc:
        # Never delete the newly created DB. It might contain owner-authored
        # data after an interrupted operation. Keep original and shadow intact.
        _block("SHADOW_IMPORT_OR_VERIFICATION_FAILED")


def _read_verified_shadow(
    state: dict[str, Any], site: dict[str, Any],
    actual_target_identity: str,
) -> tuple[dict[str, Any], Path, dict[str, Any]]:
    """Only one private, original-owned, verified shadow can be activated."""
    original, name = shadow_identity(state, site)
    if (
        not actual_target_identity
        or state.get("target_server_identity") != actual_target_identity
        or state.get("source_runtime_frozen") is not True
        or state.get("target_runtime_activated") is True
        or state.get("dns_changed_by_p07") is True
        or state.get("cutover_prohibited") is True
        or state.get("partial_parent_migration_id")
        or state.get("status") != "CUTOVER_RUNNING"
    ):
        _block("SHADOW_SWITCH_BOUNDARY_UNVERIFIED")
    marker = _marker(state, site, name)
    try:
        if marker.is_symlink() or not marker.is_file():
            _block("SHADOW_VERIFIED_MARKER_MISSING")
        receipt = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        _block("SHADOW_VERIFIED_MARKER_UNREADABLE")
    if not isinstance(receipt, dict) or any((
        receipt.get("schema") != "vf-server-ops.final-db-shadow.v1",
        receipt.get("migration_id") != state.get("migration_id"),
        receipt.get("domain") != site.get("domain"),
        receipt.get("original_database") != original,
        receipt.get("original_origin_migration_id") != original_database_owner(state, site),
        receipt.get("shadow_database") != name,
        receipt.get("target_server_identity") != actual_target_identity,
        receipt.get("old_database_retained") is not True,
        not isinstance(receipt.get("verification_mode"), str),
        not isinstance(receipt.get("target_snapshot_sha256"), str),
        not re.fullmatch(r"[0-9a-f]{64}", str(receipt.get("target_snapshot_sha256"))),
        type(receipt.get("target_snapshot_statement_count")) is not int,
        (receipt.get("target_snapshot_statement_count") or 0) < 1,
        not isinstance(receipt.get("shadow_password"), str),
        not isinstance(receipt.get("shadow_username"), str),
    )):
        _block("SHADOW_VERIFIED_RECEIPT_INVALID")
    origin_mid = original_database_owner(state, site)
    owner_marker = legacy.target_db_marker(
        origin_mid, str(site["domain"]), original, 1
    )
    try:
        owned = legacy.read_target_ownership_marker(
            owner_marker,
            {"domain": str(site["domain"]), "database": original,
             "created_by_migration": origin_mid},
        )
    except legacy.ServerMigrationError:
        _block("SHADOW_ORIGINAL_DATABASE_MARKER_UNSAFE")
    if not isinstance(owned, dict) or any((
        not isinstance(owned.get("username"), str),
        not isinstance(owned.get("password"), str),
        receipt.get("original_marker_username") != owned.get("username"),
    )):
        _block("SHADOW_ORIGINAL_DATABASE_MARKER_DRIFT")
    return receipt, marker, owned


def verify_staged_shadow_fresh(
    state: dict[str, Any], site: dict[str, Any],
    *, actual_target_identity: str,
) -> dict[str, Any]:
    """Read back real SQL immediately before app-config switch.

    A verified initial shadow might have changed after import. Bind the
    exact target-engine canonical dump fingerprint to its private receipt.
    Unknown/missing digest, changed database contents, or refused SQL
    grammar must never become a working site.
    """
    receipt, _path, _owned = _read_verified_shadow(
        state, site, actual_target_identity
    )
    if receipt.get("status") != "STAGED_VERIFIED_NOT_ACTIVATED":
        _block("SHADOW_FRESH_READBACK_RECEIPT_NOT_READY")
    mid = str(state["migration_id"])
    try:
        with tempfile.TemporaryDirectory(
            prefix="vfops-final-shadow-read-", dir=legacy.state_dir(mid)
        ) as tmp:
            dumped = Path(tmp) / "target-shadow-current.sql.gz"
            cloudpanel.export_database(str(receipt["shadow_database"]), dumped)
            if verify.sql_unproven_side_effects(dumped):
                _block("SHADOW_FRESH_READBACK_SQL_UNSAFE")
            _reject_cross_database_import_commands(dumped)
            digest, count = verify.sql_fingerprint(dumped)
        if (
            digest != receipt["target_snapshot_sha256"]
            or count != receipt["target_snapshot_statement_count"]
        ):
            _block("SHADOW_FRESH_READBACK_CONTENT_CHANGED")
    except (
        OSError, ValueError, cloudpanel.CloudPanelError,
        verify.RestoreVerifyError, sql_diff_evidence.AdvisoryDiagnosticUnavailable,
    ):
        _block("SHADOW_FRESH_READBACK_UNVERIFIED")
    return {
        "status": "SHADOW_FRESH_READBACK_PASS",
        "original_database_retained": True,
        "cutover_allowed": False,
    }


def _exclusive_application_config(site_root: Path) -> Path:
    """Reject multiple or symlinked configurations instead of guessing precedence."""
    if site_root.is_symlink() or not site_root.is_dir():
        _block("SHADOW_APP_ROOT_UNVERIFIED")
    wordpress = (site_root / "wp-config.php", site_root / "public" / "wp-config.php")
    envs = tuple(site_root / name for name in app_config.ENV_NAMES) + tuple(
        site_root / "public" / name for name in app_config.ENV_NAMES
    )
    if any(path.is_symlink() for path in wordpress + envs):
        _block("SHADOW_APP_CONFIG_SYMLINK")
    existing_wp = [path for path in wordpress if path.is_file()]
    existing_env = [path for path in envs if path.is_file()]
    if len(existing_wp) + len(existing_env) != 1:
        _block("SHADOW_APP_CONFIG_AMBIGUOUS")
    selected = (existing_wp + existing_env)[0]
    try:
        if selected.stat().st_size > 1024 * 1024:
            _block("SHADOW_APP_CONFIG_UNBOUNDED")
    except OSError:
        _block("SHADOW_APP_CONFIG_UNREADABLE")
    return selected


def _atomic_restore_config(
    path: Path, backup: Path, expected_hash: str,
    expected_owner: dict[str, int],
) -> None:
    """Restore only the private exact-original backup, never a guessed value."""
    try:
        if backup.is_symlink() or not backup.is_file() or path.is_symlink():
            _block("SHADOW_CONFIG_BACKUP_UNSAFE")
        data = backup.read_bytes()
        if hashlib.sha256(data).hexdigest() != expected_hash:
            _block("SHADOW_CONFIG_BACKUP_DRIFT")
        if not isinstance(expected_owner, dict):
            _block("SHADOW_CONFIG_BACKUP_OWNERSHIP_UNVERIFIED")
        uid, gid, mode = (expected_owner.get(key) for key in ("uid", "gid", "mode"))
        if any(type(value) is not int or value < 0 for value in (uid, gid, mode)) or mode > 0o777:
            _block("SHADOW_CONFIG_BACKUP_OWNERSHIP_UNVERIFIED")
        fd, temporary = tempfile.mkstemp(prefix=".vfops-shadow-restore-", dir=path.parent)
        temp = Path(temporary)
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            os.chmod(temp, mode)
            os.chown(temp, uid, gid)
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)
    except (OSError, ValueError) as exc:
        _block("SHADOW_CONFIG_RESTORE_FAILED")


def _restore_app_from_receipt(
    state: dict[str, Any], site: dict[str, Any],
    receipt: dict[str, Any], marker: Path, old_owned: dict[str, Any],
) -> None:
    site_root = Path(str(site["site_root"]))
    config = _exclusive_application_config(site_root)
    backup = marker.with_suffix(".original.bak")
    try:
        relative = config.relative_to(site_root).as_posix()
    except ValueError:
        _block("SHADOW_CONFIG_PATH_OUTSIDE_SITE")
    if receipt.get("config_relative_path") != relative:
        _block("SHADOW_CONFIG_PATH_DRIFT")
    old = app_config.verify_rewritten_application_database_config(
        site_root, receipt["original_database"],
        old_owned["username"], old_owned["password"],
    )
    new = app_config.verify_rewritten_application_database_config(
        site_root, receipt["shadow_database"],
        receipt["shadow_username"], receipt["shadow_password"],
    )
    if not old and not new:
        _block("SHADOW_CONFIG_OWNER_CHANGED_NO_OVERWRITE")
    if new:
        _atomic_restore_config(
            config, backup, str(receipt.get("original_config_sha256") or ""),
            receipt.get("original_config_owner"),
        )
    if not app_config.verify_rewritten_application_database_config(
        site_root, receipt["original_database"],
        old_owned["username"], old_owned["password"],
    ):
        _block("SHADOW_CONFIG_ROLLBACK_UNVERIFIED")
    receipt["status"] = "APP_SWITCH_ROLLED_BACK"
    receipt["active_app_config_unchanged"] = True
    legacy.atomic_private_json(marker, receipt)


def activate_verified_shadow(
    state: dict[str, Any], site: dict[str, Any],
    *, actual_target_identity: str,
) -> dict[str, Any]:
    """Reversible site-config switch, strictly before TARGET runtime/DNS.

    This is a library primitive, NOT attached to cutover/CLI. It must not
    activate a production site until full end-to-end recovery gates exist.
    """
    receipt, marker, owned = _read_verified_shadow(
        state, site, actual_target_identity
    )
    if receipt.get("status") != "STAGED_VERIFIED_NOT_ACTIVATED":
        _block("SHADOW_SWITCH_RECEIPT_NOT_READY")
    root = Path(str(site["site_root"]))
    config = _exclusive_application_config(root)
    if not app_config.verify_rewritten_application_database_config(
        root, receipt["original_database"], owned["username"], owned["password"]
    ):
        _block("SHADOW_ORIGINAL_CONFIG_CHANGED")
    # The shadow must still contain the precise SQL verified at staging;
    # never trust a stale receipt during a config switch.
    verify_staged_shadow_fresh(
        state, site, actual_target_identity=actual_target_identity
    )
    backup = marker.with_suffix(".original.bak")
    if os.path.lexists(backup):
        _block("SHADOW_CONFIG_BACKUP_ALREADY_EXISTS")
    try:
        original = config.read_bytes()
        original_hash = hashlib.sha256(original).hexdigest()
        fd, tmp_name = tempfile.mkstemp(
            prefix=".vfops-shadow-config-", dir=backup.parent
        )
        temporary = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(original)
                output.flush()
                os.fsync(output.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, backup)
        finally:
            temporary.unlink(missing_ok=True)
        old_stat = config.stat()
        receipt["config_relative_path"] = config.relative_to(root).as_posix()
        receipt["original_config_sha256"] = original_hash
        receipt["original_config_owner"] = {
            "uid": old_stat.st_uid, "gid": old_stat.st_gid,
            "mode": stat.S_IMODE(old_stat.st_mode),
        }
        receipt["status"] = "APP_SWITCH_PENDING"
        legacy.atomic_private_json(marker, receipt)
        app_config.rewrite_application_database_config(
            root, str(site["domain"]), str(site["domain"]),
            receipt["shadow_database"], receipt["shadow_username"],
            receipt["shadow_password"],
        )
        # WordPress/.env rewrites use an atomic temporary file. Reattach
        # the original site-owner identity before any web runtime could read
        # a root-owned 0600 config; a failure must roll back.
        os.chown(config, old_stat.st_uid, old_stat.st_gid, follow_symlinks=False)
        if not app_config.verify_rewritten_application_database_config(
            root, receipt["shadow_database"], receipt["shadow_username"],
            receipt["shadow_password"]
        ):
            _block("SHADOW_SWITCH_CONFIG_UNVERIFIED")
        receipt["status"] = "APP_SWITCH_VERIFIED_NOT_ACTIVATED"
        receipt["active_app_config_unchanged"] = False
        legacy.atomic_private_json(marker, receipt)
        return {
            "status": receipt["status"], "old_database_retained": True,
            "cutover_allowed": False, "rollback_backup_retained": True,
        }
    except Exception:
        # Never proceed after an incomplete switch. If rollback fails, the
        # PENDING marker + private backup remain for explicit recovery.
        try:
            if receipt.get("status") in (
                "APP_SWITCH_PENDING", "APP_SWITCH_VERIFIED_NOT_ACTIVATED"
            ):
                _restore_app_from_receipt(state, site, receipt, marker, owned)
        except Exception:
            _block("SHADOW_SWITCH_PARTIAL_ROLLBACK_REQUIRED")
        _block("SHADOW_SWITCH_FAILED_ROLLED_BACK")


def rollback_shadow_application(
    state: dict[str, Any], site: dict[str, Any],
    *, actual_target_identity: str,
) -> dict[str, Any]:
    """Return app mapping to original without deleting either database."""
    receipt, marker, owned = _read_verified_shadow(
        state, site, actual_target_identity
    )
    if receipt.get("status") not in (
        "APP_SWITCH_PENDING", "APP_SWITCH_VERIFIED_NOT_ACTIVATED",
        "APP_SWITCH_ROLLED_BACK",
    ):
        _block("SHADOW_ROLLBACK_NOT_REQUIRED")
    _restore_app_from_receipt(state, site, receipt, marker, owned)
    return {
        "status": "APP_SWITCH_ROLLED_BACK", "old_database_retained": True,
        "shadow_database_retained": True, "cutover_allowed": False,
    }
