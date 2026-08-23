#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo ERROR_LINE=$LINENO' ERR
ROOT="$(pwd)"
cd product

test "$(git rev-parse HEAD)" = "${PRODUCT_REF:?}"
test "$(tr -d '\r\n' < VERSION)" = "2.5.26"
test "$(jq -r .version SOURCE_MANIFEST.json)" = "2.5.26"
test "$(jq -r .schema SOURCE_MANIFEST.json)" = "2401"
test "$(jq -r .runtime_source_file_count SOURCE_MANIFEST.json)" = "76"
find public src tests/integration -name '*.php' -print0 | xargs -0 -n1 php -l >/dev/null
node --check public/assets/app.js
node --check public/assets/scratch-tabs.js
node tests/unit/v2521_context_ux_contract.mjs
node tests/unit/v2522_unified_library_workspace_contract.mjs
node tests/unit/v2523_unified_content_workspace_contract.mjs
node tests/unit/v2526_interaction_refresh_contract.mjs
python3 scripts/verify-source-manifest.py
python3 scripts/repository-gates.py
git diff --check
echo EXACT_SOURCE_AND_STATIC_CONTRACTS=PASS

SITE="$RUNNER_TEMP/v2526-site"
mkdir -p "$SITE"
bash scripts/build-deploy-tree.sh "$SITE" >/dev/null
test "$(cat "$SITE/VERSION.txt")" = "2.5.26"
PORT=18326
php -d display_errors=0 -S "127.0.0.1:$PORT" -t "$SITE" >"$RUNNER_TEMP/v2526-http.log" 2>&1 &
SITE_PID=$!
cleanup(){ kill "$SITE_PID" 2>/dev/null || true; wait "$SITE_PID" 2>/dev/null || true; }
trap cleanup EXIT
for _ in $(seq 1 80); do curl -fsS "http://127.0.0.1:$PORT/setup.php" >/dev/null 2>&1 && break; sleep .25; done
curl -fsS -c "$RUNNER_TEMP/v2526-cookies" "http://127.0.0.1:$PORT/setup.php" >"$RUNNER_TEMP/v2526-setup.html"
TOKEN=$(python3 - "$RUNNER_TEMP/v2526-setup.html" <<'PY'
import html,re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="setup_csrf" value="([^"]+)"',s);assert m;print(html.unescape(m.group(1)))
PY
)
test "$(curl -sS -o /dev/null -w '%{http_code}' -b "$RUNNER_TEMP/v2526-cookies" -c "$RUNNER_TEMP/v2526-cookies" -H "Origin: http://127.0.0.1:$PORT" --data-urlencode "setup_csrf=$TOKEN" --data-urlencode "password=$TEST_PASSWORD" --data-urlencode "password_confirm=$TEST_PASSWORD" "http://127.0.0.1:$PORT/setup.php")" = "303"

cat >"$RUNNER_TEMP/v2526-seed.php" <<'PHP'
<?php
$site=$argv[1];$out=$argv[2];require $site.'/app/bootstrap.php';
$db=vftb_db();$org=new VfLibraryOrganizationService($db);$items=new VfLibraryItemService($db);
$cid=$org->save(null,['name'=>'V2526 Interaction']);
$id=$items->saveItem(null,['category_id'=>$cid,'title'=>'Favorite Refresh Fixture','content'=>'refresh fixture','content_mode'=>'article','content_format'=>'markdown','primary_action'=>'read','status'=>'active']);
file_put_contents($out,json_encode(['item_id'=>$id,'category_id'=>$cid]));
PHP
php "$RUNNER_TEMP/v2526-seed.php" "$SITE" "$RUNNER_TEMP/v2526-seed.json"
ITEM_ID=$(jq -r .item_id "$RUNNER_TEMP/v2526-seed.json")

