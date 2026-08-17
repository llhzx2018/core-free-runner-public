#!/usr/bin/env bash
set -Eeuo pipefail
: "${GATE_ROOT:=/tmp/p03-v1354-source-exact-v2}"
: "${FIXTURE_PASS:=VfP03-Source-Exact-2026!}"
: "${PHP_TEST_IMAGE:?}"
rm -rf "$GATE_ROOT"; mkdir -p "$GATE_ROOT"
CORRECTIVE="$GITHUB_WORKSPACE/corrective"; PRODUCT="$GITHUB_WORKSPACE/product"; PROD1353="$GITHUB_WORKSPACE/production"
python3 "$PRODUCT/scripts/build_runtime.py" "$GATE_ROOT/frozen" >/dev/null
python3 "$PROD1353/scripts/build_runtime.py" "$GATE_ROOT/prod1353" >/dev/null
python3 - "$CORRECTIVE" "$GATE_ROOT/frozen" "$GATE_ROOT/prod1353" <<'PY'
import importlib.util,json,sys
from pathlib import Path
c=Path(sys.argv[1]);f=Path(sys.argv[2]);p=Path(sys.argv[3]);s=importlib.util.spec_from_file_location('scope',c/'scripts/corrective/v1354_source_exact_scope.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);o=m.assert_frozen_runtime(f);assert o['runtime_files']==42 and o['runtime_fingerprint']==m.EXPECTED_RUNTIME_FINGERPRINT;assert (f/'memory-api.php').is_file() and not (p/'memory-api.php').exists();w=(c/'scripts/build_atomic_corrected.py').read_text();assert '"memory-api.php"' in w and "'maintenance.php','memory-api.php','robots.txt'" in w;print(json.dumps(o,sort_keys=True));print('FROZEN_RUNTIME=42_EXACT');print('V1353_MEMORY_API=ABSENT_CONFIRMED');print('FUTURE_ATOMIC_MANAGED_SCOPE=MEMORY_API_INCLUDED')
PY

git -C "$PROD1353" show HEAD:database/schema/current.sql > "$GATE_ROOT/schema29.sql"
grep -q 'Schema 29' "$GATE_ROOT/schema29.sql"
(cd "$PRODUCT" && VF_SCHEMA29_SQL="$GATE_ROOT/schema29.sql" php tests/maintenance/v1354_schema30_runtime.php)
echo 'M030_MINIMAL_REGRESSION=PASS'

build_defective(){ local out="$1" fail="${2:-}"; rm -rf "$out"; cp -a "$GATE_ROOT/frozen" "$out"; rm -f "$out/memory-api.php"; if [[ -n "$fail" ]]; then python3 "$CORRECTIVE/scripts/corrective/build_v1354_same_version_reconcile.py" --runtime-root "$GATE_ROOT/frozen" --output "$out/source-reconcile-v1.35.4.php" --test-fail-stage "$fail" >/dev/null; else python3 "$CORRECTIVE/scripts/corrective/build_v1354_same_version_reconcile.py" --runtime-root "$GATE_ROOT/frozen" --output "$out/source-reconcile-v1.35.4.php" >/dev/null; fi; docker run --rm -v "$out:/app" -w /app "$PHP_TEST_IMAGE" php -l source-reconcile-v1.35.4.php >/dev/null; }
start_fixture(){ local runtime="$1" data="$2" port="$3"; local name="p03-source-exact-$port"; mkdir -p "$data"; docker rm -f "$name" >/dev/null 2>&1||true; docker run -d --rm --name "$name" -p "$port:$port" -v "$runtime:/app" -v "$data:$data" -w /app "$PHP_TEST_IMAGE" php -S "0.0.0.0:$port" -t /app >/dev/null; local ok=0; for _ in $(seq 1 120);do if curl -fsS "http://127.0.0.1:$port/setup.php" >/dev/null 2>&1;then ok=1;break;fi;sleep .2;done; if [[ "$ok" != 1 ]];then docker logs "$name";return 1;fi; }
stop_fixture(){ docker rm -f "p03-source-exact-$1" >/dev/null 2>&1||true; }
setup_login(){ local port="$1" data="$2" cookie="$3"; local b="http://127.0.0.1:$port"; curl -fsS -c "$cookie" "$b/setup.php" -o "$GATE_ROOT/setup-$port.html"; local sc; sc=$(python3 - "$GATE_ROOT/setup-$port.html" <<'PY'
import re,sys
m=re.search(r'name="setup_csrf" value="([^"]+)"',open(sys.argv[1]).read());assert m;print(m.group(1))
PY
); curl -fsS -i -b "$cookie" -c "$cookie" -H "Origin: $b" --data-urlencode "setup_csrf=$sc" --data-urlencode 'site_title=VF Forge Source Exact Fixture' --data-urlencode "data_root=$data" --data-urlencode "password=$FIXTURE_PASS" --data-urlencode "password_confirm=$FIXTURE_PASS" "$b/setup.php" > "$GATE_ROOT/setup-post-$port.txt"; grep -Eq '^HTTP/.* 302|^HTTP/.* 303' "$GATE_ROOT/setup-post-$port.txt"; curl -fsS -b "$cookie" -c "$cookie" -H "Origin: $b" -H 'Content-Type: application/json' --data "{\"password\":\"$FIXTURE_PASS\"}" "$b/api.php?action=login" > "$GATE_ROOT/login-$port.json"; python3 - "$GATE_ROOT/login-$port.json" <<'PY'
import json,sys
j=json.load(open(sys.argv[1]));assert j['ok'] and j['csrf'] and j['version']=='1.35.4'
PY
}
form_csrf(){ python3 - "$1" <<'PY'
import re,sys
m=re.search(r'name="_csrf" value="([^"]+)"',open(sys.argv[1]).read());assert m;print(m.group(1))
PY
}

# Positive: exact 41 -> 42, no DB bytes change.
RT="$GATE_ROOT/positive"; DATA="$GATE_ROOT/data-positive"; COOKIE="$GATE_ROOT/cookie-positive"; PORT=18134
build_defective "$RT"; start_fixture "$RT" "$DATA" "$PORT"; trap 'stop_fixture 18134' EXIT; setup_login "$PORT" "$DATA" "$COOKIE"; BASE="http://127.0.0.1:$PORT"; DB=$(find "$DATA/database" -maxdepth 1 -type f -name '*.sqlite'|head -n1); test -n "$DB"; DB0=$(sha256sum "$DB"|awk '{print $1}')
code=$(curl -sS -o "$GATE_ROOT/unauth.html" -w '%{http_code}' "$BASE/source-reconcile-v1.35.4.php"); test "$code" != 200 || ! grep -q '执行同版本源码校正' "$GATE_ROOT/unauth.html"; echo 'NEG_UNAUTHENTICATED=DENY'
curl -fsS -b "$COOKIE" "$BASE/source-reconcile-v1.35.4.php" -o "$GATE_ROOT/get.html"; grep -q '执行同版本源码校正' "$GATE_ROOT/get.html"; CSRF=$(form_csrf "$GATE_ROOT/get.html")
code=$(curl -sS -b "$COOKIE" -o "$GATE_ROOT/no-csrf.html" -w '%{http_code}' --data 'confirmation=RECONCILE_MEMORY_API' "$BASE/source-reconcile-v1.35.4.php"); test "$code" != 200 || ! grep -q 'Source Reconciliation 完成' "$GATE_ROOT/no-csrf.html"; test ! -e "$RT/memory-api.php"; echo 'NEG_MISSING_CSRF=DENY'
curl -fsS -b "$COOKIE" --data-urlencode "_csrf=$CSRF" --data-urlencode 'confirmation=RECONCILE_MEMORY_API' "$BASE/source-reconcile-v1.35.4.php" -o "$GATE_ROOT/post.html"; grep -q 'Source Reconciliation 完成' "$GATE_ROOT/post.html"; DB1=$(sha256sum "$DB"|awk '{print $1}'); test "$DB0" = "$DB1"; test "$(sqlite3 "$DB" 'pragma integrity_check;')" = ok; test -z "$(sqlite3 "$DB" 'pragma foreign_key_check;')"
python3 - "$CORRECTIVE" "$RT" <<'PY'
import importlib.util,sys
from pathlib import Path
c=Path(sys.argv[1]);r=Path(sys.argv[2]);s=importlib.util.spec_from_file_location('scope',c/'scripts/corrective/v1354_source_exact_scope.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);o=m.assert_frozen_runtime(r);assert o['runtime_files']==42 and o['runtime_fingerprint']==m.EXPECTED_RUNTIME_FINGERPRINT;print('POST_RECONCILE_RUNTIME_42_EXACT=PASS');print('MEMORY_API_EXACT=PASS')
PY
find "$DATA/backups" -type f -name RECOVERY.json | grep -q .; echo 'SAME_VERSION_HTTP_RECONCILIATION=PASS'; echo 'DB_WRITE=0_BY_SHA_IDENTITY'; echo 'SQLITE_INTEGRITY=PASS'; echo 'FOREIGN_KEYS=PASS'; echo 'RECOVERY_METADATA=PASS'; stop_fixture "$PORT"; trap - EXIT

# Negative: existing mismatched file is denied.
RT="$GATE_ROOT/existing"; DATA="$GATE_ROOT/data-existing"; COOKIE="$GATE_ROOT/cookie-existing"; PORT=18135
build_defective "$RT"; printf 'tampered\n' > "$RT/memory-api.php"; start_fixture "$RT" "$DATA" "$PORT"; trap 'stop_fixture 18135' EXIT; setup_login "$PORT" "$DATA" "$COOKIE"; code=$(curl -sS -b "$COOKIE" -o "$GATE_ROOT/existing.html" -w '%{http_code}' "http://127.0.0.1:$PORT/source-reconcile-v1.35.4.php"); grep -q 'Source Reconciliation 阻断' "$GATE_ROOT/existing.html"; grep -q 'must be truly absent' "$GATE_ROOT/existing.html"; test "$(cat "$RT/memory-api.php")" = tampered; echo 'NEG_EXISTING_MISMATCH=DENY'; stop_fixture "$PORT"; trap - EXIT

# Failure recovery: fail after write, restore absence, DB unchanged.
RT="$GATE_ROOT/rollback"; DATA="$GATE_ROOT/data-rollback"; COOKIE="$GATE_ROOT/cookie-rollback"; PORT=18136
build_defective "$RT" after_write; start_fixture "$RT" "$DATA" "$PORT"; trap 'stop_fixture 18136' EXIT; setup_login "$PORT" "$DATA" "$COOKIE"; BASE="http://127.0.0.1:$PORT"; DB=$(find "$DATA/database" -maxdepth 1 -type f -name '*.sqlite'|head -n1); DB0=$(sha256sum "$DB"|awk '{print $1}'); curl -fsS -b "$COOKIE" "$BASE/source-reconcile-v1.35.4.php" -o "$GATE_ROOT/rget.html"; CSRF=$(form_csrf "$GATE_ROOT/rget.html"); code=$(curl -sS -b "$COOKIE" -o "$GATE_ROOT/rpost.html" -w '%{http_code}' --data-urlencode "_csrf=$CSRF" --data-urlencode 'confirmation=RECONCILE_MEMORY_API' "$BASE/source-reconcile-v1.35.4.php"); grep -q 'TEST_FAILPOINT_after_write' "$GATE_ROOT/rpost.html"; test ! -e "$RT/memory-api.php"; DB1=$(sha256sum "$DB"|awk '{print $1}'); test "$DB0" = "$DB1"; echo 'FAILURE_RECOVERY=PASS'; echo 'ROLLBACK_MEMORY_API_ABSENT=PASS'; echo 'ROLLBACK_DB_UNCHANGED=PASS'; stop_fixture "$PORT"; trap - EXIT

grep -q "version_compare(\$target,\$current,'>')" "$PRODUCT/app/ManualUpdateService.php"
echo 'CURRENT_MANUAL_UPDATE_TRANSPORT_SAME_VERSION=UNSUPPORTED_EXACT_CONTRACT'
echo 'PRODUCTION_WRITE=0'; echo 'PHYSICAL_DELETE=0'; echo 'V1.35.5=NOT_CREATED'; echo 'P03_V1354_SOURCE_EXACT_CORRECTIVE_RUNNER_GATE=PASS'
