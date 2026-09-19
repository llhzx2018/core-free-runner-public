#!/usr/bin/env bash
set -Eeuo pipefail

PRODUCT="$GITHUB_WORKSPACE/product"
SOURCE35="$GITHUB_WORKSPACE/source35"
SOURCE36="$GITHUB_WORKSPACE/source36"

test "$(git -C "$PRODUCT" rev-parse HEAD)" = "$EXPECTED_PRESEAL"
test "$(tr -d '\r\n' < "$PRODUCT/VERSION")" = "$TARGET_VERSION"

echo 'P02_OWNER_PREVIEW_RUNTIME_APPLICABILITY=N_A_PUBLISH_FIRST_OWNER_AUTHORIZATION'
echo 'P02_PUBLIC_AUTHORITY_INSTALL=REQUIRED'
echo 'P02_PUBLIC_AUTHORITY_SECURITY=REQUIRED'
echo 'P02_PUBLIC_AUTHORITY_TESTING=REQUIRED'
echo 'P02_PUBLIC_AUTHORITY_UPGRADE=REQUIRED'
echo 'P02_PUBLIC_AUTHORITY_DATA_SCHEMA=REQUIRED'
echo 'P02_PUBLIC_AUTHORITY_GIT=REQUIRED'
echo 'P02_PUBLIC_AUTHORITY_UA_UI=REQUIRED'
echo 'P02_PUBLIC_AUTHORITY_API_PROVIDER=N_A'
echo 'P02_PUBLIC_AUTHORITY_SEO=N_A'
echo 'P02_PUBLIC_AUTHORITY_CRON_JOB=N_A'
echo 'P02_PUBLIC_AUTHORITY_NOTIFICATION=N_A'
echo 'P02_PUBLIC_AUTHORITY_OBSERVABILITY=N_A_RELEASE_ONLY'
echo 'P02_PUBLIC_AUTHORITY_PERFORMANCE=N_A'
echo 'P02_PUBLIC_AUTHORITY_NO_UNKNOWN=YES'
grep -F 'DYNAMIC_TRUTH_NOT_STORED_HERE' "$PRODUCT/docs/authority/CURRENT.md" >/dev/null
jq -e '((has("candidate_version")|not) and (has("production_version")|not) and (has("release_tag")|not))' "$PRODUCT/VF_PROJECT.json" >/dev/null
echo P02_PRE_RELEASE_AUTHORITY_DRIFT_GATE=PASS

cd "$PRODUCT"
python3 scripts/generate-source-manifest.py
test "$(jq -r .version SOURCE_MANIFEST.json)" = "$TARGET_VERSION"
test "$(jq -r .schema SOURCE_MANIFEST.json)" = "$SCHEMA"
test "$(jq -r .runtime_source_file_count SOURCE_MANIFEST.json)" = 71
python3 scripts/verify-source-manifest.py
git diff --check

git config user.name VictorForge
git config user.email llhzx2018@gmail.com
git add SOURCE_MANIFEST.json SOURCE_MANIFEST.txt
if ! git diff --cached --quiet; then
  git commit -m 'chore(P02): reseal V2.5.38 source manifest'
fi
git push origin "HEAD:$PRODUCT_BRANCH"
FINAL_REF="$(git rev-parse HEAD)"
FINAL_TREE="$(git show -s --format=%T "$FINAL_REF")"
echo "P02_V2538_FINAL_REF=$FINAL_REF"
echo "P02_V2538_FINAL_TREE=$FINAL_TREE"

bash scripts/verify-repository.sh
while IFS= read -r cmd; do
  test -n "$cmd"
  eval "$cmd"
done < <(awk '/run: node tests\/unit\//{sub(/^.*run: /,""); print}' .github/workflows/repository-health.yml)
node --check public/assets/app.js
node --check public/assets/v2537-inkstone-shell.js
git diff --check
echo P02_V2538_REPOSITORY_AND_UNIT_GATE=PASS

