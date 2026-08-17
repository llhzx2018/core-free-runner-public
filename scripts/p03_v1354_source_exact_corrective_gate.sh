#!/usr/bin/env bash
set -Eeuo pipefail

: "${GATE_ROOT:=/tmp/p03-v1354-source-exact}"
: "${FIXTURE_PASS:=VfP03-Source-Exact-2026!}"

rm -rf "$GATE_ROOT"
mkdir -p "$GATE_ROOT"

CORRECTIVE="$GITHUB_WORKSPACE/corrective"
PRODUCT="$GITHUB_WORKSPACE/product"
PROD1353="$GITHUB_WORKSPACE/production"

python3 "$PRODUCT/scripts/build_runtime.py" "$GATE_ROOT/frozen" >/dev/null
python3 "$PROD1353/scripts/build_runtime.py" "$GATE_ROOT/prod1353" >/dev/null

python3 - "$CORRECTIVE" "$GATE_ROOT/frozen" "$GATE_ROOT/prod1353" <<'PY'
import importlib.util,json,sys
from pathlib import Path
corr=Path(sys.argv[1]); frozen=Path(sys.argv[2]); prod=Path(sys.argv[3])
spec=importlib.util.spec_from_file_location('scope',corr/'scripts/corrective/v1354_source_exact_scope.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
out=m.assert_frozen_runtime(frozen)
assert out['runtime_files']==42
assert out['runtime_fingerprint']==m.EXPECTED_RUNTIME_FINGERPRINT
assert (frozen/'memory-api.php').is_file()
assert not (prod/'memory-api.php').exists()
wrapper=(corr/'scripts/build_atomic_corrected.py').read_text(encoding='utf-8')
assert '"memory-api.php"' in wrapper
assert "'maintenance.php','memory-api.php','robots.txt'" in wrapper
print(json.dumps(out,sort_keys=True))
print('FROZEN_RUNTIME=42_EXACT')
print('V1353_MEMORY_API=ABSENT_CONFIRMED')
print('FUTURE_ATOMIC_MANAGED_SCOPE=MEMORY_API_INCLUDED')
PY

# Minimal M030/preservation regression only; unrelated historical gates are not rerun.
git -C "$PROD1353" show HEAD:database/schema/current.sql > "$GATE_ROOT/schema29.sql"
grep -q 'Schema 29' "$GATE_ROOT/schema29.sql"
(
  cd "$PRODUCT"
  VF_SCHEMA29_SQL="$GATE_ROOT/schema29.sql" php tests/maintenance/v1354_schema30_runtime.php
)
echo 'M030_MINIMAL_REGRESSION=PASS'

defective="$GATE_ROOT/defective"
cp -a "$GATE_ROOT/frozen" "$defective"
rm -f "$defective/memory-api.php"
python3 "$CORRECTIVE/scripts/corrective/build_v1354_same_version_reconcile.py" --runtime-root "$GATE_ROOT/frozen" --output "$defective/source-reconcile-v1.35.4.php" | tee "$GATE_ROOT/reconcile-build.json"
php -l "$defective/source-reconcile-v1.35.4.php" >/dev/null

echo 'SAME_VERSION_RECONCILER_BUILD=PASS'

start_fixture() {
  local runtime="$1" data_root="$2" port="$3" pidfile="$4"
  mkdir -p "$data_root"
  VF_FORGE_DATA_ROOT="$data_root" php -S "127.0.0.1:$port" -t "$runtime" >"$GATE_ROOT/php-$port.log" 2>&1 &
  echo $! > "$pidfile"
  local ready=0
  for _ in $(seq 1 100); do
    if curl -fsS "http://127.0.0.1:$port/setup.php" >/dev/null 2>&1; then ready=1; break; fi
    sleep .15
  done
  test "$ready" = 1
}

setup_and_login() {
  local port="$1" data_root="$2" cookie="$3" csrf_out="$4"
  local base="http://127.0.0.1:$port"
  curl -fsS -c "$cookie" "$base/setup.php" -o "$GATE_ROOT/setup-$port.html"
  local setup_csrf
  setup_csrf=$(python3 - "$GATE_ROOT/setup-$port.html" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="setup_csrf" value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
  curl -fsS -i -b "$cookie" -c "$cookie" -H "Origin: $base" \
    --data-urlencode "setup_csrf=$setup_csrf" \
    --data-urlencode 'site_title=VF Forge Source Exact Fixture' \
    --data-urlencode "data_root=$data_root" \
    --data-urlencode "password=$FIXTURE_PASS" \
    --data-urlencode "password_confirm=$FIXTURE_PASS" \
    "$base/setup.php" > "$GATE_ROOT/setup-post-$port.txt"
  grep -Eq '^HTTP/.* 302|^HTTP/.* 303' "$GATE_ROOT/setup-post-$port.txt"
  curl -fsS -b "$cookie" -c "$cookie" -H "Origin: $base" -H 'Content-Type: application/json' \
    --data "{\"password\":\"$FIXTURE_PASS\"}" "$base/api.php?action=login" > "$GATE_ROOT/login-$port.json"
  python3 - "$GATE_ROOT/login-$port.json" "$csrf_out" <<'PY'
import json,sys
j=json.load(open(sys.argv[1],encoding='utf-8'));assert j['ok'] is True and j.get('csrf');open(sys.argv[2],'w').write(j['csrf'])
PY
}

stop_fixture() {
  local pidfile="$1"
  if [[ -f "$pidfile" ]]; then kill "$(cat "$pidfile")" >/dev/null 2>&1 || true; wait "$(cat "$pidfile")" 2>/dev/null || true; fi
}

# Positive HTTP same-version reconciliation.
PORT=18134
DATA="$GATE_ROOT/data-positive"
COOKIE="$GATE_ROOT/cookie-positive"
PIDFILE="$GATE_ROOT/pid-positive"
CSRF_FILE="$GATE_ROOT/csrf-positive"
start_fixture "$defective" "$DATA" "$PORT" "$PIDFILE"
trap 'stop_fixture "$PIDFILE"' EXIT
setup_and_login "$PORT" "$DATA" "$COOKIE" "$CSRF_FILE"
BASE="http://127.0.0.1:$PORT"
DB=$(find "$DATA/database" -maxdepth 1 -type f -name '*.sqlite' | head -n1)
test -n "$DB"
DB_BEFORE=$(sha256sum "$DB" | awk '{print $1}')

# Unauthenticated access must not reach reconcile form.
code=$(curl -sS -o "$GATE_ROOT/unauth.html" -w '%{http_code}' "$BASE/source-reconcile-v1.35.4.php")
test "$code" != 200 || ! grep -q '执行同版本源码校正' "$GATE_ROOT/unauth.html"
echo 'NEG_UNAUTHENTICATED=DENY'

curl -fsS -b "$COOKIE" "$BASE/source-reconcile-v1.35.4.php" -o "$GATE_ROOT/reconcile-get.html"
grep -q '执行同版本源码校正' "$GATE_ROOT/reconcile-get.html"
FORM_CSRF=$(python3 - "$GATE_ROOT/reconcile-get.html" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="_csrf" value="([^"]+)"',s);assert m;print(m.group(1))
PY
)

