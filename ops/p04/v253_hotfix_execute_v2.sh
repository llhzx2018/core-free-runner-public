#!/usr/bin/env bash
set -Eeuo pipefail
: "${VF_RELEASE_WRITE_TOKEN:?VF_RELEASE_WRITE_TOKEN required}"
HOTFIX_BRANCH='hotfix/p04-v2.5.3-settings-maintenance-ui-20260816'
V252_COMMIT='91984268ffe66781700db9da10de8d509c878c0b'
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORK="${RUNNER_TEMP:?}/p04-v253-e2e"
REPO="$WORK/repo"
rm -rf "$WORK"; mkdir -p "$WORK"
cleanup(){ if [[ -n "${PID:-}" ]]; then kill "$PID" 2>/dev/null || true; fi; rm -rf "$WORK"; }
trap cleanup EXIT

echo 'GATE 1/10 · Exact immutable V2.5.2 base'
git clone -q "https://x-access-token:${VF_RELEASE_WRITE_TOKEN}@github.com/llhzx2018/vf-infra.git" "$REPO"
cd "$REPO"; git checkout -q "$HOTFIX_BRANCH"
test "$(git rev-parse HEAD)" = "$V252_COMMIT"
python3 "$SCRIPT_DIR/v253_hotfix_patch.py" .
python3 "$SCRIPT_DIR/v253_hotfix_postpatch.py" .
test "$(cat VERSION)" = 2.5.3
! grep -R "UpdateContract::PRIMARY_KEY_ID" public src/app/Core/Update
! grep -R "mb_substr" src/app/Core/Update scripts/build-v251-maintenance-release.py
echo 'BASE_AND_PATCH=PASS'

echo 'GATE 2/10 · Business no-touch + syntax + unit contract'
BUSINESS_DIFF=$(git diff --name-only "$V252_COMMIT" -- src/app/DomainCheckService.php src/app/DomainRepository.php src/app/RdapClient.php src/app/Modules src/app/Core/Provider src/app/Core/ProviderAccountService.php src/app/Core/ProviderSyncService.php src/app/CronRunner.php src/app/CronStatusService.php migrations || true)
test -z "$BUSINESS_DIFF"
find src public -name '*.php' -print0 | xargs -0 -n1 php -l >/dev/null
node --check public/assets/app.js
php tests/unit/core_updates_contract_v252.php
echo 'BUSINESS_NO_TOUCH_SYNTAX_UNIT=PASS'

echo 'GATE 3/10 · Build exact V2.5.2 runtime and V2.5.3 candidate'
mkdir -p "$WORK/v252-src"
git archive "$V252_COMMIT" | tar -x -C "$WORK/v252-src"
python3 "$WORK/v252-src/scripts/build-release-tree.py" "$WORK/v252-runtime" >/dev/null
python3 scripts/build-release-tree.py "$WORK/v253-runtime" >/dev/null
python3 scripts/build-v253-update-release.py --target-runtime "$WORK/v253-runtime" --output "$WORK/v253-release" >"$WORK/build.jsonl"
test "$(cat "$WORK/v252-runtime/VERSION.txt")" = 2.5.2
test "$(cat "$WORK/v253-runtime/VERSION.txt")" = 2.5.3
php "$WORK/v253-release/repair-v2.5.3.php" --self-test
python3 - "$WORK/v253-release/PACKAGE_MANIFEST.json" >"$WORK/package.env" <<'PY'
import json,sys
p=json.load(open(sys.argv[1],encoding='utf-8'))
assert p['version']=='2.5.3' and p['schema']==14
assert p['allowed_source_versions']==['2.5.2']
assert p['payload_file_count']==7
assert p['schema_change'] is False and p['business_model_change'] is False and p['provider_write_authority_change'] is False
assert p['update_and_atomic_bytes_identical'] is True
print('TARGET_MANIFEST_SHA='+p['production_source_manifest_sha256'])
print('TARGET_SOURCE_FILES='+str(p['production_source_file_count']))
print('ASSET_BYTES='+str(__import__('os').path.getsize(sys.argv[1].replace('PACKAGE_MANIFEST.json','VF_Infra_V2.5.3_UPDATE.zip'))))
print('ASSET_SHA='+__import__('hashlib').sha256(open(sys.argv[1].replace('PACKAGE_MANIFEST.json','VF_Infra_V2.5.3_UPDATE.zip'),'rb').read()).hexdigest())
PY
source "$WORK/package.env"
echo "V253_PACKAGE=PASS BYTES=$ASSET_BYTES SHA=$ASSET_SHA MANIFEST=$TARGET_MANIFEST_SHA FILES=$TARGET_SOURCE_FILES"

