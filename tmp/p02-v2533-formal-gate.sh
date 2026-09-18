#!/usr/bin/env bash
set -Eeuo pipefail

PRODUCT="$GITHUB_WORKSPACE/product"
SOURCE31="$GITHUB_WORKSPACE/source31"
SOURCE32="$GITHUB_WORKSPACE/source32"

test "$(git -C "$PRODUCT" rev-parse HEAD)" = "$PRODUCT_REF"
test "$(git -C "$SOURCE31" rev-parse HEAD)" = "$SOURCE31_REF"
test "$(git -C "$SOURCE32" rev-parse HEAD)" = "$SOURCE32_REF"
test "$(tr -d '\r\n' < "$PRODUCT/VERSION")" = "$TARGET_VERSION"
test "$(tr -d '\r\n' < "$SOURCE31/VERSION")" = "$SOURCE31_VERSION"
test "$(tr -d '\r\n' < "$SOURCE32/VERSION")" = "$SOURCE32_VERSION"
test "$(jq -r .version "$PRODUCT/SOURCE_MANIFEST.json")" = "$TARGET_VERSION"
test "$(jq -r .schema "$PRODUCT/SOURCE_MANIFEST.json")" = "$SCHEMA"
test "$(jq -r .runtime_source_file_count "$PRODUCT/SOURCE_MANIFEST.json")" = 67

cd "$PRODUCT"
bash scripts/verify-repository.sh
while IFS= read -r cmd; do
  test -n "$cmd"
  eval "$cmd"
done < <(awk '/run: node tests\/unit\//{sub(/^.*run: /,""); print}' .github/workflows/repository-health.yml)
git diff --check
echo P02_V2533_EXACT_SOURCE_GATE=PASS

npm install --no-save --no-package-lock playwright@1.55.0 >/dev/null
npx playwright install --with-deps chromium >/dev/null
bash scripts/ux-browser-reverify.sh
echo P02_V2533_REAL_CHROMIUM_GATE=PASS

python3 "$GITHUB_WORKSPACE/tmp/p02-v2533-formalize.py"
for z in build/formal-a/VF_Library_V2.5.33_UPDATE.zip build/formal-a/VF_Library_V2.5.33_FULL.zip build/formal-a/VF_Library_V2.5.33_ATOMIC.zip; do
  unzip -t "$z" >/dev/null
done
unzip -p build/formal-a/VF_Library_V2.5.33_UPDATE.zip atomic-manifest.json |
  jq -e '.format_version==2 and .source_versions==["2.5.31","2.5.32"] and .target_version=="2.5.33" and .source_schema==2401 and .target_schema==2401' >/dev/null
echo P02_V2533_FORMAL_ARCHIVE_IDENTITY=PASS

FRESH_ROOT="$RUNNER_TEMP/fresh2533"
FRESH_SITE="$FRESH_ROOT/site"
mkdir -p "$FRESH_SITE"
unzip -q build/formal-a/VF_Library_V2.5.33_FULL.zip -d "$FRESH_SITE"
test "$(cat "$FRESH_SITE/VERSION.txt")" = "$TARGET_VERSION"
FRESH_PW="P02-V2533-FRESH-${GITHUB_RUN_ID}!"
FRESH_PORT=18433
php -S 127.0.0.1:$FRESH_PORT -t "$FRESH_SITE" >/dev/null 2>&1 &
FRESH_PID=$!
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
  jq -e '.ok==true and .version=="2.5.33" and .schema_version==2401 and .integrity=="ok" and .foreign_key_errors==0' >/dev/null
kill "$FRESH_PID"
wait "$FRESH_PID" 2>/dev/null || true
echo P02_V2533_FULL_FRESH_INSTALL=PASS

