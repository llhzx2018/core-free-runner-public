#!/usr/bin/env bash
set -Eeuo pipefail
: "${GATE_ROOT:=/tmp/p03-v1354-cleanup}"
: "${FIXTURE_PASS:=VfP03-Cleanup-2026!}"
: "${PHP_TEST_IMAGE:?PHP_TEST_IMAGE is required}"

rm -rf "$GATE_ROOT"
mkdir -p "$GATE_ROOT"
CORRECTIVE="$GITHUB_WORKSPACE/corrective"
PRODUCT="$GITHUB_WORKSPACE/product"
WRITER="vf-forge-v1354-source-reconcile-1ec8566c6838.php"
WRITER_SHA="b9a41499d33d1b5dddc0b9fd2ddc43a324aa9378da8336ef34cab183fa0dc18d"
FORENSIC="vf-forge-v1354-source-forensic-3dc194b1768a.php"
FORENSIC_SHA="b0024ea1d8b12f0d89a4bc9163c82139f46d5b7bd3c9ad57e978d910f73b928f"
CLEANUP="vf-forge-v1354-temporary-tool-cleanup-aaaaaaaaaaaa.php"

python3 "$PRODUCT/scripts/build_runtime.py" "$GATE_ROOT/frozen" >/dev/null
python3 - "$CORRECTIVE" "$GATE_ROOT/frozen" <<'PY'
import importlib.util,sys
from pathlib import Path
c=Path(sys.argv[1]); r=Path(sys.argv[2])
s=importlib.util.spec_from_file_location('scope',c/'scripts/corrective/v1354_source_exact_scope.py')
m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
o=m.assert_frozen_runtime(r)
assert o['runtime_files']==42
assert o['runtime_fingerprint']=='2fd3ebbbebfd7155371fe44664715cbe34f63cfb98dfeb691bba90d4864ca083'
assert o['source_manifest_sha256']=='07103a75ce7841cb2ede11cd30a822830cf255f991195eb05391282e6e50ec47'
assert o['memory_api_bytes']==4497
assert o['memory_api_sha256']=='1c9b784d0a1c8cb8f9245c4c9bc7af6511c55006de5fd3fefa796b1ec438a9b7'
print('FROZEN_IDENTITY=PASS')
PY

