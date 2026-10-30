"""Private, one-shot two-sided backup/SQL readiness evidence.

This module NEVER imports SQL, starts a database, modifies migration state,
accepts user-supplied PASS claims, or authorizes recovery/cutover. Only fixed
reason codes, integer counts and table ordinals leave the process. Raw SQL,
database names, backup paths, hashes, identities and metadata stay private.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import stat
from typing import Any

import migration_conflict_recovery
import package_core
import sql_diff_evidence


SCHEMA = "P07_PRIVATE_TWO_SIDED_RECOVERY_GATE_V1"


class RecoveryBlocked(ValueError):
    """Fixed reason code only; never pass input or exception message through."""


def _input_package(path: Path, expected_site: str) -> tuple[dict[str, Any], Path]:
    if not path.is_dir() or path.is_symlink():
        raise RecoveryBlocked("PRIVATE_PACKAGE_DIRECTORY_UNAVAILABLE")
    try:
        result = package_core.verify_package_stable(path)
    except Exception:
        raise RecoveryBlocked("PRIVATE_BACKUP_VERIFICATION_UNAVAILABLE") from None
    if result.get("status") != "PASS":
        raise RecoveryBlocked("PRIVATE_BACKUP_INTEGRITY_NOT_PASS")
    try:
        manifest_path = path / "manifest.json"
        if manifest_path.is_symlink() or not manifest_path.is_file():
            raise RecoveryBlocked("PRIVATE_MANIFEST_UNSAFE")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (type(manifest) is not dict
                or manifest.get("schema") != package_core.PACKAGE_SCHEMA
                or manifest.get("backup_kind") != "pre_migration"
                or not isinstance(manifest.get("backup_id"), str)
                or not manifest["backup_id"]
                or (manifest.get("site") or {}).get("domain") != expected_site):
            raise RecoveryBlocked("PRIVATE_PACKAGE_IDENTITY_NOT_PROVEN")
        contents = manifest.get("contents") or {}
        entries = contents.get("mysql")
        if not isinstance(entries, list) or len(entries) != 1:
            raise RecoveryBlocked("PRIVATE_SINGLE_DATABASE_REQUIRED")
        entry = entries[0]
        if not isinstance(entry, dict) or not isinstance(entry.get("file"), str):
            raise RecoveryBlocked("PRIVATE_SQL_MANIFEST_INVALID")
        rel = PurePosixPath(entry["file"])
        if (rel.is_absolute() or ".." in rel.parts or not rel.parts
                or rel.parts[0] != "mysql" or not rel.name.endswith(".sql.gz")):
            raise RecoveryBlocked("PRIVATE_SQL_PATH_UNSAFE")
        raw = path / Path(*rel.parts)
        root = path.resolve(strict=True)
        resolved = raw.resolve(strict=True)
        if not (resolved != root and root in resolved.parents):
            raise RecoveryBlocked("PRIVATE_SQL_PATH_UNSAFE")
        if any((path / Path(*rel.parts[:i])).is_symlink()
               for i in range(1, len(rel.parts) + 1)):
            raise RecoveryBlocked("PRIVATE_SQL_SYMLINK_REFUSED")
        info = resolved.stat()
        if not stat.S_ISREG(info.st_mode) or not info.st_size or info.st_nlink != 1:
            raise RecoveryBlocked("PRIVATE_SQL_FILE_UNSAFE")
        return manifest, resolved
    except RecoveryBlocked:
        raise
    except (OSError, UnicodeError, ValueError, TypeError, AttributeError):
        raise RecoveryBlocked("PRIVATE_PACKAGE_UNREADABLE") from None


def _result(status: str, reason: str, **evidence: Any) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "status": status,
        "reason": reason,
        "source_backup_integrity": evidence.pop("source_backup_integrity", "UNKNOWN"),
        "target_backup_integrity": evidence.pop("target_backup_integrity", "UNKNOWN"),
        "actual_source_restore_verified": False,
        "actual_target_restore_verified": False,
        "source_target_snapshot_consistency": "NOT_ESTABLISHED",
        "dynamic_sql_approved": False,
        "data_writes_performed": False,
        "migration_state_modified": False,
        "migration_resume_allowed": False,
        "cutover_allowed": False,
        "verification": "NOT_A_PASS_GATE",
        **evidence,
    }


def evaluate(source_package: Path, target_package: Path, site: str) -> dict[str, Any]:
    """Validate offline backup provenance and advisory SQL counts, fail closed.

    The two verified packages may be taken at different times and different
    database engines. SQL literal parity is not data semantics or restore proof.
    """
    try:
        if not isinstance(site, str) or not site or "/" in site or "\\" in site:
            raise RecoveryBlocked("EXPECTED_SITE_INVALID")
        if source_package.resolve(strict=True) == target_package.resolve(strict=True):
            raise RecoveryBlocked("TWO_INDEPENDENT_BACKUP_POINTS_REQUIRED")
        src, a = _input_package(source_package, site)
        tgt, b = _input_package(target_package, site)
        if src["backup_id"] == tgt["backup_id"]:
            raise RecoveryBlocked("TWO_DISTINCT_BACKUP_IDENTITIES_REQUIRED")
        result = sql_diff_evidence.diagnostic(a, b)
        if result.get("verification") != "NOT_A_PASS_GATE":
            raise RecoveryBlocked("SQL_ADVISORY_EVIDENCE_UNAVAILABLE")
        pk = result.get("pk_conflicts") or {}
        schema = result.get("schema_difference") or {}
        guard = result.get("dynamic_guard") or {}
        if (pk.get("comparison") not in {"PK_LITERAL_DIFFER", "PK_LITERAL_EQUAL_NOT_VERIFIED"}
                or type(pk.get("tables_examined")) is not int
                or pk["tables_examined"] < 1):
            raise RecoveryBlocked("PRIVATE_SQL_PK_COVERAGE_UNPROVEN")
        work = migration_conflict_recovery.draft({
            "status": "ADVISORY_DIAGNOSTIC_ONLY",
            "database_writes_performed": False,
            "migration_state_modified": False,
            "evidence": result,
        })
        keys = ("source_only_keys", "target_only_keys",
                "same_key_changed_literals", "identical_key_identical_literals")
        summary = {key: pk.get(key) for key in keys}
        integers = (
            schema.get("source_tables"), schema.get("target_tables"),
            schema.get("common_tables"), schema.get("mismatched_tables"),
            pk.get("pk_tables_evaluable"), pk.get("pk_tables_unavailable"),
            pk.get("tables_examined"), guard.get("recognized_unsafe"),
            *summary.values(),
        )
        if any(type(v) is not int or v < 0 or v > 10_000_000 for v in integers):
            raise RecoveryBlocked("PRIVATE_SQL_COUNTERS_UNPROVEN")
        if (schema["source_tables"] != pk["tables_examined"]
                or schema["common_tables"] > min(schema["source_tables"],
                                                  schema["target_tables"])):
            raise RecoveryBlocked("PRIVATE_SQL_TABLE_COUNTS_INCONSISTENT")
        ordinals = pk.get("differing_table_ordinals")
        if not isinstance(ordinals, list) or len(ordinals) > 200:
            raise RecoveryBlocked("PRIVATE_SQL_TABLE_ORDINALS_UNPROVEN")
        fields = ("table_ordinal", "source_only_keys", "target_only_keys",
                  "same_key_changed_literals", "identical_key_identical_literals")
        filtered = []
        seen: set[int] = set()
        for item in ordinals:
            if not isinstance(item, dict) or not all(
                type(item.get(name)) is int and 0 <= item[name] <= 10_000_000
                for name in fields
            ):
                raise RecoveryBlocked("PRIVATE_SQL_TABLE_ORDINALS_UNPROVEN")
            ordinal = item["table_ordinal"]
            if ordinal < 1 or ordinal > pk["tables_examined"] or ordinal in seen:
                raise RecoveryBlocked("PRIVATE_SQL_TABLE_ORDINALS_UNPROVEN")
            seen.add(ordinal)
            filtered.append({name: item[name] for name in fields})
        reasons = guard.get("unsafe_branch_reasons")
        whitelist = (
            "CONTROL_OR_MULTISTATEMENT", "GLOBAL_OR_PERSIST",
            "SIDE_EFFECT_OR_CONTROL_KEYWORD", "SESSION_GRAMMAR_UNPROVEN",
            "READ_GRAMMAR_UNPROVEN", "UNKNOWN_GRAMMAR",
        )
        if not isinstance(reasons, dict) or any(
            type(reasons.get(k)) is not int or not 0 <= reasons[k] <= 10_000_000
            for k in whitelist
        ):
            raise RecoveryBlocked("PRIVATE_SQL_GUARD_COUNTERS_UNPROVEN")
        filtered_reasons = {name: reasons[name] for name in whitelist}
        return _result(
            "BLOCKED_INDEPENDENT_RESTORE_AND_OPERATOR_POLICY",
            "BACKUPS_VERIFIED_SQL_CONFLICTS_UNRESOLVED",
            source_backup_integrity="PASS",
            target_backup_integrity="PASS",
            source_tables=schema.get("source_tables"),
            target_tables=schema.get("target_tables"),
            common_tables=schema.get("common_tables"),
            mismatched_tables=schema.get("mismatched_tables"),
            pk_tables_evaluable=pk.get("pk_tables_evaluable"),
            pk_tables_unavailable=pk.get("pk_tables_unavailable"),
            primary_key_summary=summary,
            conflict_table_ordinals=filtered,
            dynamic_unsafe=guard.get("recognized_unsafe"),
            dynamic_unsafe_branch_reasons=filtered_reasons,
            recovery_review_status=work.get("status"),
            time_consistency="NOT_VERIFIED_DIFFERENT_CAPTURE_POINTS_POSSIBLE",
        )
    except RecoveryBlocked as exc:
        return _result("BLOCKED_UNVERIFIED_INPUT", str(exc))
    except (OSError, ValueError, TypeError):
        return _result("BLOCKED_UNVERIFIED_INPUT", "PRIVATE_RECOVERY_EVIDENCE_UNAVAILABLE")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="R3 private backup recovery evidence; never imports SQL")
    parser.add_argument("--source-package", type=Path, required=True)
    parser.add_argument("--target-package", type=Path, required=True)
    parser.add_argument("--site", required=True)
    args = parser.parse_args(argv)
    report = evaluate(args.source_package, args.target_package, args.site)
    print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    # Exit zero means the diagnostic ran, NOT that migration is ready.
    return 0 if report["status"] == "BLOCKED_INDEPENDENT_RESTORE_AND_OPERATOR_POLICY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
