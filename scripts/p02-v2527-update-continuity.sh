#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo ERROR_LINE=$LINENO' ERR
RUNNER_ROOT="$(pwd)"
cd product

PRODUCT_REF="${PRODUCT_REF:?}"
VER=2.5.27
SRCVER=2.5.25
SCHEMA=2401
UPDATE_NAME="VF_Library_V2.5.27_UPDATE.zip"

test "$(git rev-parse HEAD)" = "$PRODUCT_REF"
test "$(tr -d '\r\n' < VERSION)" = "$VER"
test "$(jq -r .version SOURCE_MANIFEST.json)" = "$VER"
test "$(jq -r .schema SOURCE_MANIFEST.json)" = "$SCHEMA"
test "$(jq -r .runtime_source_file_count SOURCE_MANIFEST.json)" = 76
find public src tests/integration -name '*.php' -print0 | xargs -0 -n1 php -l >/dev/null
node --check public/assets/app.js
node --check public/assets/scratch-tabs.js
node tests/unit/v2521_context_ux_contract.mjs
node tests/unit/v2522_unified_library_workspace_contract.mjs
node tests/unit/v2523_unified_content_workspace_contract.mjs
node tests/unit/v2526_interaction_refresh_contract.mjs
node tests/unit/v2527_update_continuity_contract.mjs
python3 scripts/verify-source-manifest.py
python3 scripts/repository-gates.py
git diff --check
echo EXACT_SOURCE_AUTHORITY_PRIVACY_GATES=PASS

cp scripts/build-release-v2.5.4.py "$RUNNER_TEMP/build-v2527.py"
python3 - "$RUNNER_TEMP/build-v2527.py" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text(encoding='utf-8')
old="ROOT=Path(__file__).resolve().parents[1]; SRCVER='2.5.2'; VER='2.5.4'; SCHEMA=2401; DT=(2026,8,19,2,0,0)"
new="ROOT=Path.cwd(); SRCVER='2.5.25'; VER='2.5.27'; SCHEMA=2401; DT=(2026,8,24,2,0,0)"
assert old in s
s=s.replace(old,new,1)
s=s.replace("default='build/release-v2.5.4'","default='build/release-v2.5.27'").replace("default='release/v2.5.4'","default='release/v2.5.27'")
start="notes=out/f'VF_Library_V{VER}_RELEASE_NOTES.md'; notes.write_text(f'''"
end="''')\n arts=[sz,fz,uz,az,rf,notes]"
i=s.index(start);j=s.index(end,i)
notes="""notes=out/f'VF_Library_V{VER}_RELEASE_NOTES.md'; notes.write_text(f'''# VF Library V{VER}

V2.5.27 restores direct upgrade from authenticated Production V2.5.25 and bootstraps durable multi-source Atomic update support while retaining the V2.5.26 interaction fixes.

- Favorite only changes the “My Favorites” collection state.
- Pin remains the sole explicit control that moves a material to the category top.
- Favorite and pin states stay independent.
- Existing manual category order is preserved when favoriting or unfavoriting.
- Adding or removing a favorite immediately refreshes the item, active collection, navigation metadata, and favorite count.
- Every click on New immediately creates and opens a fresh blank temporary material.
- Atomic format v1 remains available for the V2.5.25 bootstrap; installed V2.5.27 adds explicit multi-source Atomic format v2 for later releases.
- Channel and package source-version sets must match exactly, and journal/rollback identity uses the actual Runtime source.
- Runtime Source Manifest is 76 / 76.
- Direct Atomic source is authenticated Production {SRCVER}; Schema remains {SCHEMA}; no migration.
''')
 arts=[sz,fz,uz,az,rf,notes]"""
