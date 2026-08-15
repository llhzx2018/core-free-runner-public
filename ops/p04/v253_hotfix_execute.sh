#!/usr/bin/env bash
set -Eeuo pipefail
: "${VF_RELEASE_WRITE_TOKEN:?VF_RELEASE_WRITE_TOKEN required}"
HOTFIX_BRANCH='hotfix/p04-v2.5.3-settings-maintenance-ui-20260816'
V252_COMMIT='91984268ffe66781700db9da10de8d509c878c0b'
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORK="${RUNNER_TEMP:?}/p04-v253-work"
REPO="$WORK/repo"
rm -rf "$WORK"; mkdir -p "$WORK"
trap 'rm -rf "$WORK"' EXIT

git clone -q "https://x-access-token:${VF_RELEASE_WRITE_TOKEN}@github.com/llhzx2018/vf-infra.git" "$REPO"
cd "$REPO"; git checkout -q "$HOTFIX_BRANCH"
test "$(git rev-parse HEAD)" = "$V252_COMMIT"
echo 'HOTFIX_BASE_EXACT_V252=PASS'
python3 "$SCRIPT_DIR/v253_hotfix_patch.py" .
python3 "$SCRIPT_DIR/v253_hotfix_postpatch.py" .

test "$(cat VERSION)" = 2.5.3
! grep -R "UpdateContract::PRIMARY_KEY_ID" public src/app/Core/Update
! grep -R "mb_substr" src/app/Core/Update scripts/build-v251-maintenance-release.py
test -z "$(git diff --name-only "$V252_COMMIT" -- src/app/DomainCheckService.php src/app/DomainRepository.php src/app/RdapClient.php src/app/Modules src/app/Core/Provider src/app/Core/ProviderAccountService.php src/app/Core/ProviderSyncService.php src/app/CronRunner.php src/app/CronStatusService.php migrations 2>/dev/null || true)"
find src public -name '*.php' -print0 | xargs -0 -n1 php -l >/dev/null
node --check public/assets/app.js
php tests/unit/core_updates_contract_v252.php
echo 'HOTFIX_SCOPE_SYNTAX=PASS'

mkdir -p "$WORK/v252-src"
git archive "$V252_COMMIT" | tar -x -C "$WORK/v252-src"
python3 "$WORK/v252-src/scripts/build-release-tree.py" "$WORK/v252-runtime"
python3 scripts/build-release-tree.py "$WORK/v253-runtime"
python3 scripts/build-v253-update-release.py --target-runtime "$WORK/v253-runtime" --output "$WORK/v253-release"
test "$(cat "$WORK/v252-runtime/VERSION.txt")" = 2.5.2
test "$(cat "$WORK/v253-runtime/VERSION.txt")" = 2.5.3
php "$WORK/v253-release/repair-v2.5.3.php" --self-test
python3 - "$WORK/v253-release/PACKAGE_MANIFEST.json" <<'PY'
import json,sys
p=json.load(open(sys.argv[1],encoding='utf-8'))
assert p['version']=='2.5.3' and p['schema']==14
assert p['allowed_source_versions']==['2.5.2']
assert p['payload_file_count']==7
assert p['schema_change'] is False and p['business_model_change'] is False and p['provider_write_authority_change'] is False
assert p['update_and_atomic_bytes_identical'] is True
print('V253_PACKAGE_CONTRACT=PASS')
PY

