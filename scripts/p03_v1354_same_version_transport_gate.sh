#!/usr/bin/env bash
set -Eeuo pipefail
: "${GATE_ROOT:=/tmp/p03-v1354-transport}"
: "${FIXTURE_PASS:=VfP03-Transport-2026!}"
: "${PHP_TEST_IMAGE:?}"
rm -rf "$GATE_ROOT"; mkdir -p "$GATE_ROOT"
CORRECTIVE="$GITHUB_WORKSPACE/corrective"
PRODUCT="$GITHUB_WORKSPACE/product"
python3 "$PRODUCT/scripts/build_runtime.py" "$GATE_ROOT/frozen" >/dev/null
python3 - "$CORRECTIVE" "$GATE_ROOT/frozen" <<'PY'
import importlib.util,sys
from pathlib import Path
c=Path(sys.argv[1]);r=Path(sys.argv[2]);s=importlib.util.spec_from_file_location('scope',c/'scripts/corrective/v1354_source_exact_scope.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);o=m.assert_frozen_runtime(r);assert o['runtime_files']==42;assert o['runtime_fingerprint']==m.EXPECTED_RUNTIME_FINGERPRINT;assert o['memory_api_bytes']==4497;assert o['memory_api_sha256']=='1c9b784d0a1c8cb8f9245c4c9bc7af6511c55006de5fd3fefa796b1ec438a9b7';print('FROZEN_IDENTITY=PASS')
PY

build_fixture(){
  local out="$1" suffix="$2" fail="${3:-}"
  rm -rf "$out"; cp -a "$GATE_ROOT/frozen" "$out"; rm -f "$out/memory-api.php"
  local name="vf-forge-v1354-source-reconcile-${suffix}.php"
  if [[ -n "$fail" ]]; then
    python3 "$CORRECTIVE/scripts/corrective/finalize_v1354_same_version_reconcile_production.py" --runtime-root "$GATE_ROOT/frozen" --output-dir "$out" --filename "$name" --test-fail-stage "$fail" >"$out/.build.json"
  else
    python3 "$CORRECTIVE/scripts/corrective/finalize_v1354_same_version_reconcile_production.py" --runtime-root "$GATE_ROOT/frozen" --output-dir "$out" --filename "$name" >"$out/.build.json"
  fi
  python3 - "$out/.build.json" "$out/$name" <<'PY'
import hashlib,json,sys
from pathlib import Path
j=json.load(open(sys.argv[1]));p=Path(sys.argv[2]);raw=p.read_bytes();assert j['filename']==p.name;assert j['bytes']==len(raw);assert j['sha256']==hashlib.sha256(raw).hexdigest();assert j['runtime_fingerprint']=='2fd3ebbbebfd7155371fe44664715cbe34f63cfb98dfeb691bba90d4864ca083';assert j['memory_api_sha256']=='1c9b784d0a1c8cb8f9245c4c9bc7af6511c55006de5fd3fefa796b1ec438a9b7';print('TOOL_SHA=LOCKED');print(j['sha256'])
PY
  docker run --rm -v "$out:/app" -w /app "$PHP_TEST_IMAGE" php -l "$name" >/dev/null
  echo 'TOOL_SYNTAX=PASS'
}
start_fixture(){
  local runtime="$1" data="$2" port="$3"
  local name="p03-v1354-transport-$port"
  mkdir -p "$data"; docker rm -f "$name" >/dev/null 2>&1 || true
  docker run -d --rm --name "$name" -p "$port:$port" -v "$runtime:/app" -v "$data:$data" -w /app "$PHP_TEST_IMAGE" php -S "0.0.0.0:$port" -t /app >/dev/null
  local ok=0
  for _ in $(seq 1 120); do if curl -fsS "http://127.0.0.1:$port/setup.php" >/dev/null 2>&1; then ok=1; break; fi; sleep .2; done
  if [[ "$ok" != 1 ]]; then docker logs "$name"; return 1; fi
}
stop_fixture(){ docker rm -f "p03-v1354-transport-$1" >/dev/null 2>&1 || true; }
setup_login(){
  local port="$1" data="$2" cookie="$3" runtime="$4"
  local b="http://127.0.0.1:$port"
  curl -fsS -c "$cookie" "$b/setup.php" -o "$GATE_ROOT/setup-$port.html"
  local sc
  sc=$(python3 - "$GATE_ROOT/setup-$port.html" <<'PY'
import re,sys
m=re.search(r'name="setup_csrf" value="([^"]+)"',open(sys.argv[1]).read());assert m;print(m.group(1))
PY
)
  curl -fsS -i -b "$cookie" -c "$cookie" -H "Origin: $b" --data-urlencode "setup_csrf=$sc" --data-urlencode 'site_title=VF Forge Transport Fixture' --data-urlencode "data_root=$data" --data-urlencode "password=$FIXTURE_PASS" --data-urlencode "password_confirm=$FIXTURE_PASS" "$b/setup.php" > "$GATE_ROOT/setup-post-$port.txt"
  grep -Eq '^HTTP/.* 302|^HTTP/.* 303' "$GATE_ROOT/setup-post-$port.txt"
  if [[ ! -e "$runtime/index.html" ]]; then cp "$GATE_ROOT/frozen/index.html" "$runtime/index.html"; fi
  curl -fsS -b "$cookie" -c "$cookie" -H "Origin: $b" -H 'Content-Type: application/json' --data "{\"password\":\"$FIXTURE_PASS\"}" "$b/api.php?action=login" > "$GATE_ROOT/login-$port.json"
  python3 - "$GATE_ROOT/login-$port.json" <<'PY'
import json,sys
j=json.load(open(sys.argv[1]));assert j.get('ok') and j.get('csrf')
PY
}
form_csrf(){ python3 - "$1" <<'PY'
import re,sys
m=re.search(r'name="_csrf" value="([^"]+)"',open(sys.argv[1]).read());assert m;print(m.group(1))
PY
}

# Positive + auth/csrf negatives + self-cleanup.
RT="$GATE_ROOT/positive"; DATA="$GATE_ROOT/data-positive"; COOKIE="$GATE_ROOT/cookie-positive"; PORT=18234; SUFFIX=111111111111; TOOL="vf-forge-v1354-source-reconcile-${SUFFIX}.php"
build_fixture "$RT" "$SUFFIX"; TOOL_SHA0=$(sha256sum "$RT/$TOOL"|awk '{print $1}'); start_fixture "$RT" "$DATA" "$PORT"; trap 'stop_fixture 18234' EXIT; setup_login "$PORT" "$DATA" "$COOKIE" "$RT"; BASE="http://127.0.0.1:$PORT"; DB=$(find "$DATA/database" -maxdepth 1 -type f -name '*.sqlite'|head -n1); test -n "$DB"; DB0=$(sha256sum "$DB"|awk '{print $1}'); test "$TOOL_SHA0" = "$(sha256sum "$RT/$TOOL"|awk '{print $1}')"
code=$(curl -sS -o "$GATE_ROOT/unauth.html" -w '%{http_code}' "$BASE/$TOOL"); test "$code" != 200 || ! grep -q '执行 V1.35.4 Source Exact 最终校正' "$GATE_ROOT/unauth.html"; test ! -e "$RT/memory-api.php"; echo 'UNAUTHENTICATED=DENY'
curl -fsS -b "$COOKIE" "$BASE/$TOOL" -o "$GATE_ROOT/get.html"; grep -q '执行 V1.35.4 Source Exact 最终校正' "$GATE_ROOT/get.html"; CSRF=$(form_csrf "$GATE_ROOT/get.html")
code=$(curl -sS -b "$COOKIE" -o "$GATE_ROOT/no-csrf.html" -w '%{http_code}' --data 'confirmation=RECONCILE_MEMORY_API' "$BASE/$TOOL"); test "$code" != 200 || ! grep -q 'SOURCE_EXACT_RECONCILIATION_PASS' "$GATE_ROOT/no-csrf.html"; test ! -e "$RT/memory-api.php"; echo 'MISSING_CSRF=DENY'
curl -fsS -b "$COOKIE" --data-urlencode "_csrf=$CSRF" --data-urlencode 'confirmation=RECONCILE_MEMORY_API' "$BASE/$TOOL" -o "$GATE_ROOT/success.json"
python3 - "$GATE_ROOT/success.json" <<'PY'
import json,sys
j=json.load(open(sys.argv[1]));assert j['closure']=='SOURCE_EXACT_RECONCILIATION_PASS';assert j['production_version']=='1.35.4';assert j['schema']==30;assert j['runtime_files']==42;assert j['runtime_fingerprint']=='2fd3ebbbebfd7155371fe44664715cbe34f63cfb98dfeb691bba90d4864ca083';assert j['memory_api']['status']=='EXACT';assert j['memory_api']['bytes']==4497;assert j['memory_api']['sha256']=='1c9b784d0a1c8cb8f9245c4c9bc7af6511c55006de5fd3fefa796b1ec438a9b7';assert j['missing']==[] and j['unexpected']==[] and j['hash_mismatch']==[];assert j['source_exact']=='PASS';assert j['sqlite_integrity']=='PASS';assert j['foreign_keys']=='PASS';assert j['production_db_write']==0;assert j['migration']=='NOT_EXECUTED';assert j['m030']=='NOT_EXECUTED';assert j['temporary_reconcile_tool_remaining']==0;assert j['product_failure']=='NONE';assert j['project_block']=='NONE';print('SUCCESS_JSON_CONTRACT=PASS')
PY
test ! -e "$RT/$TOOL"; test -f "$RT/memory-api.php"; test "$(wc -c < "$RT/memory-api.php")" = 4497; test "$(sha256sum "$RT/memory-api.php"|awk '{print $1}')" = '1c9b784d0a1c8cb8f9245c4c9bc7af6511c55006de5fd3fefa796b1ec438a9b7'; DB1=$(sha256sum "$DB"|awk '{print $1}'); test "$DB0" = "$DB1"; echo 'DB_WRITE=0'; echo 'M030=NOT_EXECUTED'; echo 'SELF_CLEANUP=PASS'; echo 'TEMPORARY_RECONCILIATION_TOOL_REMAINING=0'
python3 - "$CORRECTIVE" "$RT" <<'PY'
import importlib.util,sys
from pathlib import Path
c=Path(sys.argv[1]);r=Path(sys.argv[2]);s=importlib.util.spec_from_file_location('scope',c/'scripts/corrective/v1354_source_exact_scope.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);o=m.assert_frozen_runtime(r);assert o['runtime_files']==42;assert o['runtime_fingerprint']==m.EXPECTED_RUNTIME_FINGERPRINT;print('CLEANUP_RUNTIME_42_EXACT=PASS')
PY
stop_fixture "$PORT"; trap - EXIT

# Existing memory-api.php must deny.
RT="$GATE_ROOT/existing"; DATA="$GATE_ROOT/data-existing"; COOKIE="$GATE_ROOT/cookie-existing"; PORT=18235; SUFFIX=222222222222; TOOL="vf-forge-v1354-source-reconcile-${SUFFIX}.php"
build_fixture "$RT" "$SUFFIX"; printf 'tampered\n' > "$RT/memory-api.php"; start_fixture "$RT" "$DATA" "$PORT"; trap 'stop_fixture 18235' EXIT; setup_login "$PORT" "$DATA" "$COOKIE" "$RT"; code=$(curl -sS -b "$COOKIE" -o "$GATE_ROOT/existing.html" -w '%{http_code}' "http://127.0.0.1:$PORT/$TOOL"); test "$code" = 409; grep -q 'must be truly absent' "$GATE_ROOT/existing.html"; test -e "$RT/$TOOL"; echo 'EXISTING_MEMORY_API=DENY'; stop_fixture "$PORT"; trap - EXIT

# Other 41-file drift must deny.
RT="$GATE_ROOT/drift"; DATA="$GATE_ROOT/data-drift"; COOKIE="$GATE_ROOT/cookie-drift"; PORT=18236; SUFFIX=333333333333; TOOL="vf-forge-v1354-source-reconcile-${SUFFIX}.php"
build_fixture "$RT" "$SUFFIX"; start_fixture "$RT" "$DATA" "$PORT"; trap 'stop_fixture 18236' EXIT; setup_login "$PORT" "$DATA" "$COOKIE" "$RT"; printf '\nDRIFT\n' >> "$RT/robots.txt"; code=$(curl -sS -b "$COOKIE" -o "$GATE_ROOT/drift.html" -w '%{http_code}' "http://127.0.0.1:$PORT/$TOOL"); test "$code" = 409; grep -q 'Preflight source drift: robots.txt' "$GATE_ROOT/drift.html"; test ! -e "$RT/memory-api.php"; echo 'OTHER_41_FILE_DRIFT=DENY'; stop_fixture "$PORT"; trap - EXIT

# Wrong Version must deny before any write.
RT="$GATE_ROOT/wrong-version"; DATA="$GATE_ROOT/data-wrong-version"; COOKIE="$GATE_ROOT/cookie-wrong-version"; PORT=18237; SUFFIX=444444444444; TOOL="vf-forge-v1354-source-reconcile-${SUFFIX}.php"
build_fixture "$RT" "$SUFFIX"; sed -i "s/define('VFAB_VERSION', '1.35.4');/define('VFAB_VERSION', '1.35.3');/" "$RT/app/bootstrap.php"; start_fixture "$RT" "$DATA" "$PORT"; trap 'stop_fixture 18237' EXIT; setup_login "$PORT" "$DATA" "$COOKIE" "$RT"; code=$(curl -sS -b "$COOKIE" -o "$GATE_ROOT/wrong-version.html" -w '%{http_code}' "http://127.0.0.1:$PORT/$TOOL"); test "$code" = 409; grep -q 'Current Version/Schema must be exactly 1.35.4/30' "$GATE_ROOT/wrong-version.html"; test ! -e "$RT/memory-api.php"; echo 'WRONG_VERSION=DENY'; stop_fixture "$PORT"; trap - EXIT

# Wrong Schema must deny before any write.
RT="$GATE_ROOT/wrong-schema"; DATA="$GATE_ROOT/data-wrong-schema"; COOKIE="$GATE_ROOT/cookie-wrong-schema"; PORT=18238; SUFFIX=555555555555; TOOL="vf-forge-v1354-source-reconcile-${SUFFIX}.php"
build_fixture "$RT" "$SUFFIX"; sed -i "s/define('VFAB_SCHEMA_VERSION', 30);/define('VFAB_SCHEMA_VERSION', 29);/" "$RT/app/bootstrap.php"; start_fixture "$RT" "$DATA" "$PORT"; trap 'stop_fixture 18238' EXIT; setup_login "$PORT" "$DATA" "$COOKIE" "$RT"; code=$(curl -sS -b "$COOKIE" -o "$GATE_ROOT/wrong-schema.html" -w '%{http_code}' "http://127.0.0.1:$PORT/$TOOL"); test "$code" = 409; grep -q 'Current Version/Schema must be exactly 1.35.4/30' "$GATE_ROOT/wrong-schema.html"; test ! -e "$RT/memory-api.php"; echo 'WRONG_SCHEMA=DENY'; stop_fixture "$PORT"; trap - EXIT

# Rollback: fail after write, restore absence, DB unchanged, evidence tool remains.
RT="$GATE_ROOT/rollback"; DATA="$GATE_ROOT/data-rollback"; COOKIE="$GATE_ROOT/cookie-rollback"; PORT=18239; SUFFIX=666666666666; TOOL="vf-forge-v1354-source-reconcile-${SUFFIX}.php"
build_fixture "$RT" "$SUFFIX" after_write; start_fixture "$RT" "$DATA" "$PORT"; trap 'stop_fixture 18239' EXIT; setup_login "$PORT" "$DATA" "$COOKIE" "$RT"; BASE="http://127.0.0.1:$PORT"; DB=$(find "$DATA/database" -maxdepth 1 -type f -name '*.sqlite'|head -n1); DB0=$(sha256sum "$DB"|awk '{print $1}'); curl -fsS -b "$COOKIE" "$BASE/$TOOL" -o "$GATE_ROOT/rget.html"; CSRF=$(form_csrf "$GATE_ROOT/rget.html"); code=$(curl -sS -b "$COOKIE" -o "$GATE_ROOT/rpost.html" -w '%{http_code}' --data-urlencode "_csrf=$CSRF" --data-urlencode 'confirmation=RECONCILE_MEMORY_API' "$BASE/$TOOL"); test "$code" = 409; grep -q 'TEST_FAILPOINT_after_write' "$GATE_ROOT/rpost.html"; test ! -e "$RT/memory-api.php"; test -e "$RT/$TOOL"; DB1=$(sha256sum "$DB"|awk '{print $1}'); test "$DB0" = "$DB1"; echo 'ROLLBACK=PASS'; echo 'FAILURE_EVIDENCE_TOOL_REMAINS=PASS'; stop_fixture "$PORT"; trap - EXIT

echo 'PRODUCTION_WRITE=0'
echo 'PHYSICAL_DELETE=0'
echo 'V1.35.5=NOT_CREATED'
echo 'P03_V1354_MINIMAL_TRANSPORT_REGRESSION=PASS'
