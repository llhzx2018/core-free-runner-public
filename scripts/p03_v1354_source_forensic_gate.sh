#!/usr/bin/env bash
set -Eeuo pipefail
: "${GATE_ROOT:=/tmp/p03-v1354-forensic}"
: "${FIXTURE_PASS:=VfP03-Forensic-2026!}"
: "${PHP_TEST_IMAGE:?PHP_TEST_IMAGE is required}"

rm -rf "$GATE_ROOT"
mkdir -p "$GATE_ROOT"
CORRECTIVE="$GITHUB_WORKSPACE/corrective"
PRODUCT="$GITHUB_WORKSPACE/product"

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

build_probe(){
  local runtime="$1" suffix="$2"
  local name="vf-forge-v1354-source-forensic-${suffix}.php"
  python3 "$CORRECTIVE/scripts/corrective/build_v1354_source_forensic_probe.py" \
    --runtime-root "$GATE_ROOT/frozen" --output-dir "$runtime" --filename "$name" > "$runtime/.forensic-build.json"
  python3 - "$runtime/.forensic-build.json" "$runtime/$name" <<'PY'
import hashlib,json,re,sys
from pathlib import Path
m=json.load(open(sys.argv[1])); p=Path(sys.argv[2]); raw=p.read_bytes()
assert re.fullmatch(r'vf-forge-v1354-source-forensic-[0-9a-f]{12}\.php',p.name)
assert m['filename']==p.name
assert m['bytes']==len(raw)
assert m['sha256']==hashlib.sha256(raw).hexdigest()
assert m['get_only'] is True
assert m['csrf']=='NOT_APPLICABLE'
assert m['self_cleanup'] is False
assert m['production_write']==0 and m['db_write']==0 and m['provider_write']==0 and m['migration']==0
assert m['runtime_files']==42
assert m['runtime_fingerprint']=='2fd3ebbbebfd7155371fe44664715cbe34f63cfb98dfeb691bba90d4864ca083'
assert m['memory_api_bytes']==4497
assert m['memory_api_sha256']=='1c9b784d0a1c8cb8f9245c4c9bc7af6511c55006de5fd3fefa796b1ec438a9b7'
print('PROBE_BUILD_IDENTITY=PASS')
PY
  docker run --rm -v "$runtime:/app:ro" -w /app "$PHP_TEST_IMAGE" php -l "$name" >/dev/null
  echo 'PHP_SYNTAX=PASS'
  python3 - "$runtime/$name" <<'PY'
from pathlib import Path
import re,sys
text=Path(sys.argv[1]).read_text()
banned=[
 'file_put_contents','fopen(','rename(','unlink(','copy(','mkdir(','chmod(','touch(',
 'vfab_require_admin(','vfab_require_csrf(','vfab_csrf_token(','vfab_db(',
 'Backup','Recovery Create'
]
for token in banned:
    assert token not in text, f'BANNED_WRITE_TOKEN:{token}'
for sql in [r"['\"]\s*(UPDATE|INSERT|DELETE|ALTER|CREATE|DROP|REPLACE)\b"]:
    assert not re.search(sql,text,re.I), 'SQL_WRITE_TOKEN'
assert "REQUEST_METHOD']??'GET')!=='GET'" in text
assert "'METHOD_NOT_ALLOWED'" in text
assert "PRAGMA query_only=ON" in text
assert "PRAGMA integrity_check" in text
assert "PRAGMA foreign_key_check" in text
assert 'session_abort()' in text
print('GET_ONLY_STATIC=PASS')
print('NO_POST_HANDLER=PASS')
print('NO_CSRF_REQUIREMENT=PASS')
print('NO_WRITE_STATIC_SCAN=PASS')
PY
}

