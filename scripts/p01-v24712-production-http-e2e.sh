#!/usr/bin/env bash
set -Eeuo pipefail

BASELINE_ROOT=${BASELINE_ROOT:-$PWD/baseline}
ARTIFACT_ROOT=${ARTIFACT_ROOT:-$PWD/artifact}
SITE=/tmp/p01-v24712-http-e2e
EVID=/tmp/p01-v24712-http-e2e-evidence
PORT=19913
BASE="http://127.0.0.1:$PORT"
COOKIES="$EVID/cookies"
BRIDGE="$ARTIFACT_ROOT/P01_V24710_AUTH_BRIDGE.php"

: "${VF_PRIVATE_READ_TOKEN:?missing private read token}"

rm -rf "$SITE" "$EVID"
cp -a "$BASELINE_ROOT/src" "$SITE"
mkdir -p "$EVID"

VF_PRIVATE_READ_TOKEN="$VF_PRIVATE_READ_TOKEN" php -S "127.0.0.1:$PORT" -t "$SITE" >"$EVID/server.log" 2>&1 &
PID=$!
cleanup(){ kill "$PID" 2>/dev/null || true; wait "$PID" 2>/dev/null || true; }
trap cleanup EXIT

for _ in $(seq 1 100); do
  if curl -fsS -c "$COOKIES" -b "$COOKIES" "$BASE/setup.php" -o "$EVID/setup.html"; then break; fi
  sleep .2
done
test -s "$EVID/setup.html"
setup_csrf=$(python3 - "$EVID/setup.html" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read()
m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s)
assert m
print(m.group(1))
PY
)
curl -fsS -c "$COOKIES" -b "$COOKIES" -X POST "$BASE/setup.php"   --data-urlencode "setup_csrf=$setup_csrf"   --data-urlencode 'site_title=P01 HTTP E2E'   --data-urlencode 'admin_password=vf-http-e2e'   --data-urlencode 'admin_password_confirm=vf-http-e2e'   -o "$EVID/setup-post.html"

ROOT="$SITE" BRIDGE="$BRIDGE" php <<'PHP'
<?php
declare(strict_types=1);
$root=getenv('ROOT');
require $root.'/app/bootstrap.php';
define('VF_P01_V24710_AUTH_BRIDGE_LIBRARY_MODE', true);
require getenv('BRIDGE');
$r=VfP01V24710AuthBridge::run($root);
if (empty($r['ok'])) exit(1);
PHP

# Login through the real API to establish the exact session/cookie/CSRF path.
login=$(curl -fsS -c "$COOKIES" -b "$COOKIES" -H 'Content-Type: application/json'   --data '{"password":"vf-http-e2e"}' "$BASE/api.php?action=login")
printf '%s' "$login" >"$EVID/login.json"
csrf=$(jq -r '.csrf // empty' <<<"$login")
test -n "$csrf"

# Seed one business row through the exact same database runtime before update.
ROOT="$SITE" php <<'PHP'
<?php
declare(strict_types=1);
require getenv('ROOT').'/app/FunctionalWorkspaceCore.php';
$db=vf_db(); $repo=new VfRepository($db);
$cat=$repo->createCategory(['name'=>'HTTP E2E Preserve','description'=>'real API update','is_private'=>0,'sort_order'=>100]);
$repo->saveLink(null,['title'=>'HTTP E2E Preserve Link','url'=>'https://http-e2e.example/item','surface'=>'start','tags'=>['http-e2e'],'category_id'=>$cat],'manual');
PHP

call_post(){
  local action="$1" payload="$2" out="$3"
  curl -sS -D "$out.headers" -o "$out" -w '%{http_code}'     -c "$COOKIES" -b "$COOKIES"     -H 'Content-Type: application/json'     -H "X-CSRF-Token: $csrf"     --data "$payload" "$BASE/api.php?action=$action"
}

code=$(call_post update_check '{}' "$EVID/check.json")
test "$code" = "200"
jq -e '.ok==true and .result.latest_version=="2.47.12" and .result.can_update==true' "$EVID/check.json" >/dev/null

code=$(call_post update_prepare '{}' "$EVID/prepare.json")
test "$code" = "200"
jq -e '.ok==true and .result.to_version=="2.47.12"' "$EVID/prepare.json" >/dev/null
op=$(jq -r '.result.operation_id' "$EVID/prepare.json")
test -n "$op"

code=$(call_post update_install "$(jq -nc --arg op "$op" '{operation_id:$op}')" "$EVID/install.json")
echo "INSTALL_HTTP_CODE=$code"
cat "$EVID/install.json"
echo
test "$code" = "200"
jq -e '.ok==true and .result.updated==true and .result.to_version=="2.47.12"' "$EVID/install.json" >/dev/null

# New request after source replacement: verify runtime really presents target version.
boot=$(curl -fsS -c "$COOKIES" -b "$COOKIES" "$BASE/api.php?action=bootstrap")
printf '%s' "$boot" >"$EVID/bootstrap-after.json"
jq -e '.ok==true and .version=="2.47.12"' "$EVID/bootstrap-after.json" >/dev/null

ROOT="$SITE" php <<'PHP'
<?php
declare(strict_types=1);
require getenv('ROOT').'/app/FunctionalWorkspaceCore.php';
if ((int)vf_db()->query("SELECT COUNT(*) FROM links WHERE title='HTTP E2E Preserve Link'")->fetchColumn()!==1) exit(1);
PHP

cat >"$EVID/receipt.txt" <<EOF
P01_SOURCE_BASELINE=972541fd06c66044105ec1b19cf7738c340c90c1
TARGET_VERSION=2.47.12
REAL_HTTP_LOGIN=PASS
REAL_HTTP_CSRF=PASS
REAL_HTTP_UPDATE_CHECK=PASS
REAL_HTTP_UPDATE_PREPARE=PASS
REAL_HTTP_UPDATE_INSTALL=PASS
POST_UPDATE_NEW_HTTP_REQUEST=PASS
BUSINESS_DATA_PRESERVATION=PASS
P01_V24712_REAL_HTTP_UPDATE_E2E=PASS
EOF
cat "$EVID/receipt.txt"