PKG="$PRODUCT/build/formal-a/VF_Library_V2.5.33_UPDATE.zip"
BYTES=$(stat -c%s "$PKG")
SHA=$(sha256sum "$PKG" | awk '{print $1}')
cat > "$RUNNER_TEMP/upgrade.php" <<'PHP'
<?php
$site=$argv[1];$pkg=$argv[2];$source=$argv[3];$bytes=(int)$argv[4];$sha=$argv[5];$out=$argv[6];
require $site.'/app/bootstrap.php';
require_once $site.'/app/CoreUpdates/UpdateAdapter.php';
require_once $site.'/app/CoreUpdates/UpdateCore.php';
require_once $site.'/app/VfLibraryCoreUpdateAdapter.php';
$m=[
 'schema_version'=>'1.0','project_id'=>'P02','component_id'=>'APP','enabled'=>true,
 'current_version'=>$source,'target_version'=>'2.5.33','update_type'=>'ATOMIC',
 'from_versions'=>['2.5.31','2.5.32'],'schema_from'=>'2401','schema_to'=>'2401',
 'repository'=>'llhzx2018/vf-library','release_tag'=>'v2.5.33',
 'asset_name'=>'VF_Library_V2.5.33_UPDATE.zip','asset_bytes'=>$bytes,'asset_sha256'=>$sha,
 'backup_required'=>true,'rollback_supported'=>true,'released_at'=>'2026-09-18T00:00:00Z'
];
$c=new CoreUpdates\UpdateCore('P02','APP');
if(($c->check($source,'2401',$m)['status']??'')!=='AVAILABLE')exit(2);
if(($c->verifyPackage($pkg,$m)['status']??'')!=='VERIFIED')exit(3);
$r=$c->upgrade($source,'2401',new VfLibraryCoreUpdateAdapter(),$pkg,$m);
file_put_contents($out,json_encode($r));
if(!in_array($r['status']??'',['COMMITTED','COMMITTED_WITH_CLEANUP_WARNING'],true)||empty($r['backup_locator']))exit(4);
PHP

upgrade_case(){
  local SRC_DIR="$1"
  local SRCVER="$2"
  local PORT="$3"
  local CASE_ROOT="$RUNNER_TEMP/up-${SRCVER//./-}"
  local SITE="$CASE_ROOT/site"
  rm -rf "$CASE_ROOT"
  mkdir -p "$SITE"
  bash "$SRC_DIR/scripts/build-deploy-tree.sh" "$SITE" >/dev/null
  test "$(cat "$SITE/VERSION.txt")" = "$SRCVER"

  local PW="P02-UP-${SRCVER}-${GITHUB_RUN_ID}!"
  php -S 127.0.0.1:$PORT -t "$SITE" >/dev/null 2>&1 &
  local PID=$!
  for _ in $(seq 1 80); do
    curl -fsS "http://127.0.0.1:$PORT/setup.php" >/dev/null 2>&1 && break
    sleep .25
  done
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
    --data-urlencode "setup_csrf=$TOKEN" \
    --data-urlencode "password=$PW" \
    --data-urlencode "password_confirm=$PW" \
    "http://127.0.0.1:$PORT/setup.php")" = 303

  local SESSION CSRF CAT CID ITEM SAVED IID
  SESSION=$(curl -fsS -b "$CASE_ROOT/c" "http://127.0.0.1:$PORT/api.php?action=session")
  CSRF=$(jq -r .csrf <<<"$SESSION")
  CAT=$(curl -fsS -b "$CASE_ROOT/c" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
    -d '{"name":"Upgrade Preserve","icon":"folder"}' "http://127.0.0.1:$PORT/api.php?action=category_save")
  CID=$(jq -r .id <<<"$CAT")
  ITEM=$(jq -nc --argjson cid "$CID" --arg src "$SRCVER" \
    '{category_id:$cid,title:("P02 Preserve "+$src),content:("keep-"+$src),content_mode:"article",content_format:"markdown",primary_action:"read",status:"active"}')
  SAVED=$(curl -fsS -b "$CASE_ROOT/c" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
    -d "$ITEM" "http://127.0.0.1:$PORT/api.php?action=content_save")
  IID=$(jq -r .id <<<"$SAVED")
  curl -fsS -b "$CASE_ROOT/c" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
    -d "{\"id\":$IID,\"favorite\":true}" "http://127.0.0.1:$PORT/api.php?action=content_favorite" |
    jq -e .ok >/dev/null

  php "$RUNNER_TEMP/upgrade.php" "$SITE" "$PKG" "$SRCVER" "$BYTES" "$SHA" "$CASE_ROOT/result"
  test "$(cat "$SITE/VERSION.txt")" = "$TARGET_VERSION"
  jq -e '.backup_locator|length>0' "$CASE_ROOT/result" >/dev/null
  curl -fsS -b "$CASE_ROOT/c" "http://127.0.0.1:$PORT/api.php?action=content_get&id=$IID" |
    jq -e --arg src "$SRCVER" '(.item.is_favorite|tonumber)==1 and .item.content==("keep-"+$src)' >/dev/null
  php "$SITE/cli/verify.php" |
    jq -e '.ok==true and .version=="2.5.33" and .schema_version==2401 and .integrity=="ok" and .foreign_key_errors==0' >/dev/null
  kill "$PID"
  wait "$PID" 2>/dev/null || true
  echo "P02_V2533_ATOMIC_FROM_${SRCVER}=PASS"
}