npm install --no-save --no-package-lock playwright@1.55.0 >/dev/null
npx playwright install --with-deps chromium >/dev/null
bash scripts/ux-browser-reverify.sh
echo P02_V2538_REAL_CHROMIUM_GATE=PASS

python3 "$GITHUB_WORKSPACE/tmp/p02-v2538-formalize.py"
for z in build/formal-a/VF_Library_V2.5.38_UPDATE.zip build/formal-a/VF_Library_V2.5.38_FULL.zip build/formal-a/VF_Library_V2.5.38_ATOMIC.zip; do
  unzip -t "$z" >/dev/null
done
unzip -p build/formal-a/VF_Library_V2.5.38_UPDATE.zip atomic-manifest.json |
  jq -e '.format_version==2 and .source_versions==["2.5.36","2.5.37"] and .target_version=="2.5.38" and .source_schema==2401 and .target_schema==2401' >/dev/null
grep -F "const VF_REPAIR_SOURCES_JSON = '[\"2.5.36\",\"2.5.37\"]';" build/formal-a/repair-v2.5.38.php >/dev/null
echo P02_V2538_FORMAL_ARCHIVE_IDENTITY=PASS

# Fresh install exact formal FULL.
FRESH_ROOT="$RUNNER_TEMP/fresh2537"
FRESH_SITE="$FRESH_ROOT/site"
mkdir -p "$FRESH_SITE"
unzip -q build/formal-a/VF_Library_V2.5.38_FULL.zip -d "$FRESH_SITE"
test "$(cat "$FRESH_SITE/VERSION.txt")" = "$TARGET_VERSION"
test -f "$FRESH_SITE/assets/v2537-inkstone.css"
test -f "$FRESH_SITE/assets/v2537-inkstone-shell.js"
FRESH_PW="P02-V2537-FRESH-${GITHUB_RUN_ID}!"
FRESH_PORT=21538
php -S 127.0.0.1:$FRESH_PORT -t "$FRESH_SITE" >/dev/null 2>&1 &
FRESH_PID=$!
cleanup_fresh(){ kill "$FRESH_PID" 2>/dev/null || true; }
trap cleanup_fresh EXIT
for _ in $(seq 1 80); do
  curl -fsS "http://127.0.0.1:$FRESH_PORT/setup.php" >/dev/null 2>&1 && break
  sleep .25
done
curl -fsS -c "$FRESH_ROOT/c" "http://127.0.0.1:$FRESH_PORT/setup.php" > "$FRESH_ROOT/setup"
FRESH_TOKEN=$(python3 - "$FRESH_ROOT/setup" <<'PY'
import re,html,sys
s=open(sys.argv[1],encoding='utf-8').read()
m=re.search(r'name="setup_csrf" value="([^"]+)"',s)
assert m
print(html.unescape(m.group(1)))
PY
)
test "$(curl -sS -o /dev/null -w '%{http_code}' -b "$FRESH_ROOT/c" -c "$FRESH_ROOT/c" \
  -H "Origin: http://127.0.0.1:$FRESH_PORT" \
  --data-urlencode "setup_csrf=$FRESH_TOKEN" \
  --data-urlencode "password=$FRESH_PW" \
  --data-urlencode "password_confirm=$FRESH_PW" \
  "http://127.0.0.1:$FRESH_PORT/setup.php")" = 303
php "$FRESH_SITE/cli/verify.php" |
  jq -e '.ok==true and .version=="2.5.38" and .schema_version==2401 and .integrity=="ok" and .foreign_key_errors==0' >/dev/null
kill "$FRESH_PID"; wait "$FRESH_PID" 2>/dev/null || true
trap - EXIT
echo P02_V2538_FULL_FRESH_INSTALL=PASS