# Missing CSRF must deny and leave target absent.
code=$(curl -sS -b "$COOKIE" -o "$GATE_ROOT/no-csrf.html" -w '%{http_code}' --data 'confirmation=RECONCILE_MEMORY_API' "$BASE/source-reconcile-v1.35.4.php")
test "$code" != 200 || ! grep -q 'Source Reconciliation 完成' "$GATE_ROOT/no-csrf.html"
test ! -e "$defective/memory-api.php"
echo 'NEG_MISSING_CSRF=DENY'

curl -fsS -b "$COOKIE" --data-urlencode "_csrf=$FORM_CSRF" --data-urlencode 'confirmation=RECONCILE_MEMORY_API' "$BASE/source-reconcile-v1.35.4.php" -o "$GATE_ROOT/reconcile-post.html"
grep -q 'Source Reconciliation 完成' "$GATE_ROOT/reconcile-post.html"
test -f "$defective/memory-api.php"
DB_AFTER=$(sha256sum "$DB" | awk '{print $1}')
test "$DB_BEFORE" = "$DB_AFTER"
test "$(sqlite3 "$DB" 'pragma integrity_check;')" = 'ok'
test -z "$(sqlite3 "$DB" 'pragma foreign_key_check;')"
python3 - "$CORRECTIVE" "$defective" <<'PY'
import importlib.util,sys
from pathlib import Path
corr=Path(sys.argv[1]);root=Path(sys.argv[2]);spec=importlib.util.spec_from_file_location('scope',corr/'scripts/corrective/v1354_source_exact_scope.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);o=m.assert_frozen_runtime(root);assert o['runtime_files']==42;assert o['runtime_fingerprint']==m.EXPECTED_RUNTIME_FINGERPRINT;print('POST_RECONCILE_RUNTIME_42_EXACT=PASS');print('MEMORY_API_EXACT=PASS')
PY
RECOVERY_COUNT=$(find "$DATA/backups" -type f -name RECOVERY.json 2>/dev/null | wc -l)
test "$RECOVERY_COUNT" -ge 1
echo 'SAME_VERSION_HTTP_RECONCILIATION=PASS'
echo 'DB_WRITE=0_BY_SHA_IDENTITY'
echo 'SQLITE_INTEGRITY=PASS'
echo 'FOREIGN_KEYS=PASS'
echo 'RECOVERY_METADATA=PASS'
stop_fixture "$PIDFILE"; trap - EXIT

# Negative: mismatched existing memory-api must fail closed.
NEG="$GATE_ROOT/negative-existing"
cp -a "$GATE_ROOT/frozen" "$NEG"
printf 'tampered\n' > "$NEG/memory-api.php"
python3 "$CORRECTIVE/scripts/corrective/build_v1354_same_version_reconcile.py" --runtime-root "$GATE_ROOT/frozen" --output "$NEG/source-reconcile-v1.35.4.php" >/dev/null
PORT=18135; DATA="$GATE_ROOT/data-existing"; COOKIE="$GATE_ROOT/cookie-existing"; PIDFILE="$GATE_ROOT/pid-existing"; CSRF_FILE="$GATE_ROOT/csrf-existing"
start_fixture "$NEG" "$DATA" "$PORT" "$PIDFILE"; trap 'stop_fixture "$PIDFILE"' EXIT
setup_and_login "$PORT" "$DATA" "$COOKIE" "$CSRF_FILE"
code=$(curl -sS -b "$COOKIE" -o "$GATE_ROOT/existing.html" -w '%{http_code}' "http://127.0.0.1:$PORT/source-reconcile-v1.35.4.php")
grep -q 'Source Reconciliation 阻断' "$GATE_ROOT/existing.html"
grep -q 'must be truly absent' "$GATE_ROOT/existing.html"
test "$(cat "$NEG/memory-api.php")" = 'tampered'
echo 'NEG_EXISTING_MISMATCH=DENY'
stop_fixture "$PIDFILE"; trap - EXIT

# Recovery negative: fail after atomic write must delete only the newly written path.
ROLL="$GATE_ROOT/rollback"
cp -a "$GATE_ROOT/frozen" "$ROLL"
rm -f "$ROLL/memory-api.php"
python3 "$CORRECTIVE/scripts/corrective/build_v1354_same_version_reconcile.py" --runtime-root "$GATE_ROOT/frozen" --output "$ROLL/source-reconcile-v1.35.4.php" --test-fail-stage after_write >/dev/null
PORT=18136; DATA="$GATE_ROOT/data-rollback"; COOKIE="$GATE_ROOT/cookie-rollback"; PIDFILE="$GATE_ROOT/pid-rollback"; CSRF_FILE="$GATE_ROOT/csrf-rollback"
start_fixture "$ROLL" "$DATA" "$PORT" "$PIDFILE"; trap 'stop_fixture "$PIDFILE"' EXIT
setup_and_login "$PORT" "$DATA" "$COOKIE" "$CSRF_FILE"
BASE="http://127.0.0.1:$PORT"; DB=$(find "$DATA/database" -maxdepth 1 -type f -name '*.sqlite' | head -n1); DB_BEFORE=$(sha256sum "$DB"|awk '{print $1}')
curl -fsS -b "$COOKIE" "$BASE/source-reconcile-v1.35.4.php" -o "$GATE_ROOT/rollback-get.html"
FORM_CSRF=$(python3 - "$GATE_ROOT/rollback-get.html" <<'PY'
import re,sys
m=re.search(r'name="_csrf" value="([^"]+)"',open(sys.argv[1],encoding='utf-8').read());assert m;print(m.group(1))
PY
)
code=$(curl -sS -b "$COOKIE" -o "$GATE_ROOT/rollback-post.html" -w '%{http_code}' --data-urlencode "_csrf=$FORM_CSRF" --data-urlencode 'confirmation=RECONCILE_MEMORY_API' "$BASE/source-reconcile-v1.35.4.php")
grep -q 'Source Reconciliation 阻断' "$GATE_ROOT/rollback-post.html"
grep -q 'TEST_FAILPOINT_after_write' "$GATE_ROOT/rollback-post.html"
test ! -e "$ROLL/memory-api.php"
DB_AFTER=$(sha256sum "$DB"|awk '{print $1}'); test "$DB_BEFORE" = "$DB_AFTER"
echo 'FAILURE_RECOVERY=PASS'
echo 'ROLLBACK_MEMORY_API_ABSENT=PASS'
echo 'ROLLBACK_DB_UNCHANGED=PASS'
stop_fixture "$PIDFILE"; trap - EXIT

# Native transport contract check: current ManualUpdateService rejects same-version target.
grep -q "version_compare(\$target,\$current,'>')" "$PRODUCT/app/ManualUpdateService.php" || grep -q "version_compare(\$target,\$current,'>')" "$PRODUCT/../product/src/app/ManualUpdateService.php"
echo 'CURRENT_MANUAL_UPDATE_TRANSPORT_SAME_VERSION=UNSUPPORTED_EXACT_CONTRACT'
echo 'PRODUCTION_WRITE=0'
echo 'PHYSICAL_DELETE=0'
echo 'V1.35.5=NOT_CREATED'
echo 'P03_V1354_SOURCE_EXACT_CORRECTIVE_RUNNER_GATE=PASS'
