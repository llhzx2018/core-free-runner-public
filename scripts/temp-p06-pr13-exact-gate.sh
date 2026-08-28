#!/usr/bin/env bash
set -Eeuo pipefail

P06="${1:-source}"
EXACT_SOURCE="644e43538bf18a72195d1235ba97e38b33d98756"
BASE_MAIN="cadd08903c0835af2cccbcbbec82a92e4e9ea4e8"
EXPECTED_VERSION="0.1.15"
EXPECTED_SCHEMA="3"

cd "$P06"

test "$(git rev-parse HEAD)" = "$EXACT_SOURCE"
git merge-base --is-ancestor "$BASE_MAIN" "$EXACT_SOURCE"
test "$(tr -d '\r\n' < VERSION)" = "$EXPECTED_VERSION"
python3 - <<'PY'
import json
p=json.load(open('VF_PROJECT.json'))
assert p['project_id']=='P06'
assert p['version']=='0.1.15'
assert p['schema']==3
assert p['lifecycle']=='PRODUCTION_CURRENT'
PY

mapfile -t changed < <(git diff --name-only "$BASE_MAIN" "$EXACT_SOURCE")
test "${#changed[@]}" -eq 4
for file in \
  bin/backoffice-self-test.php \
  bin/operations-ui-self-test.php \
  public/assets/backoffice.css \
  src/Http/Studio/BackofficeShell.php; do
  printf '%s\n' "${changed[@]}" | grep -Fxq "$file"
done
git diff --check "$BASE_MAIN" "$EXACT_SOURCE"
echo P06_PR13_SOURCE_SCOPE=PASS

composer validate --strict
composer install --no-interaction --prefer-dist --no-progress
while IFS= read -r f; do php -l "$f" >/dev/null; done < <(find src public bin deploy -type f -name '*.php' | sort)
echo P06_PR13_PHP_SYNTAX=PASS

REG_ROOT="$RUNNER_TEMP/p06-pr13-exact"
rm -rf "$REG_ROOT"
export APP_ENV=test
export VF_PRESS_STORAGE_PATH="$REG_ROOT/storage"
export VF_PRESS_DB_PATH="$REG_ROOT/storage/app.db"
export VF_PRESS_OWNER_USERNAME=gate-owner
export VF_PRESS_OWNER_PASSWORD='P06-PR13-Gate-Owner-Password-2026!'
export VF_PRESS_OWNER_DISPLAY_NAME='PR13 Gate Owner'
mkdir -p "$REG_ROOT/storage"
php bin/migrate.php
test "$(sqlite3 "$VF_PRESS_DB_PATH" 'SELECT MAX(version) FROM schema_migrations;')" = "$EXPECTED_SCHEMA"
php bin/create-owner.php
php bin/preflight.php
echo P06_PR13_FRESH_MIGRATION=PASS

composer self-test
composer security-self-test
php bin/job-self-test.php
composer research-self-test
composer publication-self-test
composer reader-self-test
composer edition-self-test
composer living-publishing-self-test
composer operations-self-test
composer operations-ui-self-test
composer backoffice-self-test
composer backoffice-catalog-self-test
composer public-asset-self-test
composer update-self-test
php bin/common-baseline-v2-self-test.php
php bin/common-baseline-human-ui-self-test.php
echo P06_PR13_FORMAL_REGRESSION=PASS

php -r '
$s=file_get_contents("src/Http/Studio/BackofficeShell.php");
foreach (["P06 Operations","出版运维控制台","<p>内容运营</p>","<p>系统维护</p>","vf-admin-nav-indicator","/studio/system","/studio/system/baseline","/studio/system/health"] as $x) {
  if (strpos($s,$x)===false) { fwrite(STDERR,"missing shell contract: $x\n"); exit(1); }
}
$m=strpos($s,"/runtime-asset/maintenance");
$b=strpos($s,"/runtime-asset/backoffice");
if ($m===false || $b===false || $b <= $m) { fwrite(STDERR,"backoffice style precedence failed\n"); exit(2); }
echo "P06_PR13_ABSORPTION_SURFACE=PASS\n";
'

HTTP_ROOT="$RUNNER_TEMP/p06-pr13-http"
rm -rf "$HTTP_ROOT"
export VF_PRESS_STORAGE_PATH="$HTTP_ROOT/storage"
export VF_PRESS_DB_PATH="$HTTP_ROOT/storage/app.db"
mkdir -p "$HTTP_ROOT/storage" "$HTTP_ROOT/sessions"
php bin/migrate.php
test "$(sqlite3 "$VF_PRESS_DB_PATH" 'SELECT MAX(version) FROM schema_migrations;')" = "$EXPECTED_SCHEMA"
php bin/create-owner.php
ROOT="$HTTP_ROOT"
PORT="$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')"
PASS="$VF_PRESS_OWNER_PASSWORD"
export VF_PRESS_SESSION_IDLE_SECONDS=604800
export VF_PRESS_SESSION_ABSOLUTE_SECONDS=2592000
export VF_PRESS_SESSION_COOKIE_SECONDS=2592000
export VF_PRESS_SERVER_SESSION_FLOOR_SECONDS=2592000
export VF_PRESS_STEP_UP_WINDOW_SECONDS=900
export VF_PRESS_DISPLAY_TIMEZONE=Asia/Shanghai
export VF_PRESS_LOCALE=zh-CN
php -d session.save_path="$ROOT/sessions" -S 127.0.0.1:$PORT -t public public/index.php >"$ROOT/server.log" 2>&1 &
PID=$!
trap 'kill "$PID" 2>/dev/null || true' EXIT
READY=0
for _ in $(seq 1 100); do
  if curl -fsS "http://127.0.0.1:$PORT/health" >"$ROOT/health.json" 2>/dev/null; then READY=1; break; fi
  sleep .1