setup_case(){
  local SITE="$1"
  local CASE_ROOT="$2"
  local PORT="$3"
  local PW="$4"
  php -S 127.0.0.1:$PORT -t "$SITE" >"$CASE_ROOT/php.log" 2>&1 &
  CASE_PID=$!
  for _ in $(seq 1 80); do curl -fsS "http://127.0.0.1:$PORT/setup.php" >/dev/null 2>&1 && break; sleep .25; done
  curl -fsS -c "$CASE_ROOT/c" "http://127.0.0.1:$PORT/setup.php" > "$CASE_ROOT/setup"
  local TOKEN
  TOKEN=$(python3 - "$CASE_ROOT/setup" <<'PY'
import re,html,sys
s=open(sys.argv[1],encoding='utf-8').read()
m=re.search(r'name="setup_csrf" value="([^"]+)"',s)
assert m
print(html.unescape(m.group(1)))
PY
)
  test "$(curl -sS -o /dev/null -w '%{http_code}' -b "$CASE_ROOT/c" -c "$CASE_ROOT/c" \
    -H "Origin: http://127.0.0.1:$PORT" \
    --data-urlencode "setup_csrf=$TOKEN" --data-urlencode "password=$PW" --data-urlencode "password_confirm=$PW" \
    "http://127.0.0.1:$PORT/setup.php")" = 303
}

seed_case(){
  local CASE_ROOT="$1"
  local PORT="$2"
  local SRCVER="$3"
  local SESSION CSRF CAT CID ITEM SAVED
  SESSION=$(curl -fsS -b "$CASE_ROOT/c" "http://127.0.0.1:$PORT/api.php?action=session")
  CSRF=$(jq -r .csrf <<<"$SESSION")
  CAT=$(curl -fsS -b "$CASE_ROOT/c" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
    -d '{"name":"V2537 Preserve","icon":"folder"}' "http://127.0.0.1:$PORT/api.php?action=category_save")
  CID=$(jq -r .id <<<"$CAT")
  ITEM=$(jq -nc --argjson cid "$CID" --arg src "$SRCVER" \
    '{category_id:$cid,title:("P02 Inkstone Preserve "+$src),content:("keep-inkstone-"+$src),content_mode:"article",content_format:"markdown",primary_action:"read",status:"active"}')
  SAVED=$(curl -fsS -b "$CASE_ROOT/c" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
    -d "$ITEM" "http://127.0.0.1:$PORT/api.php?action=content_save")
  CASE_ITEM_ID=$(jq -r .id <<<"$SAVED")
  curl -fsS -b "$CASE_ROOT/c" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
    -d "{\"id\":$CASE_ITEM_ID,\"favorite\":true}" "http://127.0.0.1:$PORT/api.php?action=content_favorite" | jq -e .ok >/dev/null
}

verify_case(){
  local SITE="$1"
  local CASE_ROOT="$2"
  local PORT="$3"
  local SRCVER="$4"
  local IID="$5"
  test "$(cat "$SITE/VERSION.txt")" = "$TARGET_VERSION"
  test -f "$SITE/assets/v2537-inkstone.css"
  test -f "$SITE/assets/v2537-inkstone-shell.js"
  curl -fsS -b "$CASE_ROOT/c" "http://127.0.0.1:$PORT/api.php?action=content_get&id=$IID" |
    jq -e --arg src "$SRCVER" '(.item.is_favorite|tonumber)==1 and .item.content==("keep-inkstone-"+$src)' >/dev/null
  php "$SITE/cli/verify.php" |
    jq -e '.ok==true and .version=="2.5.38" and .schema_version==2401 and .integrity=="ok" and .foreign_key_errors==0' >/dev/null
}

