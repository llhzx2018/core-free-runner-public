#!/usr/bin/env bash
set -Eeuo pipefail

SOURCE_VERSION='1.1.10'
TARGET_VERSION='1.1.11'
SOURCE_SHA256='16448869130988685c5fadb42f50362dfac08d6b2dd8657394b8a43c7787ba5d'
TARGET_SHA256='b24bbbeb997fa6414689a01b32eb70a7bf20c82ffeec8761fea4b69612629ce8'
PASSWORD='P05AtomicGate-2026-Strong'
BASE='https://github.com/llhzx2018/core-free-runner-public/releases/download'
WORK='/tmp/p05-atomic'
BUILDER='scripts/p05-v1111-standard-atomic-builder-bootstrap.py'

rm -rf "$WORK"
mkdir -p "$WORK/source" "$WORK/target"

for cmd in php python3 curl unzip jq sqlite3 sha256sum; do command -v "$cmd" >/dev/null; done
php -m | grep -Fx PDO >/dev/null
php -m | grep -Fi sqlite >/dev/null

echo 'P05_ATOMIC_PHASE=DOWNLOAD_EXACT_FORMAL_RELEASES'
curl -fsSL "$BASE/p05-dist-v${SOURCE_VERSION}/VF_SEO_V${SOURCE_VERSION}_FULL.zip" -o "$WORK/VF_SEO_V${SOURCE_VERSION}_FULL.zip"
curl -fsSL "$BASE/p05-dist-v${TARGET_VERSION}/VF_SEO_V${TARGET_VERSION}_FULL.zip" -o "$WORK/VF_SEO_V${TARGET_VERSION}_FULL.zip"
test "$(sha256sum "$WORK/VF_SEO_V${SOURCE_VERSION}_FULL.zip" | awk '{print $1}')" = "$SOURCE_SHA256"
test "$(sha256sum "$WORK/VF_SEO_V${TARGET_VERSION}_FULL.zip" | awk '{print $1}')" = "$TARGET_SHA256"
unzip -q "$WORK/VF_SEO_V${SOURCE_VERSION}_FULL.zip" -d "$WORK/source"
unzip -q "$WORK/VF_SEO_V${TARGET_VERSION}_FULL.zip" -d "$WORK/target"
test "$(cat "$WORK/source/VERSION")" = "$SOURCE_VERSION"
test "$(cat "$WORK/target/VERSION")" = "$TARGET_VERSION"
test ! -e "$WORK/source/VF_INSTALL_INSTANCE.json"
test ! -e "$WORK/target/VF_INSTALL_INSTANCE.json"
echo 'P05_FORMAL_SOURCE_ASSETS_EXACT=PASS'

echo 'P05_ATOMIC_PHASE=BUILD_DETERMINISTIC_ARTIFACTS'
python3 "$BUILDER" "$WORK/source" "$WORK/target" "$WORK/out1" | tee "$WORK/build1.json"
php -l "$WORK/out1/repair-v1.1.11.php" >/dev/null
php "$WORK/out1/repair-v1.1.11.php" --self-test | tee "$WORK/out1/atomic-self-test.json"
jq -e '.ok==true and .source_version=="1.1.10" and .target_version=="1.1.11" and .recovery_point==true and .rollback==true and .interruption_recovery==true and .idempotence==true and .runtime_pointer_preserved==true' "$WORK/out1/atomic-self-test.json" >/dev/null
python3 "$BUILDER" "$WORK/source" "$WORK/target" "$WORK/out2" >"$WORK/build2.json"
test "$(sha256sum "$WORK/out1/repair-v1.1.11.php" | awk '{print $1}')" = "$(sha256sum "$WORK/out2/repair-v1.1.11.php" | awk '{print $1}')"
test "$(sha256sum "$WORK/out1/VF_SEO_V1.1.11_UPDATE.zip" | awk '{print $1}')" = "$(sha256sum "$WORK/out2/VF_SEO_V1.1.11_UPDATE.zip" | awk '{print $1}')"
test "$(unzip -Z1 "$WORK/out1/VF_SEO_V1.1.11_UPDATE.zip" | wc -l)" -eq 1
unzip -Z1 "$WORK/out1/VF_SEO_V1.1.11_UPDATE.zip" | grep -Fx 'repair-v1.1.11.php' >/dev/null
echo 'P05_ATOMIC_DETERMINISTIC_ARTIFACTS=PASS'

