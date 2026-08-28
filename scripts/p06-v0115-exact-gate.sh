#!/usr/bin/env bash
set -Eeuo pipefail

P06="${1:-p06}"
EXACT_SOURCE="561e59a82f035e2622c4567710bec06a1c50dab3"
BASE_MAIN="d689b79a6f1d98f0bf5bccba438f3c9a74077782"
TARGET_BRANCH="ui/p06-human-baseline-v0115-20260828"

cd "$P06"

test "$(git rev-parse HEAD)" = "$EXACT_SOURCE"
test "$(git rev-parse origin/$TARGET_BRANCH)" = "$EXACT_SOURCE"
test "$(git rev-parse origin/main)" = "$BASE_MAIN"
test "$(tr -d '\r\n' < VERSION)" = '0.1.15'

mapfile -t changed < <(git diff --name-only "$BASE_MAIN" "$EXACT_SOURCE")
test "${#changed[@]}" -eq 6
for file in \
  CHANGELOG.md VERSION VF_PROJECT.json \
  bin/common-baseline-human-ui-self-test.php \
  public/assets/maintenance.css \
  src/Http/Studio/SystemBaselineController.php; do
  printf '%s\n' "${changed[@]}" | grep -Fxq "$file"
done

test -z "$(git diff --name-only "$BASE_MAIN" "$EXACT_SOURCE" -- src/Application/Operations/CommonBaselineV2.php database migrations)"
python3 - <<'PY'
import json
p=json.load(open('VF_PROJECT.json'))
assert p['project_id']=='P06'
assert p['version']=='0.1.15'
assert p['schema']==3
x=p['human_ui_exposure_v0_1_15']
assert x['state']=='CANDIDATE'
assert x['baseline_resolver_change'] is False
assert x['schema_change'] is False
assert x['production_change'] is False
assert x['domain_translation_count']==15
assert x['technical_details_default_collapsed'] is True
assert set(x['explicit_exceptions_preserved'])=={
 'P06-TIME-DISPLAY-CONVERSION-LEGACY-SURFACES',
 'P06-API-RETRY-PROVIDER-SPECIFIC'
}
a=json.load(open('docs/authority/VF_COMMON_PRODUCT_BASELINE_V2_ADOPTION.json'))
assert a['state']=='CURRENT'
assert a['runtime_summary']=={'pass':12,'exception':2,'drift':0,'unknown':0,'n_a':1,'required_domain_count':15}
assert {e['id'] for e in a['explicit_exceptions']}=={
 'P06-TIME-DISPLAY-CONVERSION-LEGACY-SURFACES',
 'P06-API-RETRY-PROVIDER-SPECIFIC'
}
PY

git diff --check "$BASE_MAIN" "$EXACT_SOURCE"
php bin/common-baseline-human-ui-self-test.php
echo P06_V0115_SOURCE_SCOPE=PASS

composer install --no-interaction --prefer-dist --no-progress
while IFS= read -r f; do php -l "$f" >/dev/null; done < <(find src public bin deploy -type f -name '*.php' | sort)
echo P06_V0115_PHP_SYNTAX=PASS

ROOT="$RUNNER_TEMP/p06-v0115-exact"
export APP_ENV=test
export VF_PRESS_STORAGE_PATH="$ROOT/storage"
export VF_PRESS_DB_PATH="$ROOT/storage/app.db"
export VF_PRESS_OWNER_USERNAME=human-owner
export VF_PRESS_OWNER_PASSWORD='P06-Human-Baseline-Owner-Password-2026!'
export VF_PRESS_OWNER_DISPLAY_NAME='Human Baseline Owner'
mkdir -p "$ROOT/storage"
php bin/migrate.php
test "$(sqlite3 "$VF_PRESS_DB_PATH" 'SELECT MAX(version) FROM schema_migrations;')" = 3
php bin/create-owner.php
php bin/preflight.php
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
echo P06_V0115_REGRESSION=PASS

PORT=19059
PASS="$VF_PRESS_OWNER_PASSWORD"
export VF_PRESS_SESSION_IDLE_SECONDS=604800
export VF_PRESS_SESSION_ABSOLUTE_SECONDS=2592000
export VF_PRESS_SESSION_COOKIE_SECONDS=2592000
export VF_PRESS_SERVER_SESSION_FLOOR_SECONDS=2592000
export VF_PRESS_STEP_UP_WINDOW_SECONDS=900
export VF_PRESS_DISPLAY_TIMEZONE=Asia/Shanghai
export VF_PRESS_LOCALE=zh-CN
mkdir -p "$ROOT/sessions"
php -d session.save_path="$ROOT/sessions" -S 127.0.0.1:$PORT -t public public/index.php >"$ROOT/server.log" 2>&1 &
PID=$!
trap 'kill "$PID" 2>/dev/null || true' EXIT
for _ in $(seq 1 100); do curl -fsS "http://127.0.0.1:$PORT/health" >"$ROOT/health.json" 2>/dev/null && break; sleep .1; done
python3 - <<'PY'
import json,os
x=json.load(open(os.path.join(os.environ['RUNNER_TEMP'],'p06-v0115-exact','health.json')))
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
  --data-urlencode "_csrf=$CSRF" --data-urlencode username=human-owner --data-urlencode "password=$PASS"
