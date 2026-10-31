"""Rebuild exact P07 product candidate from released source in temporary CI only."""
from __future__ import annotations
from pathlib import Path
import hashlib
import sys

ORIGINAL = "fd9a3cd7e366f0914e86a71a062fe16be6e46398"
EXPECTED = "7d276b14586719c960cb4f609697502beaf96b3a"

def blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\x00" + data).hexdigest()

path = Path(sys.argv[1])
data = path.read_bytes()
assert blob(data) == ORIGINAL, "released source identity mismatch"
original = data.decode("utf-8")

before_resume = '''    if (state.get("status") == "PREPARE_FAILED"
            and isinstance(previous_guard, dict)
            and previous_guard.get("reason") == "CONDITIONAL_DDL"):
        raise PullMigrationError(
            "PREPARE_RESUME_SQL_GUARD_AND_RECOVERY_PROOF_REQUIRED"
        )'''
after_resume = '''    if (state.get("status") == "PREPARE_FAILED"
            and isinstance(previous_guard, dict)
            and previous_guard.get("reason") == "CONDITIONAL_DDL"):
        raise PullMigrationError(
            "PREPARE_RESUME_SQL_GUARD_AND_RECOVERY_PROOF_REQUIRED"
        )
    # Older migrations can have no persisted SQL-guard evidence although
    # some sites were already staged. Never infer a safe retry merely from
    # a missing field: target DBs may already hold source/target mixed data.
    # This must execute before a status change, network call or DB write.
    if state.get("status") == "PREPARE_FAILED":
        sites = state.get("sites")
        if (not isinstance(sites, list) or not sites
                or any(not isinstance(site, dict) for site in sites)
                or any(site.get("stage_status") == "PULLED_STAGED"
                       for site in sites)):
            raise PullMigrationError(
                "PREPARE_RESUME_PARTIAL_STATE_RECOVERY_PROOF_REQUIRED"
            )'''

before_summary = '''        "cutover_prohibited": bool(state.get("cutover_prohibited", False)),'''
after_summary = '''        # Report runtime readiness rather than simply echoing the
        # partial-child flag. A PREPARE_FAILED parent can otherwise print
        # cutover_prohibited=false even though cutover_migration rejects it.
        "cutover_prohibited": bool(
            state.get("cutover_prohibited", False)
            or state.get("partial_parent_migration_id")
            or state.get("status") not in {
                "PREPARED", "CUTOVER_RUNNING", "CUTOVER_FAILED_ROLLED_BACK"
            }
        ),
        "prepare_failure_provenance": (
            "MISSING_PARTIAL_STATE_RECOVERY_REQUIRED"
            if state.get("status") == "PREPARE_FAILED"
            and not isinstance(state.get("last_sql_guard_failure"), dict)
            else "RECORDED" if isinstance(
                state.get("last_sql_guard_failure"), dict
            ) else "NOT_APPLICABLE"
        ),'''

assert original.count(before_resume) == 1, "resume patch anchor mismatch"
assert original.count(before_summary) == 1, "status patch anchor mismatch"
modified = original.replace(before_resume, after_resume).replace(before_summary, after_summary)
assert blob(modified.encode("utf-8")) == EXPECTED, "product candidate source mismatch"
path.write_text(modified, encoding="utf-8")
print("P07_FAIL_CLOSED_EXACT_PRODUCT_SOURCE_RECONSTRUCTED_PASS")