start_fixture(){
  local runtime="$1" data="$2" port="$3"
  local name="p03-v1354-forensic-$port"
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
stop_fixture(){ docker rm -f "p03-v1354-forensic-$1" >/dev/null 2>&1 || true; }

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
    --data-urlencode 'site_title=VF Forge Forensic Fixture' \
    --data-urlencode "data_root=$data" \
    --data-urlencode "password=$FIXTURE_PASS" \
    --data-urlencode "password_confirm=$FIXTURE_PASS" \
    "$base/setup.php" > "$GATE_ROOT/setup-post-$port.txt"
  grep -Eq '^HTTP/.* 302|^HTTP/.* 303' "$GATE_ROOT/setup-post-$port.txt"
  # setup.php intentionally removes bootstrap index.html; restore exact frozen runtime fixture.
  if [[ ! -e "$runtime/index.html" ]]; then cp "$GATE_ROOT/frozen/index.html" "$runtime/index.html"; fi
  curl -fsS -b "$cookie" -c "$cookie" -H "Origin: $base" -H 'Content-Type: application/json' \
    --data "{\"password\":\"$FIXTURE_PASS\"}" "$base/api.php?action=login" > "$GATE_ROOT/login-$port.json"
  python3 - "$GATE_ROOT/login-$port.json" <<'PY'
import json,sys
j=json.load(open(sys.argv[1])); assert j.get('ok') and j.get('csrf')
PY
}

db_path(){ find "$1/database" -maxdepth 1 -type f -name '*.sqlite' | head -n1; }
assert_db_unchanged(){ local db="$1" before="$2"; test -n "$db"; test "$before" = "$(sha256sum "$db"|awk '{print $1}')"; }

run_case(){
  local label="$1" port="$2" suffix="$3"
  local runtime="$GATE_ROOT/$label" data="$GATE_ROOT/data-$label" cookie="$GATE_ROOT/cookie-$label"
  rm -rf "$runtime"; cp -a "$GATE_ROOT/frozen" "$runtime"
  case "$label" in
    case-b) rm -f "$runtime/memory-api.php" ;;
    case-c) printf 'tampered-memory-api\n' > "$runtime/memory-api.php" ;;
    case-d) printf '\nFORENSIC_DRIFT\n' >> "$runtime/robots.txt" ;;
  esac
  build_probe "$runtime" "$suffix"
  local tool="vf-forge-v1354-source-forensic-${suffix}.php"
  start_fixture "$runtime" "$data" "$port"
  trap "stop_fixture $port" RETURN
  setup_login "$port" "$data" "$cookie" "$runtime"
  local base="http://127.0.0.1:$port" db db0
  db=$(db_path "$data"); test -n "$db"; db0=$(sha256sum "$db"|awk '{print $1}')

  # Authentication required: no cookie must be denied and remain read-only.
  local code
  code=$(curl -sS -o "$GATE_ROOT/$label-unauth.json" -w '%{http_code}' "$base/$tool")
  test "$code" = 401
  python3 - "$GATE_ROOT/$label-unauth.json" <<'PY'
import json,sys
j=json.load(open(sys.argv[1])); assert j['ok'] is False; assert j['code']=='AUTH_REQUIRED'; assert j['production_write']==0
PY
  assert_db_unchanged "$db" "$db0"
  echo "$label:UNAUTHENTICATED=DENY"

  # POST is categorically rejected; no CSRF path exists.
  code=$(curl -sS -b "$cookie" -o "$GATE_ROOT/$label-post.json" -w '%{http_code}' -X POST "$base/$tool")
  test "$code" = 405
  python3 - "$GATE_ROOT/$label-post.json" <<'PY'
import json,sys
j=json.load(open(sys.argv[1])); assert j['ok'] is False; assert j['code']=='METHOD_NOT_ALLOWED'; assert j['get_only'] is True; assert j['production_write']==0
PY
  assert_db_unchanged "$db" "$db0"
  echo "$label:POST=DENY"

  curl -fsS -b "$cookie" "$base/$tool" -o "$GATE_ROOT/$label.json"
  assert_db_unchanged "$db" "$db0"

  python3 - "$label" "$GATE_ROOT/$label.json" <<'PY'