upgrade_case "$SOURCE31" "$SOURCE31_VERSION" 18431
upgrade_case "$SOURCE32" "$SOURCE32_VERSION" 18432
echo P02_V2533_MULTI_SOURCE_UPGRADE_GATE=PASS

export GH_TOKEN="$RELEASE_TOKEN"
if gh release view v2.5.33 --repo llhzx2018/vf-library >/dev/null 2>&1; then
  echo "v2.5.33 already exists; refusing to mutate an existing formal release" >&2
  exit 1
fi
gh release create v2.5.33 build/formal-a/* \
  --repo llhzx2018/vf-library \
  --target "$PRODUCT_REF" \
  --title 'VF Library V2.5.33' \
  --notes-file build/formal-a/VF_Library_V2.5.33_RELEASE_NOTES.md

gh release view v2.5.33 --repo llhzx2018/vf-library \
  --json databaseId,tagName,isDraft,isPrerelease,publishedAt > "$RUNNER_TEMP/release2533.json"
jq -e '.tagName=="v2.5.33" and .isDraft==false and .isPrerelease==false' "$RUNNER_TEMP/release2533.json" >/dev/null

mkdir -p "$RUNNER_TEMP/readback2533"
gh release download v2.5.33 --repo llhzx2018/vf-library \
  --pattern 'VF_Library_V2.5.33_UPDATE.zip' --dir "$RUNNER_TEMP/readback2533"
RBYTES=$(stat -c%s "$RUNNER_TEMP/readback2533/VF_Library_V2.5.33_UPDATE.zip")
RSHA=$(sha256sum "$RUNNER_TEMP/readback2533/VF_Library_V2.5.33_UPDATE.zip" | awk '{print $1}')
test "$RBYTES" = "$(stat -c%s build/formal-a/VF_Library_V2.5.33_UPDATE.zip)"
test "$RSHA" = "$(sha256sum build/formal-a/VF_Library_V2.5.33_UPDATE.zip | awk '{print $1}')"
TAGSHA=$(gh api repos/llhzx2018/vf-library/git/ref/tags/v2.5.33 --jq .object.sha)
test "$TAGSHA" = "$PRODUCT_REF"

echo "P02_RELEASE_ID=$(jq -r .databaseId "$RUNNER_TEMP/release2533.json")"
echo "P02_PUBLISHED_AT=$(jq -r .publishedAt "$RUNNER_TEMP/release2533.json")"
echo "P02_UPDATE_BYTES=$RBYTES"
echo "P02_UPDATE_SHA256=$RSHA"
echo "P02_TAG_SHA=$TAGSHA"
echo P02_V2533_FORMAL_RELEASE_REMOTE_READBACK=PASS
echo P02_PRODUCTION_WRITE=NO