cat >"$ROOT/v2526-browser.mjs" <<'JS'
import {chromium} from 'playwright';
const base=process.env.BASE_URL,password=process.env.TEST_PASSWORD,id=Number(process.env.ITEM_ID);
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1365,height:900}});
const errors=[];page.on('pageerror',error=>errors.push(String(error)));
await page.goto(base,{waitUntil:'networkidle'});
await page.locator('#accountBtn').click();
await page.locator('#loginForm [name=password]').fill(password);
await page.locator('#loginSubmit').click();
await page.locator('#addContentSplit').waitFor({state:'visible'});
await page.locator('[data-mode="all"]').click();
await page.locator(`[data-item-row="${id}"]`).waitFor({state:'visible'});
if((await page.locator('#favoriteCount').textContent()).trim()!=='0')throw new Error('favorite count did not start at zero');

await page.locator(`[data-item-more="${id}"]`).click();
await page.locator('[data-favorite]').click();
await page.waitForFunction(itemId=>{
  const row=document.querySelector(`[data-item-row="${itemId}"]`);
  return !!row?.querySelector('.favorite-mark')&&document.querySelector('#favoriteCount')?.textContent.trim()==='1';
},id);
await page.locator(`[data-item-more="${id}"]`).click();
if((await page.locator('[data-favorite]').textContent()).trim().includes('取消收藏')===false)throw new Error('favorite menu did not refresh');
await page.locator('[data-favorite]').click();
await page.waitForFunction(itemId=>{
  const row=document.querySelector(`[data-item-row="${itemId}"]`);
  return !!row&&!row.querySelector('.favorite-mark')&&document.querySelector('#favoriteCount')?.textContent.trim()==='0';
},id);
await page.locator(`[data-item-more="${id}"]`).click();
if((await page.locator('[data-favorite]').textContent()).trim().includes('加入收藏')===false)throw new Error('unfavorite menu did not refresh');
await page.keyboard.press('Escape');

await page.locator('#addContentBtn').click();
await page.locator('#scratchWorkspaceV259').waitFor({state:'visible'});
const firstCount=await page.locator('[data-scratch-tab]').count();
if(firstCount!==1)throw new Error(`expected one first scratch tab, got ${firstCount}`);
await page.locator('[data-scratch-editor]').fill('first temporary material');
await page.waitForTimeout(900);
await page.locator('[data-scratch-exit]').click();
await page.locator('#scratchWorkspaceV259').waitFor({state:'detached'});
await page.locator('#addContentBtn').click();
await page.locator('#scratchWorkspaceV259').waitFor({state:'visible'});
await page.waitForFunction(before=>document.querySelectorAll('[data-scratch-tab]').length===before+1,firstCount);
const activeValue=await page.locator('[data-scratch-editor]').inputValue();
if(activeValue!=='')throw new Error('New did not focus a blank temporary material');
if(errors.length)throw new Error('browser page errors: '+errors.join(' | '));
console.log('FAVORITE_ADD_REMOVE_AUTO_REFRESH=PASS');
console.log('NEW_IMMEDIATE_SCRATCH_CREATE=PASS');
await browser.close();
JS
BASE_URL="http://127.0.0.1:$PORT/" ITEM_ID="$ITEM_ID" TEST_PASSWORD="$TEST_PASSWORD" node "$ROOT/v2526-browser.mjs"
php tests/integration/favorite_ordering_regression.php "$SITE" | jq -e '.ok==true and .results.favorite_preserves_category_position=="PASS" and .results.favorite_and_pin_state_independent=="PASS"' >/dev/null
php "$SITE/cli/verify.php" | jq -e '.ok==true and .version=="2.5.26" and .schema_version==2401 and .integrity=="ok" and .foreign_key_errors==0' >/dev/null
echo FAVORITE_ORDERING_REGRESSION=PASS
echo FRESH_INSTALL_INTEGRITY=PASS
echo CANDIDATE_SOURCE_COMMIT="$(git rev-parse HEAD)"
echo SCHEMA_MIGRATION=NO
echo PRODUCTION_WRITE=NO