PIDS=()
cleanup(){ for p in "${PIDS[@]:-}"; do kill "$p" >/dev/null 2>&1 || true; done; }
trap cleanup EXIT

start_router(){
  local root="$1" port="$2" log="$3"
  php -d opcache.enable_cli=0 -S "127.0.0.1:${port}" -t "$root" "$root/index.php" >"$log" 2>&1 &
  local pid=$!
  PIDS+=("$pid")
  for _ in $(seq 1 100); do
    if curl -fsS "http://127.0.0.1:${port}/setup" -o /dev/null; then return 0; fi
    sleep .15
  done
  cat "$log"
  return 1
}

stop_last(){
  local idx=$((${#PIDS[@]}-1))
  local p="${PIDS[$idx]}"
  kill "$p" >/dev/null 2>&1 || true
  unset 'PIDS[$idx]'
}

setup_source(){
  local root="$1" port="$2" label="$3"
  rm -rf "$(dirname "$root")"
  mkdir -p "$(dirname "$root")"
  cp -a "$WORK/source" "$root"
  start_router "$root" "$port" "$WORK/${label}-server.log"
  local cookie="$WORK/${label}.cookie" page="$WORK/${label}-setup.html"
  curl -fsS -c "$cookie" -b "$cookie" "http://127.0.0.1:${port}/setup" -o "$page"
  local csrf
  csrf=$(python3 - "$page" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read()
m=re.search(r'name="csrf_token"[^>]*value="([^"]+)"',s)
assert m
print(m.group(1))
PY
)
  curl -fsS -c "$cookie" -b "$cookie" -H "Origin: http://127.0.0.1:${port}" -X POST "http://127.0.0.1:${port}/setup" \
    --data-urlencode "csrf_token=$csrf" \
    --data-urlencode 'username=admin' \
    --data-urlencode "password=$PASSWORD" \
    --data-urlencode "password_confirm=$PASSWORD" \
    -o "$WORK/${label}-setup-post.html"
  grep -E '安装完成|已完成' "$WORK/${label}-setup-post.html" >/dev/null
  stop_last
  test -f "$root/VF_INSTALL_INSTANCE.json"
  test "$(jq -r .format "$root/VF_INSTALL_INSTANCE.json")" = '3'
}

db_path(){
  local root="$1" slug
  slug=$(jq -r .storageSlug "$root/VF_INSTALL_INSTANCE.json")
  printf '%s/%s/data/vf-seo.sqlite3' "$(dirname "$root")" "$slug"
}

updates_path(){
  local root="$1" slug
  slug=$(jq -r .storageSlug "$root/VF_INSTALL_INSTANCE.json")
  printf '%s/%s/updates' "$(dirname "$root")" "$slug"
}

seed(){
  local root="$1" db
  db=$(db_path "$root")
  sqlite3 "$db" "INSERT INTO projects(id,name,description) VALUES('11111111-1111-4111-8111-111111111111','ATOMIC_KEEP','must survive');"
}

assert_data(){
  local root="$1" db
  db=$(db_path "$root")
  test "$(sqlite3 "$db" "SELECT count(*) FROM projects WHERE id='11111111-1111-4111-8111-111111111111' AND name='ATOMIC_KEEP';")" = '1'
  test "$(sqlite3 "$db" "SELECT schema_identity||':'||schema_version FROM schema_metadata WHERE singleton=1;")" = 'VF-SEO-SCHEMA@1:1'
  test "$(sqlite3 "$db" 'PRAGMA integrity_check;')" = 'ok'
}

REPAIR="$WORK/out1/repair-v1.1.11.php"

echo 'P05_ATOMIC_PHASE=ACTUAL_UPGRADE_AND_IDEMPOTENCE'
U="$WORK/upgrade/site"
setup_source "$U" 18710 upgrade
seed "$U"
P_BEFORE=$(sha256sum "$U/VF_INSTALL_INSTANCE.json" | awk '{print $1}')
DB_BEFORE=$(db_path "$U")
php -d opcache.enable_cli=0 "$REPAIR" --verify-source="$U" | jq -e '.ok==true' >/dev/null
php -d opcache.enable_cli=0 "$REPAIR" --run="$U" | tee "$WORK/upgrade-result.json"
jq -e '.ok==true and .already_current==false and .pointer_preserved==true and .rollback_supported==true and .schema_version==1' "$WORK/upgrade-result.json" >/dev/null
test "$(cat "$U/VERSION")" = '1.1.11'
php -d opcache.enable_cli=0 "$REPAIR" --verify-target="$U" | jq -e '.ok==true' >/dev/null
test "$(sha256sum "$U/VF_INSTALL_INSTANCE.json" | awk '{print $1}')" = "$P_BEFORE"
test "$(db_path "$U")" = "$DB_BEFORE"
assert_data "$U"
php -d opcache.enable_cli=0 "$REPAIR" --run="$U" | tee "$WORK/idempotent.json"
jq -e '.ok==true and .already_current==true' "$WORK/idempotent.json" >/dev/null
echo 'P05_V1110_TO_V1111_ACTUAL_UPGRADE_DATA_IDEMPOTENCE=PASS'

echo 'P05_ATOMIC_PHASE=FAILURE_ROLLBACK'
F="$WORK/failure/site"
setup_source "$F" 18711 failure
seed "$F"
FP=$(sha256sum "$F/VF_INSTALL_INSTANCE.json" | awk '{print $1}')
set +e
VF_ATOMIC_TEST_FAIL_AFTER_APPLY=1 php -d opcache.enable_cli=0 "$REPAIR" --run="$F" >"$WORK/failure.out" 2>"$WORK/failure.err"
RC=$?
set -e
test "$RC" -ne 0
test "$(cat "$F/VERSION")" = '1.1.10'
php -d opcache.enable_cli=0 "$REPAIR" --verify-source="$F" | jq -e '.ok==true' >/dev/null
test "$(sha256sum "$F/VF_INSTALL_INSTANCE.json" | awk '{print $1}')" = "$FP"
assert_data "$F"
test ! -e "$(updates_path "$F")/p05-atomic-transaction.json"
echo 'P05_V1111_FAILURE_ROLLBACK=PASS'

echo 'P05_ATOMIC_PHASE=HARD_INTERRUPTION_RECOVERY'
H="$WORK/hard/site"
setup_source "$H" 18712 hard
seed "$H"
HP=$(sha256sum "$H/VF_INSTALL_INSTANCE.json" | awk '{print $1}')
set +e
VF_ATOMIC_TEST_HARD_EXIT_AFTER_APPLY=1 php -d opcache.enable_cli=0 "$REPAIR" --run="$H" >"$WORK/hard.out" 2>"$WORK/hard.err"
RC=$?
set -e
test "$RC" -eq 97
test -f "$(updates_path "$H")/p05-atomic-transaction.json"
php -d opcache.enable_cli=0 "$REPAIR" --run="$H" | tee "$WORK/hard-recovery.json"
jq -e '.ok==true and .interrupted_recovered==true and .already_current==false' "$WORK/hard-recovery.json" >/dev/null
test "$(cat "$H/VERSION")" = '1.1.11'
test "$(sha256sum "$H/VF_INSTALL_INSTANCE.json" | awk '{print $1}')" = "$HP"
assert_data "$H"
test ! -e "$(updates_path "$H")/p05-atomic-transaction.json"
echo 'P05_V1111_HARD_INTERRUPTION_RECOVERY=PASS'

echo 'P05_ATOMIC_PHASE=BROWSER_SINGLE_PHP'
B="$WORK/browser/site"
setup_source "$B" 18713 browser
cp "$REPAIR" "$B/repair-v1.1.11.php"
php -d opcache.enable_cli=0 -S 127.0.0.1:18714 -t "$B" >"$WORK/browser-repair-server.log" 2>&1 &
RPID=$!
PIDS+=("$RPID")
for _ in $(seq 1 100); do
  if curl -fsS http://127.0.0.1:18714/repair-v1.1.11.php -o /dev/null; then break; fi
  sleep .15
done
curl -fsS -c "$WORK/repair.cookie" -b "$WORK/repair.cookie" http://127.0.0.1:18714/repair-v1.1.11.php -o "$WORK/repair-get.html"
grep -F '执行原子升级' "$WORK/repair-get.html" >/dev/null
RCSRF=$(python3 - <<'PY'
import re
s=open('/tmp/p05-atomic/repair-get.html',encoding='utf-8').read()
m=re.search(r'name="csrf" value="([^"]+)"',s)
assert m
print(m.group(1))
PY
)
curl -fsS -c "$WORK/repair.cookie" -b "$WORK/repair.cookie" -H 'Origin: http://127.0.0.1:18714' -X POST http://127.0.0.1:18714/repair-v1.1.11.php \
  --data-urlencode "csrf=$RCSRF" --data-urlencode 'password=wrong-password' -o "$WORK/repair-wrong.html"
grep -F '管理员密码不正确' "$WORK/repair-wrong.html" >/dev/null
curl -fsS -c "$WORK/repair.cookie" -b "$WORK/repair.cookie" -H 'Origin: http://127.0.0.1:18714' -X POST http://127.0.0.1:18714/repair-v1.1.11.php \
  --data-urlencode "csrf=$RCSRF" --data-urlencode "password=$PASSWORD" -o "$WORK/repair-post.html"
grep -F '升级完成' "$WORK/repair-post.html" >/dev/null
test "$(cat "$B/VERSION")" = '1.1.11'
stop_last
echo 'P05_V1111_BROWSER_SINGLE_PHP_ATOMIC_UPGRADE=PASS'

echo 'P05_ATOMIC_PHASE=SEAL_EVIDENCE'
python3 - <<'PY'
import json,pathlib
out=pathlib.Path('/tmp/p05-atomic/out1')
p=out/'P05-V1.1.11-ATOMIC-METADATA.json'
x=json.loads(p.read_text())
x.update({
  'status':'FORMAL_ATOMIC_ARTIFACT_GATE_PASS',
  'formal_source_release':'v1.1.10',
  'formal_target_release':'v1.1.11',
  'actual_upgrade':'PASS',
  'data_preservation':'PASS',
  'idempotence':'PASS',
  'failure_rollback':'PASS',
  'hard_interruption_recovery':'PASS',
  'browser_single_php':'PASS',
  'schema_change':False,
  'production_write':0,
})
p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
(out/'P05-V1.1.11-ATOMIC-GATE.json').write_text(json.dumps({
  'project_id':'P05',
  'source_version':'1.1.10',
  'target_version':'1.1.11',
  'result':'PASS',
  'source_formal_sha256':'16448869130988685c5fadb42f50362dfac08d6b2dd8657394b8a43c7787ba5d',
  'target_formal_sha256':'b24bbbeb997fa6414689a01b32eb70a7bf20c82ffeec8761fea4b69612629ce8',
  'self_test':'PASS',
  'actual_upgrade':'PASS',
  'data_preservation':'PASS',
  'idempotence':'PASS',
  'rollback':'PASS',
  'interruption_recovery':'PASS',
  'browser_single_php':'PASS',
  'production_write':0,
},ensure_ascii=False,indent=2)+'\n')
PY
sha256sum \
  "$WORK/out1/repair-v1.1.11.php" \
  "$WORK/out1/VF_SEO_V1.1.11_UPDATE.zip" \
  "$WORK/out1/atomic-self-test.json" \
  "$WORK/out1/P05-V1.1.11-ATOMIC-METADATA.json" \
  "$WORK/out1/P05-V1.1.11-ATOMIC-GATE.json" > "$WORK/out1/SHA256SUMS.txt"
cat "$WORK/out1/P05-V1.1.11-ATOMIC-GATE.json"
cat "$WORK/out1/SHA256SUMS.txt"
echo 'P05_V1111_STANDARD_ATOMIC_ARTIFACT_GATE=PASS'
echo 'P05_PRODUCTION_WRITE=0'
