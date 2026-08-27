#!/usr/bin/env bash
set -Eeuo pipefail
: "${RUNNER_TEMP:?}"
: "${FIXTURE_PASS:?}"
: "${PHP_TEST_IMAGE:?}"

stage(){ echo "P03_V2_GATE_STAGE=$1"; }

stage current_reverify
chmod +x tests/maintenance/current_reverify.sh
bash tests/maintenance/current_reverify.sh
echo CURRENT_REVERIFY_FULL_PASS

stage v2_fresh_runtime
RUNTIME="$RUNNER_TEMP/p03-v2-runtime"
DATA_ROOT="$RUNNER_TEMP/p03-v2-private"
SESS_DIR="$RUNNER_TEMP/p03-v2-sessions"
COOKIE="$RUNNER_TEMP/p03-v2-cookies"
BASE='http://127.0.0.1:18103'
CONTAINER='vf-forge-v2-gate-http'
rm -rf "$RUNTIME" "$DATA_ROOT" "$SESS_DIR" "$COOKIE"
mkdir -p "$DATA_ROOT" "$SESS_DIR"
python3 scripts/build_runtime.py "$RUNTIME" >/dev/null
docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
docker run -d --rm --name "$CONTAINER" -p 18103:18103 \
  -v "$RUNTIME:/app" -v "$DATA_ROOT:$DATA_ROOT" -v "$SESS_DIR:$SESS_DIR" -w /app "$PHP_TEST_IMAGE" \
  php -d "session.save_path=$SESS_DIR" -S 0.0.0.0:18103 -t /app >/dev/null
cleanup(){ docker logs "$CONTAINER" 2>/dev/null || true; docker rm -f "$CONTAINER" >/dev/null 2>&1 || true; }
trap cleanup EXIT
for i in $(seq 1 80); do curl -fsS "$BASE/setup.php" >/dev/null 2>&1 && break; sleep 0.25; done
curl -fsS -c "$COOKIE" "$BASE/setup.php" -o "$RUNNER_TEMP/p03-v2-setup.html"
CSRF=$(python3 - "$RUNNER_TEMP/p03-v2-setup.html" <<'PY'
import re,sys,html
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="setup_csrf" value="([^"]+)"',s);assert m;print(html.unescape(m.group(1)))
PY
)
STATUS=$(curl -sS -o "$RUNNER_TEMP/p03-v2-setup-post.html" -w '%{http_code}' -b "$COOKIE" -c "$COOKIE" \
  -H "Origin: $BASE" --data-urlencode "setup_csrf=$CSRF" \
  --data-urlencode 'site_title=VF Forge Baseline V2 Fixture' \
  --data-urlencode "data_root=$DATA_ROOT" \
  --data-urlencode "password=$FIXTURE_PASS" --data-urlencode "password_confirm=$FIXTURE_PASS" "$BASE/setup.php")
test "$STATUS" = '302' -o "$STATUS" = '303'
DB=$(find "$DATA_ROOT/database" -maxdepth 1 -type f -name '*.sqlite' | head -n1)
test -f "$DB"
test "$(sqlite3 "$DB" "select setting_value from settings where setting_key='timezone';")" = 'Asia/Shanghai'
test "$(sqlite3 "$DB" "select setting_value from settings where setting_key='session_keep_days';")" = '30'
test "$(sqlite3 "$DB" "select setting_value from settings where setting_key='session_timeout_minutes';")" = '10080'
echo V2_FRESH_DEFAULTS_PASS

stage v2_login_contract
LOGIN_JSON=$(printf '{"password":"%s"}' "$FIXTURE_PASS")
curl -fsS -b "$COOKIE" -c "$COOKIE" -H "Origin: $BASE" -H 'Content-Type: application/json' --data "$LOGIN_JSON" "$BASE/api.php?action=login" -o "$RUNNER_TEMP/p03-v2-login.json"
TOKEN=$(python3 - "$RUNNER_TEMP/p03-v2-login.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]));assert d['ok'];print(d['csrf'])
PY
)
curl -fsS -b "$COOKIE" -c "$COOKIE" "$BASE/api.php?action=session" -o "$RUNNER_TEMP/p03-v2-session.json"
python3 - "$RUNNER_TEMP/p03-v2-session.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]));assert d['ok'] and d['authenticated'];assert d['baseline_id']=='VF-COMMON-PRODUCT-BASELINE@2.0';assert d['profile']=='PERSONAL_SINGLE_ADMIN';assert d['session_timeout_minutes']==10080;assert d['session_keep_days']==30;assert d['absolute_timeout_seconds']==2592000;assert d['recent_auth_valid'] is True
print('V2_SESSION_CONTRACT_PASS')
PY
python3 - "$COOKIE" <<'PY'
import sys,time
rows=[]
for raw in open(sys.argv[1],encoding='utf-8').read().splitlines():
    if raw.startswith('#HttpOnly_'): raw=raw[len('#HttpOnly_'):]
    elif raw.startswith('#') or not raw: continue
    parts=raw.split('\t')
    if len(parts)>=7 and parts[5]=='vfforge_session': rows.append(parts)