UPDATE_PKG="$PRODUCT/build/formal-a/VF_Library_V2.5.38_UPDATE.zip"
UPDATE_BYTES=$(stat -c%s "$UPDATE_PKG")
UPDATE_SHA=$(sha256sum "$UPDATE_PKG" | awk '{print $1}')
cat > "$RUNNER_TEMP/update-upgrade.php" <<'PHP'
<?php
$site=$argv[1];$pkg=$argv[2];$source=$argv[3];$bytes=(int)$argv[4];$sha=$argv[5];$out=$argv[6];
require $site.'/app/bootstrap.php';
require_once $site.'/app/CoreUpdates/UpdateAdapter.php';
require_once $site.'/app/CoreUpdates/UpdateCore.php';
require_once $site.'/app/VfLibraryCoreUpdateAdapter.php';
$m=[
 'schema_version'=>'1.0','project_id'=>'P02','component_id'=>'APP','enabled'=>true,
 'current_version'=>$source,'target_version'=>'2.5.38','update_type'=>'ATOMIC',
 'from_versions'=>['2.5.36','2.5.37'],'schema_from'=>'2401','schema_to'=>'2401',
 'repository'=>'llhzx2018/vf-library','release_tag'=>'v2.5.38',
 'asset_name'=>'VF_Library_V2.5.38_UPDATE.zip','asset_bytes'=>$bytes,'asset_sha256'=>$sha,
 'backup_required'=>true,'rollback_supported'=>true,'released_at'=>'2026-09-19T00:00:00Z'
];
$core=new CoreUpdates\UpdateCore('P02','APP');
if(($core->check($source,'2401',$m)['status']??'')!=='AVAILABLE')exit(2);
if(($core->verifyPackage($pkg,$m)['status']??'')!=='VERIFIED')exit(3);
$r=$core->upgrade($source,'2401',new VfLibraryCoreUpdateAdapter(),$pkg,$m);
file_put_contents($out,json_encode($r));
if(!in_array($r['status']??'',['COMMITTED','COMMITTED_WITH_CLEANUP_WARNING'],true)||empty($r['backup_locator']))exit(4);
PHP

update_case(){
  local SRC_DIR="$1" SRCVER="$2" PORT="$3"
  local CASE_ROOT="$RUNNER_TEMP/update-${SRCVER//./-}"
  local SITE="$CASE_ROOT/site"
  local PW="P02-UP-${SRCVER}-${GITHUB_RUN_ID}!"
  rm -rf "$CASE_ROOT"; mkdir -p "$SITE"
  bash "$SRC_DIR/scripts/build-deploy-tree.sh" "$SITE" >/dev/null
  test "$(cat "$SITE/VERSION.txt")" = "$SRCVER"
  setup_case "$SITE" "$CASE_ROOT" "$PORT" "$PW"
  seed_case "$CASE_ROOT" "$PORT" "$SRCVER"
  local IID="$CASE_ITEM_ID"
  php "$RUNNER_TEMP/update-upgrade.php" "$SITE" "$UPDATE_PKG" "$SRCVER" "$UPDATE_BYTES" "$UPDATE_SHA" "$CASE_ROOT/result"
  jq -e '.backup_locator|length>0' "$CASE_ROOT/result" >/dev/null
  verify_case "$SITE" "$CASE_ROOT" "$PORT" "$SRCVER" "$IID"
  kill "$CASE_PID"; wait "$CASE_PID" 2>/dev/null || true
  echo "P02_V2538_UPDATE_FROM_${SRCVER}=PASS"
}

update_case "$SOURCE35" "$SOURCE35_VERSION" 21635
update_case "$SOURCE36" "$SOURCE36_VERSION" 21636
echo P02_V2538_MULTI_SOURCE_UPDATE_GATE=PASS

# Browser Repair from exact V2.5.37 (latest published source baseline).
RP_ROOT="$RUNNER_TEMP/repair-2536"
RP_SITE="$RP_ROOT/site"
rm -rf "$RP_ROOT"; mkdir -p "$RP_SITE"
bash "$SOURCE36/scripts/build-deploy-tree.sh" "$RP_SITE" >/dev/null
test "$(cat "$RP_SITE/VERSION.txt")" = "2.5.37"
setup_case "$RP_SITE" "$RP_ROOT" 21736 "P02-REPAIR-2536-${GITHUB_RUN_ID}!"
seed_case "$RP_ROOT" 21736 "2.5.37"
RP_ITEM="$CASE_ITEM_ID"
cp "$PRODUCT/build/formal-a/repair-v2.5.38.php" "$RP_SITE/repair-v2.5.38.php"
curl -fsS -b "$RP_ROOT/c" "http://127.0.0.1:21736/repair-v2.5.38.php" > "$RP_ROOT/repair-page"
grep -F "允许来源：2.5.36 / 2.5.37；当前：2.5.37" "$RP_ROOT/repair-page" >/dev/null
REPAIR_CSRF=$(python3 - "$RP_ROOT/repair-page" <<'PY'
import re,html,sys
s=open(sys.argv[1],encoding='utf-8').read()
m=re.search(r'name="csrf" value="([^"]+)"',s)
assert m
print(html.unescape(m.group(1)))
PY
)
curl -fsS -b "$RP_ROOT/c" -c "$RP_ROOT/c" \
  -H "Origin: http://127.0.0.1:21736" \
  --data-urlencode "action=upgrade" \
  --data-urlencode "csrf=$REPAIR_CSRF" \
  "http://127.0.0.1:21736/repair-v2.5.38.php" > "$RP_ROOT/repair-result"
