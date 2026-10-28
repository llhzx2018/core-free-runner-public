#!/usr/bin/env bash
set -uo pipefail
candidate="$(realpath "$1")"
stable="$(realpath "$2")"
proof="$3"
mkdir -p "$proof"
work="$(mktemp -d "$RUNNER_TEMP/p01-safety-harness-XXXXXXXX")"
trap 'rm -rf -- "$work"' EXIT
declare -a gate_names=()
declare -a gate_states=()
failed=0
gate() {
  local name="$1"; shift
  local output="$work/$name.log"
  echo "START $name"
  if "$@" >"$output" 2>&1; then
    gate_names+=("$name"); gate_states+=("PASS")
    echo "GATE $name PASS"
  else
    local code="$?"
    gate_names+=("$name"); gate_states+=("FAIL")
    failed=$((failed+1))
    echo "GATE $name FAIL exit=$code"
    grep -E '^(P01_|PASS |FAIL |CANONICAL_|NEW_UNIT_REGRESSION=|CHANGED_TEST_FAILURE=|MISSING_|CURRENT_|BASELINE_|REGRESSION_)' "$output" | tail -n 30 || true
  fi
}
echo "PROOF_BOUNDARY=EXACT_SOURCE_SYNTHETIC_ONLY"
echo "P01_UNIT_BASELINE_RELEASE_SHA=$BASE_SHA"
gate canonical_unit_baseline timeout 1320 bash "$candidate/tests/canonical_release_regression.sh" "$candidate" "$stable"
gate isolated_fresh_install timeout 240 bash "$candidate/tests/integration/p01_ia_v3_r7_routes_http.sh" "$candidate"
test -f "$candidate/tests/integration/p01_backup_baseline_existing_install_http.sh" || exit 51
cp "$candidate/tests/integration/p01_backup_baseline_existing_install_http.sh" "$work/upgrade-fixture.sh"
grep -Fq '= 2.47.384' "$work/upgrade-fixture.sh" || exit 52
sed -i 's/= 2\.47\.384/= 2.47.466/' "$work/upgrade-fixture.sh"
grep -Fq '= 2.47.466' "$work/upgrade-fixture.sh" || exit 53
echo "P01_DISPOSABLE_UPGRADE_FIXTURE_BASELINE=2.47.466"
gate isolated_existing_install_upgrade_backup_restore timeout 320 bash "$work/upgrade-fixture.sh" "$candidate" "$stable"
gate backup_restore_failure_injection timeout 120 php "$candidate/tests/unit/backup_baseline_reset_exact_source_gate.php"
gate backup_retention_fault_fail_closed timeout 120 php "$candidate/tests/unit/backup_retention_delete_fault_matrix_native.php"
gate backup_recovery_symlink_fail_closed timeout 120 php "$candidate/tests/unit/backup_recovery_symlink_fail_closed_native.php"
gate backup_survivor_floor_no_delete timeout 120 php "$candidate/tests/unit/backup_retention_full_proof_gate_native.php"
gate atomic_runtime_cache_contract timeout 120 php "$candidate/tests/unit/atomic_runtime_cache_contract.php"
gate updater_error_recovery_contract timeout 120 php "$candidate/tests/unit/update_recovery_contract.php"
gate csrf_session_contract timeout 120 php "$candidate/tests/unit/session_csrf_contract.php"
gate private_credential_isolation timeout 120 php "$candidate/tests/unit/gov_book_private_auth_isolation_native.php"
gate storage_backup_integrity timeout 120 php "$candidate/tests/unit/backup_automatic_retention_safety_readonly_native.php"
export P01_GATE_NAMES="$(IFS=,; echo "${gate_names[*]}")"
export P01_GATE_STATES="$(IFS=,; echo "${gate_states[*]}")"
export P01_GATE_FAILURE_COUNT="$failed"
python3 - "$proof/metadata.json" <<'PY'
import json,os,sys
names=os.environ["P01_GATE_NAMES"].split(",")
states=os.environ["P01_GATE_STATES"].split(",")
value={"schema":"vf-p01-pr1820-isolated-safety/v1",
"target_repo":"llhzx2018/vf-start",
"target_sha":os.environ["TARGET_SHA"],
"baseline_sha":os.environ["BASE_SHA"],
"version":os.environ["TARGET_VERSION"],
"run_id":os.environ["GITHUB_RUN_ID"],
"unit_inventory_each":771,
"gates":[{"name":k,"status":v} for k,v in zip(names,states)],
"failed_gates":int(os.environ["P01_GATE_FAILURE_COUNT"]),
"scope":"synthetic-source-replacement;backup-restore;failure-injection;security;canonical-unit-regression",
"not_proven":["formal-full-package","real-atomic-online-version-change","production"] }
with open(sys.argv[1],"w",encoding="utf-8") as f: json.dump(value,f,sort_keys=True)
print("P01_GATES_EVALUATED="+str(len(names)))
print("P01_GATE_FAILURE_COUNT="+str(value["failed_gates"]))
PY
if [ "$failed" -ne 0 ]; then
  echo "P01_ISOLATED_SAFETY_PROOF=FAIL_REQUIRES_TRIAGE"
  exit 1
fi
echo "P01_ISOLATED_SAFETY_PROOF=PASS_FOCUSED_WITH_LIMITATIONS"