assert rows, 'session cookie missing'
expiry=int(rows[-1][4]); assert expiry >= int(time.time())+29*86400,(expiry,int(time.time()))
print('V2_COOKIE_30D_PASS')
PY

stage v2_session_boundaries
docker run --rm -v "$RUNTIME:/app" -v "$DATA_ROOT:$DATA_ROOT" -v "$SESS_DIR:$SESS_DIR" -w /app "$PHP_TEST_IMAGE" \
  php -d "session.save_path=$SESS_DIR" -r 'require "app/bootstrap.php";vfab_start_session();$n=time();$_SESSION["vfab_admin"]=true;$_SESSION["vfab_auth_epoch"]=vfab_auth_epoch();$_SESSION["vfab_login_at"]=$n-VfCommonBaseline::AUTH_ABSOLUTE_TIMEOUT_SECONDS+2;$_SESSION["vfab_last_activity_at"]=$n-VfCommonBaseline::AUTH_IDLE_TIMEOUT_SECONDS+2;$_SESSION["vfab_last_db_validation_at"]=$n;if(!vfab_is_admin())exit(2);echo "V2_SESSION_NEAR_BOUNDARY_PASS\n";'
docker run --rm -v "$RUNTIME:/app" -v "$DATA_ROOT:$DATA_ROOT" -v "$SESS_DIR:$SESS_DIR" -w /app "$PHP_TEST_IMAGE" \
  php -d "session.save_path=$SESS_DIR" -r 'require "app/bootstrap.php";vfab_start_session();$n=time();$_SESSION["vfab_admin"]=true;$_SESSION["vfab_auth_epoch"]=vfab_auth_epoch();$_SESSION["vfab_login_at"]=$n-60;$_SESSION["vfab_last_activity_at"]=$n-VfCommonBaseline::AUTH_IDLE_TIMEOUT_SECONDS-2;$_SESSION["vfab_last_db_validation_at"]=$n;if(vfab_is_admin())exit(2);echo "V2_IDLE_EXPIRY_PASS\n";'
docker run --rm -v "$RUNTIME:/app" -v "$DATA_ROOT:$DATA_ROOT" -v "$SESS_DIR:$SESS_DIR" -w /app "$PHP_TEST_IMAGE" \
  php -d "session.save_path=$SESS_DIR" -r 'require "app/bootstrap.php";vfab_start_session();$n=time();$_SESSION["vfab_admin"]=true;$_SESSION["vfab_auth_epoch"]=vfab_auth_epoch();$_SESSION["vfab_login_at"]=$n-VfCommonBaseline::AUTH_ABSOLUTE_TIMEOUT_SECONDS-2;$_SESSION["vfab_last_activity_at"]=$n-60;$_SESSION["vfab_last_db_validation_at"]=$n;if(vfab_is_admin())exit(2);echo "V2_ABSOLUTE_EXPIRY_PASS\n";'

stage v2_step_up
SESSION_ID=$(python3 - "$COOKIE" <<'PY'
import sys
for raw in open(sys.argv[1],encoding='utf-8').read().splitlines():
    if raw.startswith('#HttpOnly_'): raw=raw[len('#HttpOnly_'):]
    elif raw.startswith('#') or not raw: continue
    p=raw.split('\t')
    if len(p)>=7 and p[5]=='vfforge_session': print(p[6]);break
PY
)
test -n "$SESSION_ID"
docker run --rm -v "$RUNTIME:/app" -v "$DATA_ROOT:$DATA_ROOT" -v "$SESS_DIR:$SESS_DIR" -w /app "$PHP_TEST_IMAGE" \
  php -d "session.save_path=$SESS_DIR" -r 'session_id($argv[1]);require "app/bootstrap.php";vfab_start_session();$_SESSION["vfab_recent_auth_at"]=time()-VfCommonBaseline::STEP_UP_WINDOW_SECONDS-2;session_write_close();' "$SESSION_ID"