grep -F "升级完成" "$RP_ROOT/repair-result" >/dev/null
test ! -e "$RP_SITE/repair-v2.5.38.php"
verify_case "$RP_SITE" "$RP_ROOT" 21736 "2.5.37" "$RP_ITEM"
kill "$CASE_PID"; wait "$CASE_PID" 2>/dev/null || true
echo P02_V2538_REPAIR_WEB_FROM_2.5.37=PASS

export GH_TOKEN="$RELEASE_TOKEN"
if gh release view v2.5.38 --repo llhzx2018/vf-library >/dev/null 2>&1; then
  echo "v2.5.38 already exists; refusing to mutate an existing formal release" >&2
  exit 1
fi
gh release create v2.5.38 build/formal-a/* \
  --repo llhzx2018/vf-library \
  --target "$FINAL_REF" \
  --title 'VF Library V2.5.38' \
  --notes-file build/formal-a/VF_Library_V2.5.38_RELEASE_NOTES.md

gh release view v2.5.38 --repo llhzx2018/vf-library \
  --json databaseId,tagName,isDraft,isPrerelease,publishedAt > "$RUNNER_TEMP/release2537.json"
jq -e '.tagName=="v2.5.38" and .isDraft==false and .isPrerelease==false' "$RUNNER_TEMP/release2537.json" >/dev/null
mkdir -p "$RUNNER_TEMP/readback2537"
gh release download v2.5.38 --repo llhzx2018/vf-library \
  --pattern 'VF_Library_V2.5.38_UPDATE.zip' --pattern 'repair-v2.5.38.php' --dir "$RUNNER_TEMP/readback2537"
RBYTES=$(stat -c%s "$RUNNER_TEMP/readback2537/VF_Library_V2.5.38_UPDATE.zip")
RSHA=$(sha256sum "$RUNNER_TEMP/readback2537/VF_Library_V2.5.38_UPDATE.zip" | awk '{print $1}')
REPAIR_SHA=$(sha256sum "$RUNNER_TEMP/readback2537/repair-v2.5.38.php" | awk '{print $1}')
test "$RBYTES" = "$(stat -c%s build/formal-a/VF_Library_V2.5.38_UPDATE.zip)"
test "$RSHA" = "$(sha256sum build/formal-a/VF_Library_V2.5.38_UPDATE.zip | awk '{print $1}')"
test "$REPAIR_SHA" = "$(sha256sum build/formal-a/repair-v2.5.38.php | awk '{print $1}')"
TAGSHA=$(gh api repos/llhzx2018/vf-library/git/ref/tags/v2.5.38 --jq .object.sha)
test "$TAGSHA" = "$FINAL_REF"

echo "P02_RELEASE_ID=$(jq -r .databaseId "$RUNNER_TEMP/release2537.json")"
echo "P02_PUBLISHED_AT=$(jq -r .publishedAt "$RUNNER_TEMP/release2537.json")"
echo "P02_UPDATE_BYTES=$RBYTES"
echo "P02_UPDATE_SHA256=$RSHA"
echo "P02_REPAIR_SHA256=$REPAIR_SHA"
echo "P02_TAG_SHA=$TAGSHA"
echo P02_V2538_FORMAL_RELEASE_REMOTE_READBACK=PASS
echo P02_PRODUCTION_WRITE=NO