s=s[:i]+notes+s[j+len(end):]
s=s.replace("'candidate_browser':'PASS_RUN_32206056733_PLUS_32146866564'","'candidate_browser':'PENDING_CURRENT_EXACT_CANDIDATE_RUN'")
s=s.replace("'candidate_backend_data_privacy_transaction':'PASS_RUN_32206056733_PLUS_INHERITED_V2.5.3'","'candidate_backend_data_privacy_transaction':'PENDING_CURRENT_EXACT_CANDIDATE_RUN'")
s=s.replace("'main_readback':'PRODUCTION_2.5.2_CURRENT_EXPECTED_NOT_PROMOTED'","'main_readback':'FORMAL_2.5.26_CURRENT_NOT_PROMOTED'")
p.write_text(s,encoding='utf-8')
PY
python3 -m py_compile "$RUNNER_TEMP/build-v2527.py"
TREE=$(git show -s --format=%T "$PRODUCT_REF")
python3 "$RUNNER_TEMP/build-v2527.py" --out build/formal-a --source-commit "$PRODUCT_REF" --source-tree "$TREE" --source-ref release/v2.5.27 >"$RUNNER_TEMP/build-a.json"
python3 "$RUNNER_TEMP/build-v2527.py" --out build/formal-b --source-commit "$PRODUCT_REF" --source-tree "$TREE" --source-ref release/v2.5.27 >"$RUNNER_TEMP/build-b.json"

python3 - <<'PY'
from pathlib import Path
import hashlib,json
a=Path('build/formal-a');b=Path('build/formal-b')
ha={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in a.iterdir() if p.is_file()}
hb={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in b.iterdir() if p.is_file()}
assert ha==hb,(ha,hb)
req={'VF_Library_V2.5.27_UPDATE.zip','VF_Library_V2.5.27_FULL.zip','VF_Library_V2.5.27_ATOMIC.zip','VF_Library_V2.5.27_SOURCE.zip','repair-v2.5.27.php','VF_Library_V2.5.27_RELEASE_NOTES.md','VF_Library_V2.5.27_RELEASE_MANIFEST.json','SHA256SUMS.txt'}
assert req<=set(ha),set(ha)
m=json.load(open('build/formal-a/VF_Library_V2.5.27_RELEASE_MANIFEST.json',encoding='utf-8'))
assert m['version']=='2.5.27' and m['compatibility']['supported_from']==['2.5.25']
print('DETERMINISTIC_RELEASE_SET=PASS')
for n,h in sorted(ha.items()): print(n,h)
PY
for z in "$UPDATE_NAME" "VF_Library_V2.5.27_FULL.zip" "VF_Library_V2.5.27_ATOMIC.zip"; do unzip -t "build/formal-a/$z" >/dev/null; done
unzip -p "build/formal-a/$UPDATE_NAME" atomic-manifest.json | jq -e '.source_version=="2.5.25" and .target_version=="2.5.27" and .source_schema==2401 and .target_schema==2401' >/dev/null
echo ARCHIVE_AND_ATOMIC_IDENTITY=PASS

setup_site() {
  local site="$1" root="$2" port="$3" pw="$4"
  php -d display_errors=0 -S "127.0.0.1:$port" -t "$site" >"$root/http.log" 2>&1 &
  SITE_PID=$!
  for _ in $(seq 1 80); do curl -fsS "http://127.0.0.1:$port/setup.php" >/dev/null 2>&1 && break; sleep .25; done
  curl -fsS -c "$root/cookies" "http://127.0.0.1:$port/setup.php" >"$root/setup.html"
  local token
  token=$(python3 - "$root/setup.html" <<'PY'
import html,re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="setup_csrf" value="([^"]+)"',s);assert m;print(html.unescape(m.group(1)))
PY
)
  test "$(curl -sS -o /dev/null -w '%{http_code}' -b "$root/cookies" -c "$root/cookies" -H "Origin: http://127.0.0.1:$port" --data-urlencode "setup_csrf=$token" --data-urlencode "password=$pw" --data-urlencode "password_confirm=$pw" "http://127.0.0.1:$port/setup.php")" = 303
}

FRESH="$RUNNER_TEMP/fresh2527"; mkdir -p "$FRESH/site"
unzip -q build/formal-a/VF_Library_V2.5.27_FULL.zip -d "$FRESH/site"
test "$(cat "$FRESH/site/VERSION.txt")" = 2.5.27
setup_site "$FRESH/site" "$FRESH" 18324 "P02-V2527-FRESH-$GITHUB_RUN_ID!"