build_tools(){
  local runtime="$1"
  python3 "$CORRECTIVE/scripts/corrective/finalize_v1354_same_version_reconcile_production.py" \
    --runtime-root "$GATE_ROOT/frozen" --output-dir "$runtime" --filename "$WRITER" > "$runtime/.writer.json"
  test "$(sha256sum "$runtime/$WRITER" | awk '{print $1}')" = "$WRITER_SHA"

  python3 "$CORRECTIVE/scripts/corrective/finalize_v1354_source_forensic_probe.py" \
    --runtime-root "$GATE_ROOT/frozen" --output-dir "$runtime" --filename "$FORENSIC" > "$runtime/.forensic.json"
  test "$(sha256sum "$runtime/$FORENSIC" | awk '{print $1}')" = "$FORENSIC_SHA"

  python3 "$CORRECTIVE/scripts/corrective/finalize_v1354_temporary_tool_cleanup.py" \
    --runtime-root "$GATE_ROOT/frozen" --output-dir "$runtime" --filename "$CLEANUP" > "$runtime/.cleanup.json"
  python3 - "$runtime/.cleanup.json" "$runtime/$CLEANUP" <<'PY'
import hashlib,json,re,sys
from pathlib import Path
m=json.load(open(sys.argv[1])); p=Path(sys.argv[2]); raw=p.read_bytes()
assert m['filename']==p.name
assert re.fullmatch(r'vf-forge-v1354-temporary-tool-cleanup-[0-9a-f]{12}\.php',p.name)
assert m['bytes']==len(raw) and m['sha256']==hashlib.sha256(raw).hexdigest()
assert m['product_version']=='1.35.4' and m['schema']==30
assert m['runtime_files']==42
assert m['runtime_fingerprint']=='2fd3ebbbebfd7155371fe44664715cbe34f63cfb98dfeb691bba90d4864ca083'
assert m['targets']['vf-forge-v1354-source-reconcile-1ec8566c6838.php']=='b9a41499d33d1b5dddc0b9fd2ddc43a324aa9378da8336ef34cab183fa0dc18d'
assert m['targets']['vf-forge-v1354-source-forensic-3dc194b1768a.php']=='b0024ea1d8b12f0d89a4bc9163c82139f46d5b7bd3c9ad57e978d910f73b928f'
assert m['allowed_writes']==['unlink_exact_temporary_targets','unlink_self']
assert m['product_runtime_write']==0 and m['memory_api_write']==0 and m['db_write']==0 and m['provider_write']==0 and m['migration']==0
assert m['m030']=='NOT_RERUN'
print('CLEANUP_BUILD_IDENTITY=PASS')
PY

  docker run --rm -v "$runtime:/app:ro" -w /app "$PHP_TEST_IMAGE" php -l "$CLEANUP" >/dev/null
  echo 'PHP_SYNTAX=PASS'

  python3 - "$runtime/$CLEANUP" <<'PY'
from pathlib import Path
import base64,json,re,sys
text=Path(sys.argv[1]).read_text()
for token in [
    'file_put_contents','fopen(','rename(','copy(','mkdir(','chmod(','touch(',
    'vfab_require_admin(','vfab_require_csrf(','vfab_csrf_token(','vfab_db(',
    'PDO','sqlite:','PRAGMA','admin_sessions','BackupService','MigrationRunner'
]:
    assert token not in text, f'BANNED_WRITE_OR_DB_TOKEN:{token}'
assert not re.search(r"['\"]\s*(UPDATE|INSERT|DELETE|ALTER|CREATE|DROP|REPLACE)\b",text,re.I), 'SQL_WRITE_TOKEN'
assert text.count('unlink(')==2, f'UNLINK_CALL_COUNT:{text.count("unlink(")}'
assert 'session_abort()' in text
assert 'vftc_same_origin()' in text
assert "CSRF_FAILED" in text
assert "TARGET_SHA_MISMATCH" in text
assert "TARGET_PATH_INVALID" in text
assert "is_link($path)" in text
assert 'FROZEN_RUNTIME_SOURCE_NOT_EXACT' in text
assert 'MEMORY_API_NOT_CANONICAL_EXACT' in text
payload_match=re.search(r"const VFTC_PAYLOAD='([^']+)';",text); assert payload_match
payload=json.loads(base64.b64decode(payload_match.group(1),validate=True))
assert payload['memory_api_bytes']==4497
assert payload['memory_api_sha256']=='1c9b784d0a1c8cb8f9245c4c9bc7af6511c55006de5fd3fefa796b1ec438a9b7'
assert payload['targets']['vf-forge-v1354-source-reconcile-1ec8566c6838.php']=='b9a41499d33d1b5dddc0b9fd2ddc43a324aa9378da8336ef34cab183fa0dc18d'
assert payload['targets']['vf-forge-v1354-source-forensic-3dc194b1768a.php']=='b0024ea1d8b12f0d89a4bc9163c82139f46d5b7bd3c9ad57e978d910f73b928f'
assert payload['runtime_files']==42
assert payload['runtime_fingerprint']=='2fd3ebbbebfd7155371fe44664715cbe34f63cfb98dfeb691bba90d4864ca083'
assert payload['source_manifest_sha256']=='07103a75ce7841cb2ede11cd30a822830cf255f991195eb05391282e6e50ec47'
print('FAIL_CLOSED_STATIC=PASS')
print('NO_SQLITE_OPEN=PASS')
print('ONLY_ALLOWED_UNLINK_WRITES=PASS')
PY
}

start_fixture(){
  local runtime="$1" data="$2" port="$3"
  local name="p03-v1354-cleanup-$port"
  mkdir -p "$data"
  docker rm -f "$name" >/dev/null 2>&1 || true
  docker run -d --rm --name "$name" -p "$port:$port" \
    -v "$runtime:/app" -v "$data:$data" -w /app "$PHP_TEST_IMAGE" \
    php -d session.gc_probability=0 -S "0.0.0.0:$port" -t /app >/dev/null
  local ok=0
  for _ in $(seq 1 120); do
    if curl -fsS "http://127.0.0.1:$port/setup.php" >/dev/null 2>&1; then ok=1; break; fi
    sleep .2
  done
  if [[ "$ok" != 1 ]]; then docker logs "$name"; return 1; fi
}
stop_fixture(){ docker rm -f "p03-v1354-cleanup-$1" >/dev/null 2>&1 || true; }