grep -Fqi 'Location: /studio/operations' "$ROOT/login.h"

curl -fsS -b "$ROOT/cookies" "$BASE/studio/system" >"$ROOT/system"
grep -Fq '管理员结论' "$ROOT/system"
grep -Fq '系统运行配置已就绪' "$ROOT/system"
grep -Fq '空闲多久需要重新登录' "$ROOT/system"
grep -Fq '7 天' "$ROOT/system"
grep -Fq '30 天' "$ROOT/system"
grep -Fq '15 分钟内有效' "$ROOT/system"
grep -Fq '技术详情（开发 / 排障使用）' "$ROOT/system"
grep -Fq '<details class="maintenance-tech-details">' "$ROOT/system"
grep -Fq 'PERSONAL_SINGLE_ADMIN' "$ROOT/system"
grep -Fq 'Asia/Shanghai' "$ROOT/system"

curl -fsS -b "$ROOT/cookies" "$BASE/studio/system/baseline" >"$ROOT/baseline"
grep -Fq '管理员结论' "$ROOT/baseline"
grep -Fq '系统基线正常' "$ROOT/baseline"
grep -Fq '你需要关注' "$ROOT/baseline"
grep -Fq '当前没有必须处理的基线异常' "$ROOT/baseline"
grep -Fq '已知限制 2 项' "$ROOT/baseline"
for label in \
  '时间规则' '登录与高风险验证' '在线升级' '备份与恢复' '数据与 Schema' \
  '外部接口保护' '后台任务' '外部通知' '操作与安全记录' '后台通用状态' \
  '文件上传' '运行健康' '版本身份' '缓存策略' '界面语言'; do
  grep -Fq "$label" "$ROOT/baseline"
done
grep -Fq '旧后台时间显示尚未全部' "$ROOT/baseline"
grep -Fq '尚未统一成一个全局 Retry Wrapper' "$ROOT/baseline"
grep -Fq 'VF-COMMON-PRODUCT-BASELINE@2.0' "$ROOT/baseline"
grep -Fq '技术详情（开发 / 排障使用）' "$ROOT/baseline"

curl -fsS -b "$ROOT/cookies" "$BASE/studio/system/health" >"$ROOT/syshealth"
grep -Fq '管理员结论' "$ROOT/syshealth"
grep -Fq '当前运行健康' "$ROOT/syshealth"
grep -Fq '当前没有运行异常' "$ROOT/syshealth"
grep -Fq '技术详情（开发 / 排障使用）' "$ROOT/syshealth"

CSRF2="$(csrf "$ROOT/system")"
SID="$(awk '$6=="vf_press_session"{print $7}' "$ROOT/cookies" | tail -1)"
test -n "$SID"
php -d session.save_path="$ROOT/sessions" -r 'session_name("vf_press_session");session_id($argv[1]);session_start();unset($_SESSION["vf_press_recent_auth_at"]);session_write_close();' "$SID"
curl -sS -D "$ROOT/guard.h" -o /dev/null -b "$ROOT/cookies" -c "$ROOT/cookies" -X POST "$BASE/studio/updates/install" --data-urlencode "_csrf=$CSRF2"
grep -Fqi 'Location: /studio/system?return_to=/studio/updates' "$ROOT/guard.h"

kill "$PID"; wait "$PID" || true; trap - EXIT
! grep -Eqi 'Fatal error|Parse error|Uncaught|EADDRINUSE' "$ROOT/server.log"
echo P06_V0115_HTTP_HUMAN_UI=PASS
echo P06_V0115_STEP_UP_GUARD=PASS

test "$(git rev-parse HEAD)" = "$EXACT_SOURCE"
test "$(git rev-parse origin/$TARGET_BRANCH)" = "$EXACT_SOURCE"
test "$(git rev-parse origin/main)" = "$BASE_MAIN"
echo P06_V0115_EXACT_SOURCE="$EXACT_SOURCE"
echo P06_V0115_SCHEMA=3
echo P06_V0115_MACHINE=PASS
echo P06_V0115_RELEASE=NO
echo P06_V0115_PRODUCTION=NO
