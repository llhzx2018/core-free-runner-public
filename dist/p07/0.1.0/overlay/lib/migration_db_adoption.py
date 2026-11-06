"""P07 read-only re-adoption evidence for already imported databases.

The original TARGET database is NEVER imported, renamed, dropped or reconfigured.
The receipt is only a local first-stage consistency checkpoint, not an
authorization to resume a site, freeze SOURCE, swap DBs or change DNS.
"""
from __future__ import annotations
import re
from typing import Any, Mapping

VALID_MODES = frozenset({
    "CANONICAL_SQL_EXACT",
    "CROSS_ENGINE_GUARDED_SESSION_SQL_EXACT",
    "CROSS_ENGINE_KNOWN_DUMP_FORMAT_SQL_EXACT",
    "CROSS_ENGINE_LOGICAL_CONTENT",
})
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class AdoptBlocked(ValueError):
    pass


def selected_db(state: Mapping[str, Any], domain: str) -> str:
    if not isinstance(state, dict) or state.get("status") != "PREPARE_FAILED":
        raise AdoptBlocked("ADOPT_FAILED_MIGRATION_REQUIRED")
    guard = state.get("last_sql_guard_failure")
    if not isinstance(guard, dict) or guard.get("reason") != "CONDITIONAL_DDL":
        raise AdoptBlocked("ADOPT_ORIGINAL_SQL_GUARD_REQUIRED")
    if not all(state.get(key) is False for key in (
        "source_runtime_frozen", "target_runtime_activated",
        "dns_changed_by_p07", "source_delete_allowed",
        "existing_target_overwrite_allowed",
    )):
        raise AdoptBlocked("ADOPT_UNSAFE_MIGRATION_BOUNDARY")
    rows = [r for r in state.get("sites", [])
            if isinstance(r, dict) and r.get("domain") == domain]
    if len(rows) != 1 or rows[0].get("stage_status") != "PENDING":
        raise AdoptBlocked("ADOPT_PENDING_SITE_REQUIRED")
    dbs = rows[0].get("mysql_databases")
    if not isinstance(dbs, list) or len(dbs) != 1 or not isinstance(dbs[0], str) or not dbs[0]:
        raise AdoptBlocked("ADOPT_SINGLE_EXISTING_DATABASE_REQUIRED")
    return dbs[0]


def validated_one(item: Mapping[str, Any]) -> dict[str, str]:
    if not isinstance(item, dict) or item.get("comparison_mode") not in VALID_MODES:
        raise AdoptBlocked("ADOPT_SQL_SEMANTIC_PROOF_MISSING")
    if item.get("source_readback_mode") not in VALID_MODES:
        raise AdoptBlocked("ADOPT_SOURCE_STABILITY_UNPROVEN")
    for key in ("source_dump_sha256", "target_dump_sha256",
                "source_readback_sha256", "source_snapshot_fingerprint",
                "readback_snapshot_fingerprint"):
        if not isinstance(item.get(key), str) or not SHA256.fullmatch(item[key]):
            raise AdoptBlocked("ADOPT_SQL_DIGEST_MISSING")
    if item["source_snapshot_fingerprint"] != item["readback_snapshot_fingerprint"]:
        raise AdoptBlocked("ADOPT_SOURCE_EXPORT_CHANGED")
    if not all(isinstance(item.get(k), str) and item[k]
               for k in ("domain", "migration_id", "database")):
        raise AdoptBlocked("ADOPT_DB_IDENTITY_MISSING")
    return {key: item[key] for key in (
        "domain", "migration_id", "database", "comparison_mode",
        "source_readback_mode", "source_dump_sha256", "target_dump_sha256",
        "source_readback_sha256", "source_snapshot_fingerprint",
        "readback_snapshot_fingerprint",
    )}


def sealed_receipt(site_rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    if not isinstance(site_rows, list) or len(site_rows) != 2:
        raise AdoptBlocked("ADOPT_TWO_BOUND_SITE_PROOFS_REQUIRED")
    output = [validated_one(v) for v in site_rows]
    if len({v["domain"] for v in output}) != 2:
        raise AdoptBlocked("ADOPT_TWO_DISTINCT_SITES_REQUIRED")
    return {
        "schema": "P07_TWO_BLOCKED_DATABASE_REUSE_PROOF_V1",
        "status": "PREPARE_READBACK_MATCH_NOT_RESUMED",
        "database_imports": 0,
        "database_overwrites": 0,
        "migration_state_writes": 0,
        "existing_target_preserved": True,
        "cutover_allowed": False,
        "partial_child_cutover_allowed": False,
        "source_freeze_allowed": False,
        "site_stage_promoted": False,
        "snapshot_is_atomic_across_servers": False,
        "sites": output,
    }


def stage_existing_verified_site(
    state: dict[str, Any], domain: str, proof: Mapping[str, Any]
) -> dict[str, Any]:
    """Produce a NEW state with one proven existing DB staged; never imports.

    Caller must commit this with a before/after identity lock and must not
    clear the original SQL failure, permit cutover, or mistake this initial
    copy's readback for a final consistency snapshot.
    """
    import copy
    database = selected_db(state, domain)
    verified = validated_one(proof)
    if (verified["domain"] != domain
            or verified["migration_id"] != state.get("migration_id")
            or verified["database"] != database):
        raise AdoptBlocked("ADOPT_VERIFIED_RECORD_IDENTITY_MISMATCH")
    result = copy.deepcopy(state)
    site = next(row for row in result["sites"] if row.get("domain") == domain)
    prior = site.get("mysql_verification")
    if prior is not None and not isinstance(prior, list):
        raise AdoptBlocked("ADOPT_PRIOR_SQL_VERIFICATION_INVALID")
    site["mysql_verification"] = [
        v for v in (prior or [])
        if isinstance(v, dict) and not (
            v.get("database") == database and v.get("phase") == "prepare"
        )
    ] + [{
        "database": database, "phase": "prepare", "status": "PASS",
        "mode": verified["comparison_mode"],
        "config_mode": "PREEXISTING_OWNED_DB_NO_REIMPORT",
        "config_file": None,
        "recovered_from_failed_guard": True,
        "source_export_stability_checked": True,
        "not_final_cutover_evidence": True,
    }]
    site["mysql_prepare_count"] = 1
    site["stage_status"] = "PULLED_STAGED"
    site["database_adoption"] = {
        "schema": "P07_EXISTING_DB_ADOPTION_CHECKPOINT_V1",
        "status": "SOURCE_TARGET_PREPARE_READBACK_PASS",
        "source_snapshot_fingerprint": verified["source_snapshot_fingerprint"],
        "target_dump_sha256": verified["target_dump_sha256"],
        "snapshot_is_atomic_across_servers": False,
        "cutover_allowed": False,
        "db_reimported": False,
    }
    return result