cat >"$RUNNER_ROOT/v2527-browser.mjs" <<'JS'
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
const listSwitch=page.locator('[data-content-view="list"]:visible').first();
await listSwitch.waitFor({state:'visible'});await listSwitch.click();
await page.locator(`[data-item-row="${id}"]`).waitFor({state:'visible'});
const start=Number((await page.locator('#favoriteCount').textContent()).trim());
await page.locator(`[data-item-more="${id}"]`).click();
await page.locator('[data-favorite]').click();
await page.waitForFunction(({itemId,count})=>{
  const row=document.querySelector(`[data-item-row="${itemId}"]`);
  return !!row?.querySelector('.favorite-mark')&&Number(document.querySelector('#favoriteCount')?.textContent.trim())===count+1;
},{itemId:id,count:start});
await page.locator(`[data-item-more="${id}"]`).click();
if(!(await page.locator('[data-favorite]').textContent()).includes('取消收藏'))throw new Error('favorite menu did not refresh');
await page.locator('[data-favorite]').click();
await page.waitForFunction(({itemId,count})=>{
  const row=document.querySelector(`[data-item-row="${itemId}"]`);
  return !!row&&!row.querySelector('.favorite-mark')&&Number(document.querySelector('#favoriteCount')?.textContent.trim())===count;
},{itemId:id,count:start});
await page.locator(`[data-item-more="${id}"]`).click();
if(!(await page.locator('[data-favorite]').textContent()).includes('加入收藏'))throw new Error('unfavorite menu did not refresh');
await page.keyboard.press('Escape');
await page.locator('#addContentBtn').click();
await page.locator('#scratchWorkspaceV259').waitFor({state:'visible'});
const firstCount=await page.locator('[data-scratch-tab]').count();
if(firstCount<1)throw new Error('New did not create first temporary material');
await page.locator('[data-scratch-editor]').fill('first temporary material');
await page.waitForTimeout(900);
await page.locator('[data-scratch-exit]').click();
await page.locator('#scratchWorkspaceV259').waitFor({state:'detached'});
await page.locator('#addContentBtn').click();
await page.locator('#scratchWorkspaceV259').waitFor({state:'visible'});
await page.waitForFunction(before=>document.querySelectorAll('[data-scratch-tab]').length===before+1,firstCount);
if(await page.locator('[data-scratch-editor]').inputValue()!=='')throw new Error('New did not focus a blank temporary material');
if(errors.length)throw new Error('browser page errors: '+errors.join(' | '));
console.log('FAVORITE_ADD_REMOVE_AUTO_REFRESH=PASS');
console.log('NEW_IMMEDIATE_SCRATCH_CREATE=PASS');
await browser.close();
JS

seed_interaction() {
  local site="$1" out="$2"
  cat >"$RUNNER_TEMP/v2527-interaction-seed.php" <<'PHP'
<?php
$site=$argv[1];$out=$argv[2];require $site.'/app/bootstrap.php';
$db=vftb_db();$org=new VfLibraryOrganizationService($db);$items=new VfLibraryItemService($db);
$cid=$org->save(null,['name'=>'V2527 Interaction']);
$id=$items->saveItem(null,['category_id'=>$cid,'title'=>'Interaction Fixture','content'=>'fixture','content_mode'=>'article','content_format'=>'markdown','primary_action'=>'read','status'=>'active']);
file_put_contents($out,json_encode(['item_id'=>$id]));
PHP
  php "$RUNNER_TEMP/v2527-interaction-seed.php" "$site" "$out"
}

seed_interaction "$FRESH/site" "$FRESH/interaction.json"
ITEM_ID=$(jq -r .item_id "$FRESH/interaction.json")
BASE_URL="http://127.0.0.1:18324/" ITEM_ID="$ITEM_ID" TEST_PASSWORD="P02-V2527-FRESH-$GITHUB_RUN_ID!" node "$RUNNER_ROOT/v2527-browser.mjs"
php tests/integration/favorite_ordering_regression.php "$FRESH/site" | jq -e '.ok==true and .results.favorite_preserves_category_position=="PASS" and .results.favorite_and_pin_state_independent=="PASS" and .results.pin_controls_category_top=="PASS"' >/dev/null
php "$FRESH/site/cli/verify.php" | jq -e '.ok==true and .version=="2.5.27" and .schema_version==2401 and .integrity=="ok" and .foreign_key_errors==0' >/dev/null
kill "$SITE_PID"; wait "$SITE_PID" 2>/dev/null || true
echo FULL_FRESH_INSTALL_FAVORITE_ORDERING=PASS