import json,sys
label=sys.argv[1]; j=json.load(open(sys.argv[2]))
assert j['probe']=='READ_ONLY_SOURCE_STATE_DISCOVERY'
assert j['production_version']=='1.35.4' and j['schema']==30
assert j['runtime_files_expected']==42
assert j['runtime_fingerprint_expected']=='2fd3ebbbebfd7155371fe44664715cbe34f63cfb98dfeb691bba90d4864ca083'
assert j['memory_api']['expected_bytes']==4497
assert j['memory_api']['expected_sha256']=='1c9b784d0a1c8cb8f9245c4c9bc7af6511c55006de5fd3fefa796b1ec438a9b7'
assert j['sqlite_integrity']=='PASS' and j['foreign_keys']=='PASS'
assert j['database_state_unchanged'] is True
assert j['production_db_write']==0 and j['production_source_write']==0 and j['provider_write']==0
assert j['migration']=='NOT_EXECUTED' and j['m030']=='NOT_RERUN'
assert j['self_cleanup']=='NO' and j['temporary_probe_remaining']==1
assert j['admin_auth']=='READ_ONLY_VALIDATED'
if label=='case-a':
    assert j['ok'] is True and j['case']=='A' and j['classification']=='SOURCE_EXACT'
    assert j['memory_api']['exists'] is True and j['memory_api']['canonical_exact'] is True
    assert j['runtime_files_actual']==42
    assert j['runtime_fingerprint_actual']==j['runtime_fingerprint_expected']
    assert j['missing']==[] and j['unexpected']==[] and j['hash_mismatch']==[] and j['source_exact']=='PASS'
elif label=='case-b':
    assert j['ok'] is False and j['case']=='B' and j['classification']=='CANONICAL_MEMORY_API_ABSENT'
    assert j['memory_api']['exists'] is False and j['memory_api']['canonical_exact'] is False
    assert j['runtime_files_actual']==41 and 'memory-api.php' in j['missing'] and j['source_exact']=='FAIL'
elif label=='case-c':
    assert j['ok'] is False and j['case']=='C' and j['classification']=='EXISTING_MEMORY_API_DRIFT'
    assert j['memory_api']['exists'] is True and j['memory_api']['canonical_exact'] is False
    assert any(x['path']=='memory-api.php' for x in j['hash_mismatch']) and j['source_exact']=='FAIL'
elif label=='case-d':
    assert j['ok'] is False and j['case']=='D' and j['classification']=='OTHER_RUNTIME_DRIFT'
    assert j['memory_api']['canonical_exact'] is True
    assert any(x['path']=='robots.txt' for x in j['hash_mismatch']) and j['source_exact']=='FAIL'
print(label.upper()+'=PASS')
PY
  test -f "$runtime/$tool" # no self cleanup
  assert_db_unchanged "$db" "$db0"
  stop_fixture "$port"
  trap - RETURN
}

run_case case-a 18341 aaaaaaaaaaaa
run_case case-b 18342 bbbbbbbbbbbb
run_case case-c 18343 cccccccccccc
run_case case-d 18344 dddddddddddd

echo 'ADMIN_AUTHENTICATION=PASS'
echo 'GET_ONLY=PASS'
echo 'NO_POST=PASS'
echo 'NO_CSRF_REQUIREMENT=PASS'
echo 'NO_WRITE_STATIC_SCAN=PASS'
echo 'CASE_A_FIXTURE=PASS'
echo 'CASE_B_FIXTURE=PASS'
echo 'CASE_C_FIXTURE=PASS'
echo 'CASE_D_FIXTURE=PASS'
echo 'PRODUCTION_WRITE=0'
echo 'DB_WRITE=0'
echo 'PROVIDER_WRITE=0'
echo 'MIGRATION=NOT_EXECUTED'
echo 'M030=NOT_RERUN'
echo 'SELF_CLEANUP=NO'
echo 'FORENSIC_MINIMAL_GATE=PASS'