CODE=$(curl -sS -o "$RUNNER_TEMP/p03-v2-step-before.json" -w '%{http_code}' -b "$COOKIE" -c "$COOKIE" -H "Origin: $BASE" -H "X-CSRF-Token: $TOKEN" -H 'Content-Type: application/json' --data '{}' "$BASE/api.php?action=restore_execute")
test "$CODE" = '428'
REAUTH_JSON=$(printf '{"password":"%s"}' "$FIXTURE_PASS")
CODE=$(curl -sS -o "$RUNNER_TEMP/p03-v2-reauth.json" -w '%{http_code}' -b "$COOKIE" -c "$COOKIE" -H "Origin: $BASE" -H "X-CSRF-Token: $TOKEN" -H 'Content-Type: application/json' --data "$REAUTH_JSON" "$BASE/api.php?action=reauth")
test "$CODE" = '200'
TOKEN=$(python3 - "$RUNNER_TEMP/p03-v2-reauth.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]));assert d['ok'] and d['recent_auth_window_seconds']==900;print(d['csrf'])
PY
)
CODE=$(curl -sS -o "$RUNNER_TEMP/p03-v2-step-after.json" -w '%{http_code}' -b "$COOKIE" -c "$COOKIE" -H "Origin: $BASE" -H "X-CSRF-Token: $TOKEN" -H 'Content-Type: application/json' --data '{}' "$BASE/api.php?action=restore_execute")
test "$CODE" != '428'
test "$CODE" != '401'
test "$CODE" != '419'
echo V2_STEP_UP_PASS

stage v2_resolver
BASELINE_OUT="$RUNNER_TEMP/p03-v2-baseline.txt"
docker run --rm -v "$RUNTIME:/app" -v "$DATA_ROOT:$DATA_ROOT" -v "$SESS_DIR:$SESS_DIR" -w /app "$PHP_TEST_IMAGE" \
  php -d "session.save_path=$SESS_DIR" cli/baseline-verify.php | tee "$BASELINE_OUT"
grep -Fx 'DRIFT_COUNT=0' "$BASELINE_OUT"
grep -Fx 'UNKNOWN_COUNT=0' "$BASELINE_OUT"
grep -Fx 'BASELINE_FULL_PASS=YES' "$BASELINE_OUT"
grep -Fq 'CONNECT_TIMEOUT_SECONDS=5' "$RUNTIME/app/CoreUpdates/GitHubClient.php"
grep -Fq 'REQUEST_TIMEOUT_SECONDS=15' "$RUNTIME/app/CoreUpdates/GitHubClient.php"
grep -Fq 'MAX_RETRY_COUNT=3' "$RUNTIME/app/CoreUpdates/GitHubClient.php"
grep -Fq 'retryDelaySeconds' "$RUNTIME/app/CoreUpdates/GitHubClient.php"
grep -Fq "JOB_GENERAL_TIMEOUT_SECONDS=300" "$RUNTIME/app/CommonBaseline.php"
grep -Fq "JOB_SYNC_TIMEOUT_SECONDS=900" "$RUNTIME/app/CommonBaseline.php"
grep -Fq "JOB_MAINTENANCE_TIMEOUT_SECONDS=1800" "$RUNTIME/app/CommonBaseline.php"
grep -Fq '高级手工原子更新（Fallback）' "$RUNTIME/maintenance.php"
echo V2_RESOLVER_CONTRACT_PASS

stage v2_surfaces
curl -fsS -b "$COOKIE" "$BASE/system-info.php" -o "$RUNNER_TEMP/p03-v2-system-info.html"
curl -fsS -b "$COOKIE" "$BASE/system-baseline.php" -o "$RUNNER_TEMP/p03-v2-system-baseline.html"
grep -Fq '系统信息' "$RUNNER_TEMP/p03-v2-system-info.html"
grep -Fq 'VF-COMMON-PRODUCT-BASELINE@2.0' "$RUNNER_TEMP/p03-v2-system-info.html"
grep -Fq '系统基线' "$RUNNER_TEMP/p03-v2-system-baseline.html"
grep -Fq 'Runtime-derived · Read-only · No Shadow Truth' "$RUNNER_TEMP/p03-v2-system-baseline.html"
grep -Fq '>PASS<' "$RUNNER_TEMP/p03-v2-system-baseline.html"
echo V2_SYSTEM_SURFACES_PASS

stage final
php -r '$d=json_decode(file_get_contents("docs/authority/VF_COMMON_PRODUCT_BASELINE_V2_ADOPTION_CANDIDATE.json"),true,512,JSON_THROW_ON_ERROR);if(($d["state"]??"")!=="MACHINE_VERIFICATION_PENDING"||($d["baseline_id"]??"")!=="VF-COMMON-PRODUCT-BASELINE@2.0")exit(2);echo "V2_CANDIDATE_AUTHORITY_PASS\n";'
echo P03_COMMON_BASELINE_V2_FULL_GATE_PASS