echo 'GATE 4/10 · Fresh exact V2.5.2 real PHP/SQLite site'
ROOT="$WORK/site-root"; SITE="$ROOT/site"; DATA="$ROOT/.vfinfra-data"; DB="$DATA/database/vf-domain.sqlite"
mkdir -p "$SITE"; cp -a "$WORK/v252-runtime"/. "$SITE"/
PORT=$(python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()')
BASE="http://127.0.0.1:$PORT"; PASS='P04V253HotfixTest!'
php -S 127.0.0.1:$PORT -t "$SITE" >"$WORK/http.log" 2>&1 & PID=$!
sleep .5; kill -0 "$PID"
curl -sS -c "$WORK/cookie" "$BASE/setup.php" -o "$WORK/setup.html"
CSRF=$(python3 - "$WORK/setup.html" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="csrf" value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
SETUP_CODE=$(curl -sS -b "$WORK/cookie" -c "$WORK/cookie" -o "$WORK/setup-post.body" -w '%{http_code}' -H "Origin: $BASE" --data-urlencode "csrf=$CSRF" --data-urlencode 'site_name=VF Infra V253 Fixture' --data-urlencode "password=$PASS" --data-urlencode "password_confirm=$PASS" "$BASE/setup.php")
[[ "$SETUP_CODE" == 302 || "$SETUP_CODE" == 303 ]]
test -f "$DB"
test "$(cat "$SITE/VERSION.txt")" = 2.5.2
test "$(sqlite3 "$DB" "select coalesce(max(version),0) from schema_migrations where status='success';")" = 14
test "$(sqlite3 "$DB" 'pragma integrity_check;')" = ok
test -z "$(sqlite3 "$DB" 'pragma foreign_key_check;')"
echo 'FRESH_V252=PASS'

echo 'GATE 5/10 · Login + reproduce real V2.5.2 Settings regression'
curl -sS -b "$WORK/cookie" -c "$WORK/cookie" "$BASE/login.php?return=maintenance.php" -o "$WORK/login.html"
LCSRF=$(python3 - "$WORK/login.html" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="csrf" value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
LOGIN_CODE=$(curl -sS -b "$WORK/cookie" -c "$WORK/cookie" -o "$WORK/login-post.body" -w '%{http_code}' -H "Origin: $BASE" --data-urlencode "csrf=$LCSRF" --data-urlencode "password=$PASS" --data-urlencode 'return=maintenance.php' "$BASE/login.php")
[[ "$LOGIN_CODE" == 302 || "$LOGIN_CODE" == 303 ]]
PRE_CODE=$(curl -sS -b "$WORK/cookie" -o "$WORK/settings-before.json" -w '%{http_code}' "$BASE/api.php?action=settings")
test "$PRE_CODE" = 500
python3 - "$WORK/settings-before.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1],encoding='utf-8'))
assert d.get('ok') is False and d.get('error_code')=='INTERNAL_ERROR',d
print('V252_SETTINGS_REGRESSION_REPRODUCED=PASS')
PY

echo 'GATE 6/10 · Synthetic existing data + protected identity'
sqlite3 "$DB" "insert into domains(domain,project_name,registrar,currency,auto_renew,tags_json,notes,created_at,updated_at) values('preserve-v253.example','P04 Hotfix','Synthetic Registrar','USD',1,'[\"hotfix\"]','must survive',datetime('now'),datetime('now'));"
DOMAIN_BEFORE=$(sqlite3 -batch -noheader "$DB" "select id,domain,project_name,registrar,currency,auto_renew,tags_json,notes,created_at,updated_at from domains where domain='preserve-v253.example';" | sha256sum | awk '{print $1}')
PROVIDER_TABLES_BEFORE=$(sqlite3 -batch -noheader "$DB" "select (select count(*) from providers),(select count(*) from provider_accounts),(select count(*) from credentials);" | sha256sum | awk '{print $1}')
echo 'SYNTHETIC_DATA_READY=PASS'

echo 'GATE 7/10 · Publish exact Atomic + verify repair CSP/UI'
cat > "$WORK/publish.php" <<'PHP'
<?php
require $argv[1].'/bootstrap.php';
$p=$argv[2];$s=new \VFInfra\Core\MaintenanceUpdateService();$r=$s->inspectAndPublishPath($p,hash_file('sha256',$p),false);
echo $r['target_version'],'|',$r['target_schema'],'|',$r['payload_file_count'],'|',$r['source_manifest_sha256'],PHP_EOL;
PHP
PUBLISH=$(php "$WORK/publish.php" "$SITE" "$WORK/v253-release/VF_Infra_V2.5.3_ATOMIC.zip")
[[ "$PUBLISH" == 2.5.3\|14\|7\|* ]]
test -f "$SITE/repair-v2.5.3.php"
curl -sS -D "$WORK/repair.headers" -b "$WORK/cookie" "$BASE/repair-v2.5.3.php" -o "$WORK/repair.html"
grep -Fiq "style-src 'nonce-" "$WORK/repair.headers" || grep -Fiq "style-src 'self' 'nonce-" "$WORK/repair.headers"
grep -Fq '<style nonce=' "$WORK/repair.html"
grep -Fq '准备升级 VF Infra' "$WORK/repair.html"
RCSRF=$(python3 - "$WORK/repair.html" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="csrf" value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
echo 'REPAIR_PREPARE_UI_CSP=PASS'

echo 'GATE 8/10 · Real Atomic 2.5.2 -> 2.5.3 + DB preservation'
UP_CODE=$(curl -sS -b "$WORK/cookie" -c "$WORK/cookie" -o "$WORK/repair-post.html" -w '%{http_code}' -H "Origin: $BASE" --data-urlencode "csrf=$RCSRF" "$BASE/repair-v2.5.3.php")
test "$UP_CODE" = 200
grep -Fq '升级完成' "$WORK/repair-post.html"
test "$(cat "$SITE/VERSION.txt")" = 2.5.3
test "$(sqlite3 "$DB" "select coalesce(max(version),0) from schema_migrations where status='success';")" = 14
test "$(sqlite3 "$DB" 'pragma integrity_check;')" = ok
test -z "$(sqlite3 "$DB" 'pragma foreign_key_check;')"
DOMAIN_AFTER=$(sqlite3 -batch -noheader "$DB" "select id,domain,project_name,registrar,currency,auto_renew,tags_json,notes,created_at,updated_at from domains where domain='preserve-v253.example';" | sha256sum | awk '{print $1}')
test "$DOMAIN_BEFORE" = "$DOMAIN_AFTER"
PROVIDER_TABLES_AFTER=$(sqlite3 -batch -noheader "$DB" "select (select count(*) from providers),(select count(*) from provider_accounts),(select count(*) from credentials);" | sha256sum | awk '{print $1}')
test "$PROVIDER_TABLES_BEFORE" = "$PROVIDER_TABLES_AFTER"
test ! -e "$SITE/repair-v2.5.3.php"
echo 'ATOMIC_DATA_SCHEMA_CLEANUP=PASS'

echo 'GATE 9/10 · Settings fixed + Maintenance UI/CSP + Source Exact'
POST_CODE=$(curl -sS -b "$WORK/cookie" -o "$WORK/settings-after.json" -w '%{http_code}' "$BASE/api.php?action=settings")
test "$POST_CODE" = 200
python3 - "$WORK/settings-after.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1],encoding='utf-8'))
assert d.get('ok') is True,d
assert d['system']['version']=='2.5.3' and d['system']['schema_version']==14
ut=d['update_trust']; assert ut['required_key_id']=='core-updates + GitHub Release' and 'ready' in ut
assert 'backups' in d and 'diagnostics' in d and 'provider_accounts' in d
print('SETTINGS_V253=PASS')
PY
curl -sS -D "$WORK/maint.headers" -b "$WORK/cookie" "$BASE/maintenance.php" -o "$WORK/maint.html"
grep -Fiq "style-src 'self' 'nonce-" "$WORK/maint.headers"
grep -Fq '<style nonce=' "$WORK/maint.html"
! grep -Fq '<footer style=' "$WORK/maint.html"
cat > "$WORK/source-manifest.php" <<'PHP'
<?php
require $argv[1].'/bootstrap.php';
$m=(new \VFInfra\Core\MaintenanceUpdateService())->productionSourceManifest();
echo $m['sha256'],'|',$m['file_count'],'|',$m['version'],'|',$m['schema'],PHP_EOL;
PHP
ACTUAL_MANIFEST=$(php "$WORK/source-manifest.php" "$SITE")
test "$ACTUAL_MANIFEST" = "$TARGET_MANIFEST_SHA|$TARGET_SOURCE_FILES|2.5.3|14"
echo 'SETTINGS_MAINTENANCE_SOURCE_EXACT=PASS'

echo 'GATE 10/10 · Commit only after all gates pass'
kill "$PID" 2>/dev/null || true; PID=''
git config user.name VictorForge
git config user.email llhzx2018@gmail.com
git add VERSION CHANGELOG.md public/api.php public/assets/app.js public/maintenance.php src/app/Core/Update/UpdateManifestService.php src/app/Core/Update/UpdateRepositoryClient.php scripts/build-release-tree.py scripts/build-v251-maintenance-release.py scripts/build-v253-update-release.py
git commit -m 'fix(P04): V2.5.3 settings and maintenance hotfix'
git push -q origin "$HOTFIX_BRANCH"
echo "HOTFIX_COMMIT=$(git rev-parse HEAD)"
echo "HOTFIX_TREE=$(git rev-parse HEAD^{tree})"
echo "V253_UPDATE_BYTES=$ASSET_BYTES"
echo "V253_UPDATE_SHA256=$ASSET_SHA"
echo "V253_SOURCE_MANIFEST_SHA256=$TARGET_MANIFEST_SHA"
echo 'P04_V253_HOTFIX_ALL_GATES=PASS'