UP="$RUNNER_TEMP/up2525"; mkdir -p "$UP"
git worktree add --detach "$UP/source" v2.5.25 >/dev/null
mkdir -p "$UP/site"; bash "$UP/source/scripts/build-deploy-tree.sh" "$UP/site" >/dev/null
test "$(cat "$UP/site/VERSION.txt")" = 2.5.25
setup_site "$UP/site" "$UP" 18325 "P02-V2527-UP-$GITHUB_RUN_ID!"

cat >"$UP/seed.php" <<'PHP'
<?php
$site=$argv[1];$out=$argv[2];require $site.'/app/bootstrap.php';
$db=vftb_db();$org=new VfLibraryOrganizationService($db);$items=new VfLibraryItemService($db);
$cid=$org->save(null,['name'=>'V2527 Upgrade Preserve']);
$ids=[];foreach(['First','Second','Third'] as $t)$ids[]=$items->saveItem(null,['category_id'=>$cid,'title'=>$t,'content'=>$t,'content_mode'=>'article','content_format'=>'markdown','primary_action'=>'read','status'=>'active']);
$items->reorderItems($cid,[$ids[1],$ids[0],$ids[2]]);$items->toggleFavorite($ids[2],true);
file_put_contents($out,json_encode(['category'=>$cid,'ids'=>$ids]));
PHP
php "$UP/seed.php" "$UP/site" "$UP/ids.json"

PKG="$(pwd)/build/formal-a/$UPDATE_NAME"; BYTES=$(stat -c%s "$PKG"); SHA=$(sha256sum "$PKG"|awk '{print $1}')
cat >"$UP/upgrade.php" <<'PHP'
<?php
$site=$argv[1];$pkg=$argv[2];$bytes=(int)$argv[3];$sha=$argv[4];$out=$argv[5];
require $site.'/app/bootstrap.php';require_once $site.'/app/CoreUpdates/UpdateAdapter.php';require_once $site.'/app/CoreUpdates/UpdateCore.php';require_once $site.'/app/VfLibraryCoreUpdateAdapter.php';
$m=['schema_version'=>'1.0','project_id'=>'P02','component_id'=>'APP','enabled'=>true,'current_version'=>'2.5.25','target_version'=>'2.5.27','update_type'=>'ATOMIC','from_versions'=>['2.5.25'],'schema_from'=>'2401','schema_to'=>'2401','repository'=>'llhzx2018/vf-library','release_tag'=>'v2.5.27','asset_name'=>'VF_Library_V2.5.27_UPDATE.zip','asset_bytes'=>$bytes,'asset_sha256'=>$sha,'backup_required'=>true,'rollback_supported'=>true,'released_at'=>'2026-08-23T18:00:00Z'];
$c=new CoreUpdates\UpdateCore('P02','APP');if(($c->check('2.5.25','2401',$m)['status']??'')!=='AVAILABLE')exit(2);if(($c->verifyPackage($pkg,$m)['status']??'')!=='VERIFIED')exit(3);$res=$c->upgrade('2.5.25','2401',new VfLibraryCoreUpdateAdapter(),$pkg,$m);file_put_contents($out,json_encode($res));if(!in_array($res['status']??'',['COMMITTED','COMMITTED_WITH_CLEANUP_WARNING'],true)||empty($res['backup_locator']))exit(4);
PHP
php "$UP/upgrade.php" "$UP/site" "$PKG" "$BYTES" "$SHA" "$UP/result.json"
test "$(cat "$UP/site/VERSION.txt")" = 2.5.27
jq -e '.backup_locator|length>0' "$UP/result.json" >/dev/null