ROOT="$WORK/site-root"; SITE="$ROOT/site"; DATA="$ROOT/.vfinfra-data"; DB="$DATA/database/vf-domain.sqlite"; PORT=18523; PASS='P04V253HotfixTest!'
mkdir -p "$SITE"; cp -a "$WORK/v252-runtime"/. "$SITE"/
php -S 127.0.0.1:$PORT -t "$SITE" >"$WORK/http.log" 2>&1 & PID=$!
trap 'kill $PID 2>/dev/null || true; rm -rf "$WORK"' EXIT
for i in $(seq 1 80); do curl -fsS "http://127.0.0.1:$PORT/setup.php" -o "$WORK/setup.html" && break || sleep .2; done
curl -fsS -c "$WORK/cookie" "http://127.0.0.1:$PORT/setup.php" -o "$WORK/setup.html"
CSRF=$(python3 - "$WORK/setup.html" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="csrf" value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsS -i -b "$WORK/cookie" -c "$WORK/cookie" -H "Origin: http://127.0.0.1:$PORT" --data-urlencode "csrf=$CSRF" --data-urlencode 'site_name=VF Infra V253 Fixture' --data-urlencode "password=$PASS" --data-urlencode "password_confirm=$PASS" "http://127.0.0.1:$PORT/setup.php" >"$WORK/setup-post"
grep -Eq '^HTTP/.* 30[23]' "$WORK/setup-post"
test -f "$DB"
test "$(sqlite3 "$DB" "select value from settings where key='installed_version';")" = 2.5.2
test "$(sqlite3 "$DB" "select coalesce(max(version),0) from schema_migrations where status='success';")" = 14
sqlite3 "$DB" "insert into domains(domain,created_at,updated_at) values('preserve-v253.example',datetime('now'),datetime('now'));"
BEFORE=$(sqlite3 "$DB" "select id,domain,created_at from domains where domain='preserve-v253.example';" | sha256sum | awk '{print $1}')

curl -fsS -b "$WORK/cookie" -c "$WORK/cookie" "http://127.0.0.1:$PORT/login.php?return=maintenance.php" -o "$WORK/login.html"
LCSRF=$(python3 - "$WORK/login.html" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="csrf" value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsS -i -b "$WORK/cookie" -c "$WORK/cookie" -H "Origin: http://127.0.0.1:$PORT" --data-urlencode "csrf=$LCSRF" --data-urlencode "password=$PASS" --data-urlencode 'return=maintenance.php' "http://127.0.0.1:$PORT/login.php" >"$WORK/login-post"
grep -Eq '^HTTP/.* 30[23]' "$WORK/login-post"

cat > "$WORK/publish.php" <<'PHP'
<?php
require $argv[1].'/bootstrap.php';
$p=$argv[2];$s=new \VFInfra\Core\MaintenanceUpdateService();$r=$s->inspectAndPublishPath($p,hash_file('sha256',$p),false);
echo $r['target_version'],'|',$r['target_schema'],'|',$r['payload_file_count'],PHP_EOL;
PHP
php "$WORK/publish.php" "$SITE" "$WORK/v253-release/VF_Infra_V2.5.3_ATOMIC.zip" | grep -Fq '2.5.3|14|7'
curl -fsS -D "$WORK/repair.headers" -b "$WORK/cookie" "http://127.0.0.1:$PORT/repair-v2.5.3.php" -o "$WORK/repair.html"
grep -Fiq "style-src 'self' 'nonce-" "$WORK/repair.headers"
grep -Fq '<style nonce=' "$WORK/repair.html"
RCSRF=$(python3 - "$WORK/repair.html" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="csrf" value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsS -b "$WORK/cookie" -c "$WORK/cookie" -H "Origin: http://127.0.0.1:$PORT" --data-urlencode "csrf=$RCSRF" "http://127.0.0.1:$PORT/repair-v2.5.3.php" -o "$WORK/repair-post.html"
grep -Fq '升级完成' "$WORK/repair-post.html"
test "$(cat "$SITE/VERSION.txt")" = 2.5.3
test "$(sqlite3 "$DB" "select value from settings where key='installed_version';")" = 2.5.3
test "$(sqlite3 "$DB" "select coalesce(max(version),0) from schema_migrations where status='success';")" = 14
test "$(sqlite3 "$DB" 'pragma integrity_check;')" = ok
test -z "$(sqlite3 "$DB" 'pragma foreign_key_check;')"
AFTER=$(sqlite3 "$DB" "select id,domain,created_at from domains where domain='preserve-v253.example';" | sha256sum | awk '{print $1}')
test "$BEFORE" = "$AFTER"
test ! -e "$SITE/repair-v2.5.3.php"

curl -fsS -b "$WORK/cookie" "http://127.0.0.1:$PORT/api.php?action=settings" -o "$WORK/settings.json"
python3 - "$WORK/settings.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1],encoding='utf-8'))
assert d.get('ok') is True,d
assert d['system']['version']=='2.5.3' and d['system']['schema_version']==14
assert d['update_trust']['required_key_id']=='core-updates + GitHub Release'
assert 'backups' in d and 'diagnostics' in d and 'provider_accounts' in d
print('V253_SETTINGS_RUNTIME=PASS')
PY
curl -fsS -D "$WORK/maint.headers" -b "$WORK/cookie" "http://127.0.0.1:$PORT/maintenance.php" -o "$WORK/maint.html"
grep -Fiq "style-src 'self' 'nonce-" "$WORK/maint.headers"
grep -Fq '<style nonce=' "$WORK/maint.html"
! grep -Fq '<footer style=' "$WORK/maint.html"
echo 'V253_ATOMIC_SETTINGS_DATA_UI=PASS'

kill $PID; trap 'rm -rf "$WORK"' EXIT

git config user.name VictorForge
git config user.email llhzx2018@gmail.com
git add VERSION CHANGELOG.md public/api.php public/assets/app.js public/maintenance.php src/app/Core/Update/UpdateManifestService.php src/app/Core/Update/UpdateRepositoryClient.php scripts/build-release-tree.py scripts/build-v251-maintenance-release.py scripts/build-v253-update-release.py
git commit -m 'fix(P04): V2.5.3 settings and maintenance hotfix'
git push -q origin "$HOTFIX_BRANCH"
echo "HOTFIX_COMMIT=$(git rev-parse HEAD)"
echo "HOTFIX_TREE=$(git rev-parse HEAD^{tree})"
echo 'P04_V253_HOTFIX_VERIFIED_AND_PUSHED=PASS'