setup_login(){
  local port="$1" data="$2" cookie="$3" runtime="$4"
  local base="http://127.0.0.1:$port"
  curl -fsS -c "$cookie" "$base/setup.php" -o "$GATE_ROOT/setup-$port.html"
  local setup_csrf
  setup_csrf=$(python3 - "$GATE_ROOT/setup-$port.html" <<'PY'
import re,sys
m=re.search(r'name="setup_csrf" value="([^"]+)"',open(sys.argv[1]).read()); assert m; print(m.group(1))
PY
)
  curl -fsS -i -b "$cookie" -c "$cookie" -H "Origin: $base" \
    --data-urlencode "setup_csrf=$setup_csrf" \
    --data-urlencode 'site_title=VF Forge Cleanup Fixture' \
    --data-urlencode "data_root=$data" \
    --data-urlencode "password=$FIXTURE_PASS" \
    --data-urlencode "password_confirm=$FIXTURE_PASS" \
    "$base/setup.php" > "$GATE_ROOT/setup-post-$port.txt"
  grep -Eq '^HTTP/.* 302|^HTTP/.* 303' "$GATE_ROOT/setup-post-$port.txt"
  if [[ ! -e "$runtime/index.html" ]]; then cp "$GATE_ROOT/frozen/index.html" "$runtime/index.html"; fi
  curl -fsS -b "$cookie" -c "$cookie" -H "Origin: $base" -H 'Content-Type: application/json' \
    --data "{\"password\":\"$FIXTURE_PASS\"}" "$base/api.php?action=login" > "$GATE_ROOT/login-$port.json"
  python3 - "$GATE_ROOT/login-$port.json" <<'PY'
import json,sys
j=json.load(open(sys.argv[1])); assert j.get('ok') and j.get('csrf')
print(j['csrf'])
PY
}

db_state(){
  local port="$1" name="p03-v1354-cleanup-$1"
  docker exec "$name" php -r '
  $r=include "/app/app/.runtime.php";$p=(string)($r["db_file"]??"");if($p===""||!is_file($p)){exit(2);} $paths=["db"=>$p,"wal"=>$p."-wal","shm"=>$p."-shm","journal"=>$p."-journal"]; $o=[];foreach($paths as $k=>$f){if(!file_exists($f)){$o[$k]=null;continue;}if(!is_file($f)||is_link($f)){exit(3);} $o[$k]=["bytes"=>filesize($f),"sha256"=>hash_file("sha256",$f)];}ksort($o);echo json_encode($o,JSON_UNESCAPED_SLASHES);'
}
assert_db_state_unchanged(){ local port="$1" before="$2"; test "$before" = "$(db_state "$port")"; }

prepare_case(){
  local label="$1"
  local runtime="$GATE_ROOT/$label"
  rm -rf "$runtime"
  cp -a "$GATE_ROOT/frozen" "$runtime"
  build_tools "$runtime"
}

assert_all_tools_present(){
  local runtime="$1"
  test -f "$runtime/$WRITER" && test ! -L "$runtime/$WRITER"
  test -f "$runtime/$FORENSIC" && test ! -L "$runtime/$FORENSIC"
  test -f "$runtime/$CLEANUP" && test ! -L "$runtime/$CLEANUP"
}