cat >"$UP/post.php" <<'PHP'
<?php
$site=$argv[1];$ids=json_decode(file_get_contents($argv[2]),true);require $site.'/app/bootstrap.php';
$repo=new VfTextBoxRepository(vftb_db());$list=$repo->listItems(['mode'=>'category','status'=>'active','category_id'=>(int)$ids['category'],'sort'=>'manual','page'=>1,'page_size'=>20,'titles_only'=>true]);
$order=array_map(fn($x)=>(int)$x['id'],$list['items']);$expected=[(int)$ids['ids'][1],(int)$ids['ids'][0],(int)$ids['ids'][2]];
$item=$repo->getItem((int)$ids['ids'][2]);if($order!==$expected||(int)$item['is_favorite']!==1||(int)$item['is_pinned']!==0)exit(7);
echo json_encode(['order'=>'PASS','favorite'=>'PRESERVED','pin'=>'INDEPENDENT']);
PHP
php "$UP/post.php" "$UP/site" "$UP/ids.json" | jq -e '.order=="PASS" and .favorite=="PRESERVED" and .pin=="INDEPENDENT"' >/dev/null
seed_interaction "$UP/site" "$UP/interaction.json"
UP_ITEM_ID=$(jq -r .item_id "$UP/interaction.json")
BASE_URL="http://127.0.0.1:18325/" ITEM_ID="$UP_ITEM_ID" TEST_PASSWORD="P02-V2527-UP-$GITHUB_RUN_ID!" node "$RUNNER_ROOT/v2527-browser.mjs"
php tests/integration/favorite_ordering_regression.php "$UP/site" | jq -e '.ok==true and .results.favorite_preserves_category_position=="PASS"' >/dev/null
php "$UP/site/cli/verify.php" | jq -e '.ok==true and .version=="2.5.27" and .schema_version==2401 and .integrity=="ok" and .foreign_key_errors==0' >/dev/null

MS="$RUNNER_TEMP/multisource"; mkdir -p "$MS/deploy"
bash scripts/build-deploy-tree.sh "$MS/deploy" >/dev/null
printf '2.5.28\n' > "$MS/deploy/VERSION.txt"
python3 scripts/build-multisource-update.py --deploy-root "$MS/deploy" --output "$MS/update-a.zip" --target-version 2.5.28 --source-version 2.5.26 --source-version 2.5.27 --source-schema 2401 --target-schema 2401 --timestamp 2026-08-24T03:00:00Z >"$MS/build-a.json"
python3 scripts/build-multisource-update.py --deploy-root "$MS/deploy" --output "$MS/update-b.zip" --target-version 2.5.28 --source-version 2.5.26 --source-version 2.5.27 --source-schema 2401 --target-schema 2401 --timestamp 2026-08-24T03:00:00Z >"$MS/build-b.json"
test "$(sha256sum "$MS/update-a.zip"|awk '{print $1}')" = "$(sha256sum "$MS/update-b.zip"|awk '{print $1}')"
unzip -p "$MS/update-a.zip" atomic-manifest.json | jq -e '.format_version==2 and .source_versions==["2.5.26","2.5.27"] and .target_version=="2.5.28"' >/dev/null
MS_BYTES=$(stat -c%s "$MS/update-a.zip"); MS_SHA=$(sha256sum "$MS/update-a.zip"|awk '{print $1}')