done
test "$READY" = 1
python3 - "$ROOT/health.json" <<'PY'
import json,sys
x=json.load(open(sys.argv[1]))
assert x['status']=='ok' and x['version']=='0.1.15' and x['schema']==3,x
PY

BASE="http://127.0.0.1:$PORT"
curl -fsS -c "$ROOT/cookies" "$BASE/login" >"$ROOT/login"
csrf() {
  python3 - "$1" <<'PY'
import re,sys
m=re.search(r'name="_csrf" value="([^"]+)"',open(sys.argv[1]).read())
assert m
print(m.group(1))
PY
}
CSRF="$(csrf "$ROOT/login")"
curl -sS -D "$ROOT/login.h" -o /dev/null -b "$ROOT/cookies" -c "$ROOT/cookies" -X POST "$BASE/login" \
  --data-urlencode "_csrf=$CSRF" --data-urlencode username=gate-owner --data-urlencode "password=$PASS"
grep -Fqi 'Location: /studio/operations' "$ROOT/login.h"

curl -fsS -b "$ROOT/cookies" "$BASE/studio/operations" >"$ROOT/operations"
for claim in 'P06 Operations' '出版运维控制台' '内容运营' '系统维护' '研究运营' '出版物运营' '发布与分发' '后台任务' 'vf-admin-nav-indicator' '/studio/system' '/studio/system/baseline' '/studio/system/health'; do
  grep -Fq "$claim" "$ROOT/operations"
done
python3 - "$ROOT/operations" <<'PY'
import sys
s=open(sys.argv[1],encoding='utf-8').read()
m=s.find('/runtime-asset/maintenance')
b=s.find('/runtime-asset/backoffice')
assert m >= 0 and b > m
PY

curl -fsS -b "$ROOT/cookies" "$BASE/studio/system" >"$ROOT/system"
grep -Fq '管理员结论' "$ROOT/system"
grep -Fq '系统运行配置已就绪' "$ROOT/system"
curl -fsS -b "$ROOT/cookies" "$BASE/studio/system/baseline" >"$ROOT/baseline"
grep -Fq '系统基线正常' "$ROOT/baseline"
grep -Fq 'VF-COMMON-PRODUCT-BASELINE@2.0' "$ROOT/baseline"
curl -fsS -b "$ROOT/cookies" "$BASE/studio/system/health" >"$ROOT/syshealth"
grep -Fq '当前运行健康' "$ROOT/syshealth"

CSRF2="$(csrf "$ROOT/system")"
SID="$(awk '$6=="vf_press_session"{print $7}' "$ROOT/cookies" | tail -1)"
test -n "$SID"
php -d session.save_path="$ROOT/sessions" -r 'session_name("vf_press_session");session_id($argv[1]);session_start();unset($_SESSION["vf_press_recent_auth_at"]);session_write_close();' "$SID"
curl -sS -D "$ROOT/guard.h" -o /dev/null -b "$ROOT/cookies" -c "$ROOT/cookies" -X POST "$BASE/studio/updates/install" --data-urlencode "_csrf=$CSRF2"
grep -Fqi 'Location: /studio/system?return_to=/studio/updates' "$ROOT/guard.h"

kill "$PID"; wait "$PID" || true; trap - EXIT
! grep -Eqi 'Fatal error|Parse error|Uncaught|EADDRINUSE' "$ROOT/server.log"
echo P06_PR13_HTTP_OPERATIONS=PASS
echo P06_PR13_HTTP_SYSTEM_BASELINE_HEALTH=PASS
echo P06_PR13_STEP_UP_GUARD=PASS

php bin/migrate.php >/tmp/p06-pr13-final-migrate
grep -Fq MIGRATION_PASS /tmp/p06-pr13-final-migrate
php -r '$pdo=new PDO("sqlite:" . getenv("VF_PRESS_DB_PATH")); if($pdo->query("PRAGMA integrity_check")->fetchColumn()!=="ok") exit(1); if((int)$pdo->query("SELECT MAX(version) FROM schema_migrations")->fetchColumn()!==3) exit(2); echo "P06_PR13_SQLITE_INTEGRITY=PASS\n";'

if ! git ls-files --error-unmatch composer.lock >/dev/null 2>&1; then rm -f composer.lock; fi
test -z "$(git status --short --untracked-files=all)"

test "$(git rev-parse HEAD)" = "$EXACT_SOURCE"
RECEIPT="$(printf '%s|%s|%s|PASS' "$EXACT_SOURCE" "$EXPECTED_VERSION" "$EXPECTED_SCHEMA" | sha256sum | awk '{print $1}')"
echo P06_PR13_EXACT_SOURCE="$EXACT_SOURCE"
echo P06_PR13_VERSION="$EXPECTED_VERSION"
echo P06_PR13_SCHEMA="$EXPECTED_SCHEMA"
echo P06_PR13_MACHINE=PASS
echo P06_PR13_PUBLIC_RECEIPT_SHA256="$RECEIPT"
echo P06_PR13_RELEASE=NO
echo P06_PR13_PRODUCTION=NO