run_success_case(){
  local label=success port=18451 runtime="$GATE_ROOT/success" data="$GATE_ROOT/data-success" cookie="$GATE_ROOT/cookie-success"
  prepare_case "$label"
  start_fixture "$runtime" "$data" "$port"
  trap "stop_fixture $port" RETURN
  local csrf
  csrf=$(setup_login "$port" "$data" "$cookie" "$runtime" | tail -n1)
  local base="http://127.0.0.1:$port" baseline code form_csrf
  baseline=$(db_state "$port")
  assert_all_tools_present "$runtime"

  code=$(curl -sS -o "$GATE_ROOT/success-unauth.json" -w '%{http_code}' "$base/$CLEANUP")
  test "$code" = 401
  python3 - "$GATE_ROOT/success-unauth.json" <<'PY'
import json,sys
j=json.load(open(sys.argv[1])); assert j['ok'] is False and j['code']=='AUTH_REQUIRED'; assert j['production_db_write']==0 and j['product_runtime_write']==0
PY
  assert_all_tools_present "$runtime"
  assert_db_state_unchanged "$port" "$baseline"
  echo 'UNAUTHENTICATED=DENY_PASS'

  curl -fsS -b "$cookie" "$base/$CLEANUP" -o "$GATE_ROOT/success-get.html"
  grep -q 'Preflight PASS' "$GATE_ROOT/success-get.html"
  form_csrf=$(python3 - "$GATE_ROOT/success-get.html" <<'PY'
import re,sys
m=re.search(r'name="_csrf" value="([^"]+)"',open(sys.argv[1]).read()); assert m; print(m.group(1))
PY
)
  test "$form_csrf" = "$csrf"
  assert_all_tools_present "$runtime"
  assert_db_state_unchanged "$port" "$baseline"
  echo 'ADMIN_AUTHENTICATION=PASS'
  echo 'CLEANUP_GET_PREFLIGHT=PASS'
  echo 'DB_PRIMARY_UNCHANGED_AFTER_GET=PASS'
  echo 'DB_SIDECARS_UNCHANGED_AFTER_GET=PASS'

  code=$(curl -sS -b "$cookie" -H "Origin: $base" -o "$GATE_ROOT/success-bad-csrf.json" -w '%{http_code}' \
    --data-urlencode '_csrf=definitely-wrong' --data-urlencode 'action=cleanup' "$base/$CLEANUP")
  test "$code" = 419
  python3 - "$GATE_ROOT/success-bad-csrf.json" <<'PY'
import json,sys
j=json.load(open(sys.argv[1])); assert j['ok'] is False and j['code']=='CSRF_FAILED'; assert j['production_db_write']==0 and j['product_runtime_write']==0
PY
  assert_all_tools_present "$runtime"
  assert_db_state_unchanged "$port" "$baseline"
  echo 'CSRF_FAIL_CLOSED=PASS'

  curl -fsS -b "$cookie" -H "Origin: $base" \
    --data-urlencode "_csrf=$form_csrf" --data-urlencode 'action=cleanup' \
    "$base/$CLEANUP" -o "$GATE_ROOT/success.json"
  python3 - "$GATE_ROOT/success.json" <<'PY'
import json,sys
j=json.load(open(sys.argv[1]))
assert j['ok'] is True and j['closure']=='TEMPORARY_TOOL_CLEANUP_PASS'
assert j['production_version']=='1.35.4' and j['schema']==30
assert j['temporary_writer_remaining']==0
assert j['temporary_forensic_probe_remaining']==0
assert j['cleanup_tool_remaining']==0
assert j['production_runtime_managed_files']==42
assert j['runtime_fingerprint']=='2fd3ebbbebfd7155371fe44664715cbe34f63cfb98dfeb691bba90d4864ca083'
assert j['runtime_fingerprint']==j['runtime_fingerprint_expected']
assert j['source_manifest_sha256']=='07103a75ce7841cb2ede11cd30a822830cf255f991195eb05391282e6e50ec47'
assert j['source_exact']=='PASS'
assert j['memory_api']['status']=='CANONICAL_EXACT'
assert j['memory_api']['bytes']==4497
assert j['memory_api']['sha256']=='1c9b784d0a1c8cb8f9245c4c9bc7af6511c55006de5fd3fefa796b1ec438a9b7'
assert j['product_runtime_write']==0 and j['memory_api_write']==0 and j['production_db_write']==0 and j['provider_write']==0
assert j['migration']=='NOT_EXECUTED' and j['m030']=='NOT_RERUN' and j['self_cleanup']=='PASS'
assert sorted(j['deleted'])==sorted(['vf-forge-v1354-source-reconcile-1ec8566c6838.php','vf-forge-v1354-source-forensic-3dc194b1768a.php'])
print('SUCCESS_JSON=PASS')
PY
  test ! -e "$runtime/$WRITER" && test ! -L "$runtime/$WRITER"
  test ! -e "$runtime/$FORENSIC" && test ! -L "$runtime/$FORENSIC"
  test ! -e "$runtime/$CLEANUP" && test ! -L "$runtime/$CLEANUP"
  assert_db_state_unchanged "$port" "$baseline"
  test "$(sha256sum "$runtime/memory-api.php" | awk '{print $1}')" = '1c9b784d0a1c8cb8f9245c4c9bc7af6511c55006de5fd3fefa796b1ec438a9b7'
  echo 'TEMPORARY_WRITER_REMAINING=0'
  echo 'TEMPORARY_FORENSIC_PROBE_REMAINING=0'
  echo 'CLEANUP_TOOL_REMAINING=0'
  echo 'DB_PRIMARY_UNCHANGED=PASS'
  echo 'DB_SIDECARS_UNCHANGED=PASS'
  echo 'SOURCE_EXACT_AFTER_CLEANUP=PASS'
  stop_fixture "$port"; trap - RETURN
}