cat >"$MS/verify.php" <<'PHP'
<?php
$site=$argv[1];$pkg=$argv[2];$bytes=(int)$argv[3];$sha=$argv[4];$ids=json_decode(file_get_contents($argv[5]),true);
require $site.'/app/bootstrap.php';require_once $site.'/app/CoreUpdates/UpdateAdapter.php';require_once $site.'/app/CoreUpdates/UpdateCore.php';require_once $site.'/app/VfLibraryCoreUpdateAdapter.php';
$m=['schema_version'=>'1.0','project_id'=>'P02','component_id'=>'APP','enabled'=>true,'current_version'=>'2.5.27','target_version'=>'2.5.28','update_type'=>'ATOMIC','from_versions'=>['2.5.26','2.5.27'],'schema_from'=>'2401','schema_to'=>'2401','repository'=>'llhzx2018/vf-library','release_tag'=>'v2.5.28-test','asset_name'=>'VF_Library_V2.5.28_UPDATE.zip','asset_bytes'=>$bytes,'asset_sha256'=>$sha,'backup_required'=>true,'rollback_supported'=>true,'released_at'=>'2026-08-24T03:00:00Z'];
$core=new CoreUpdates\UpdateCore('P02','APP');
if(($core->check('2.5.26','2401',$m)['status']??'')!=='AVAILABLE')exit(20);
if(($core->check('2.5.27','2401',$m)['status']??'')!=='AVAILABLE')exit(21);
if(($core->check('2.5.25','2401',$m)['status']??'')!=='BLOCKED_SOURCE_VERSION')exit(22);
if(($core->check('2.5.27','9999',$m)['status']??'')!=='BLOCKED_SCHEMA')exit(23);
$failed=$core->upgrade('2.5.27','2401',new VfLibraryCoreUpdateAdapter(null,['force_self_check_failure'=>true]),$pkg,$m);
if(($failed['status']??'')!=='FAILED'||trim((string)file_get_contents($site.'/VERSION.txt'))!=='2.5.27')exit(24);
$committed=$core->upgrade('2.5.27','2401',new VfLibraryCoreUpdateAdapter(),$pkg,$m);
if(!in_array($committed['status']??'',['COMMITTED','COMMITTED_WITH_CLEANUP_WARNING'],true)||empty($committed['backup_locator']))exit(25);
if(trim((string)file_get_contents($site.'/VERSION.txt'))!=='2.5.28')exit(26);
vftb_close_db();$pdo=vftb_db();$item=(new VfTextBoxRepository($pdo))->getItem((int)$ids['ids'][2]);
$integrity=$pdo->query('PRAGMA integrity_check')->fetchAll(PDO::FETCH_COLUMN);$fk=$pdo->query('PRAGMA foreign_key_check')->fetchAll();
if(!$item||(int)$item['is_favorite']!==1||(int)$item['is_pinned']!==0||count($integrity)!==1||strtolower((string)$integrity[0])!=='ok'||count($fk)!==0)exit(27);
echo json_encode(['v1_bootstrap'=>'PASS','v2_sources'=>['2.5.26','2.5.27'],'forced_failure_rollback'=>'PASS','v2_commit'=>'PASS','data'=>'PRESERVED']);
PHP
php "$MS/verify.php" "$UP/site" "$MS/update-a.zip" "$MS_BYTES" "$MS_SHA" "$UP/ids.json" | jq -e '.v1_bootstrap=="PASS" and .forced_failure_rollback=="PASS" and .v2_commit=="PASS" and .data=="PRESERVED"' >/dev/null
kill "$SITE_PID"; wait "$SITE_PID" 2>/dev/null || true
echo ATOMIC_V2_DETERMINISTIC_BUILD=PASS
echo ATOMIC_V2_EXPLICIT_SOURCE_SET=PASS
echo ATOMIC_V2_ACTUAL_RUNTIME_ROLLBACK_IDENTITY=PASS
echo ATOMIC_V2_MULTI_SOURCE_UPGRADE_MATRIX=PASS
echo EXISTING_DATA_2.5.25_TO_2.5.27=PASS
echo AUTOMATIC_BACKUP_AND_DATA_PRESERVATION=PASS
echo FAVORITE_ORDERING_AFTER_ATOMIC_UPGRADE=PASS
echo V2527_INTERACTION_REFRESH_AFTER_ATOMIC_UPGRADE=PASS
echo V2525_TO_V2527_BOOTSTRAP=PASS

echo CANDIDATE_SOURCE_COMMIT="$(git rev-parse HEAD)"
echo CANDIDATE_SOURCE_TREE="$TREE"
echo REL_STATE=REL.READY_PREPARE_ONLY_V2525_TO_V2527
echo MAIN_PROMOTION=NO
echo FORMAL_TAG=NO
echo CHANNEL_PUBLICATION=NO
echo PRODUCTION_WRITE=NO