run_fail_case(){
  local label="$1" port="$2" mutation="$3" expected_error="$4"
  local runtime="$GATE_ROOT/$label" data="$GATE_ROOT/data-$label" cookie="$GATE_ROOT/cookie-$label"
  prepare_case "$label"
  start_fixture "$runtime" "$data" "$port"
  trap "stop_fixture $port" RETURN
  setup_login "$port" "$data" "$cookie" "$runtime" >/dev/null
  local base="http://127.0.0.1:$port" baseline code
  baseline=$(db_state "$port")
  case "$mutation" in
    writer_sha) printf '\nTAMPER\n' >> "$runtime/$WRITER" ;;
    forensic_symlink) rm -f "$runtime/$FORENSIC"; ln -s robots.txt "$runtime/$FORENSIC" ;;
    runtime_drift) printf '\nDRIFT\n' >> "$runtime/robots.txt" ;;
    version_mismatch) python3 - "$runtime/app/bootstrap.php" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); s=p.read_text(); old="define('VFAB_VERSION', '1.35.4');"; assert s.count(old)==1; p.write_text(s.replace(old,"define('VFAB_VERSION', '1.35.99');",1))
PY
      ;;
    *) return 9 ;;
  esac
  code=$(curl -sS -b "$cookie" -o "$GATE_ROOT/$label.json" -w '%{http_code}' "$base/$CLEANUP")
  test "$code" = 409
  python3 - "$GATE_ROOT/$label.json" "$expected_error" <<'PY'
import json,sys
j=json.load(open(sys.argv[1])); needle=sys.argv[2]
assert j['ok'] is False and j['closure']=='TEMPORARY_TOOL_CLEANUP_BLOCKED'
assert needle in j['error'], (needle,j['error'])
assert j['product_runtime_write']==0 and j['memory_api_write']==0 and j['production_db_write']==0 and j['provider_write']==0
assert j['migration']=='NOT_EXECUTED' and j['m030']=='NOT_RERUN'
PY
  test -f "$runtime/$WRITER" || test "$mutation" = forensic_symlink
  if [[ "$mutation" == forensic_symlink ]]; then test -L "$runtime/$FORENSIC"; else test -e "$runtime/$FORENSIC"; fi
  test -f "$runtime/$CLEANUP"
  assert_db_state_unchanged "$port" "$baseline"
  echo "$label=PASS"
  stop_fixture "$port"; trap - RETURN
}

run_success_case
run_fail_case fail-target-sha 18452 writer_sha 'TARGET_SHA_MISMATCH'
run_fail_case fail-symlink 18453 forensic_symlink 'TARGET_IDENTITY_INVALID'
run_fail_case fail-runtime-drift 18454 runtime_drift 'FROZEN_RUNTIME_SOURCE_NOT_EXACT'
run_fail_case fail-version 18455 version_mismatch 'PRODUCTION_VERSION_SCHEMA_MISMATCH'

echo 'FAIL_CLOSED_TARGET_SHA=PASS'
echo 'FAIL_CLOSED_SYMLINK=PASS'
echo 'FAIL_CLOSED_RUNTIME_DRIFT=PASS'
echo 'FAIL_CLOSED_VERSION_MISMATCH=PASS'
echo 'PRODUCT_RUNTIME_WRITE=0'
echo 'MEMORY_API_WRITE=0'
echo 'PRODUCTION_DB_WRITE=0'
echo 'PROVIDER_WRITE=0'
echo 'MIGRATION=NOT_EXECUTED'
echo 'M030=NOT_RERUN'
echo 'TEMPORARY_TOOL_CLEANUP_MINIMAL_GATE=PASS'
