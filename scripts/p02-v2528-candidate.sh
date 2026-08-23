#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo ERROR_LINE=$LINENO' ERR
RUNNER_ROOT="$(pwd)"
cd product

PRODUCT_REF="${PRODUCT_REF:?}"
VER=2.5.28
SRCVER=2.5.27
SCHEMA=2401
UPDATE_NAME="VF_Library_V2.5.28_UPDATE.zip"

# Exact source / identity gates.
test "$(git rev-parse HEAD)" = "$PRODUCT_REF"
test "$(tr -d '\r\n' < VERSION)" = "$VER"
test "$(jq -r .version SOURCE_MANIFEST.json)" = "$VER"
test "$(jq -r .schema SOURCE_MANIFEST.json)" = "$SCHEMA"
test "$(jq -r .runtime_source_file_count SOURCE_MANIFEST.json)" = 76
find public src tests/integration -name '*.php' -print0 | xargs -0 -n1 php -l >/dev/null
node --check public/assets/app.js
node --check public/assets/scratch-tabs.js
node --check public/assets/v255-hotfix.js
node tests/unit/v2521_context_ux_contract.mjs
node tests/unit/v2522_unified_library_workspace_contract.mjs
node tests/unit/v2523_unified_content_workspace_contract.mjs
node tests/unit/v2526_interaction_refresh_contract.mjs
node tests/unit/v2527_update_continuity_contract.mjs
python3 scripts/verify-source-manifest.py
python3 scripts/repository-gates.py
git diff --check
echo EXACT_SOURCE_AUTHORITY_PRIVACY_GATES=PASS

# Reuse the sealed release builder, rebased to authenticated Production 2.5.27 -> 2.5.28.
cp scripts/build-release-v2.5.4.py "$RUNNER_TEMP/build-v2528.py"
python3 - "$RUNNER_TEMP/build-v2528.py" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text(encoding='utf-8')
old="ROOT=Path(__file__).resolve().parents[1]; SRCVER='2.5.2'; VER='2.5.4'; SCHEMA=2401; DT=(2026,8,19,2,0,0)"
new="ROOT=Path.cwd(); SRCVER='2.5.27'; VER='2.5.28'; SCHEMA=2401; DT=(2026,8,24,4,0,0)"
assert old in s
s=s.replace(old,new,1)
s=s.replace("default='build/release-v2.5.4'","default='build/release-v2.5.28'").replace("default='release/v2.5.4'","default='release/v2.5.28'")
start="notes=out/f'VF_Library_V{VER}_RELEASE_NOTES.md'; notes.write_text(f'''"
end="''')\n arts=[sz,fz,uz,az,rf,notes]"
i=s.index(start);j=s.index(end,i)
notes="""notes=out/f'VF_Library_V{VER}_RELEASE_NOTES.md'; notes.write_text(f'''# VF Library V{VER}\n\nV2.5.28 fixes temporary-workspace navigation trapping while preserving the V2.5.27 update baseline.\n\n- Temporary workspace no longer visually traps the user above normal Library pages.\n- Clicking All, Favorites, Recent, Drafts, Trash, Settings or other registered navigation first saves the temporary material, closes the workspace, then continues the requested navigation.\n- A failed temporary save blocks navigation instead of discarding content.\n- Runtime Source Manifest remains 76 / 76.\n- Direct Atomic source is authenticated Production {SRCVER}; Schema remains {SCHEMA}; no migration.\n''')
 arts=[sz,fz,uz,az,rf,notes]"""
s=s[:i]+notes+s[j+len(end):]
s=s.replace("'candidate_browser':'PASS_RUN_32206056733_PLUS_32146866564'","'candidate_browser':'PENDING_V2.5.28_EXACT_CANDIDATE_RUN'")
s=s.replace("'candidate_backend_data_privacy_transaction':'PASS_RUN_32206056733_PLUS_INHERITED_V2.5.3'","'candidate_backend_data_privacy_transaction':'PENDING_V2.5.28_EXACT_CANDIDATE_RUN'")
s=s.replace("'main_readback':'PRODUCTION_2.5.2_CURRENT_EXPECTED_NOT_PROMOTED'","'main_readback':'PRODUCTION_2.5.27_CURRENT_NOT_PROMOTED'")
p.write_text(s,encoding='utf-8')
PY
python3 -m py_compile "$RUNNER_TEMP/build-v2528.py"
TREE=$(git show -s --format=%T "$PRODUCT_REF")
python3 "$RUNNER_TEMP/build-v2528.py" --out build/candidate-a --source-commit "$PRODUCT_REF" --source-tree "$TREE" --source-ref release/v2.5.28 >"$RUNNER_TEMP/build-a.json"
python3 "$RUNNER_TEMP/build-v2528.py" --out build/candidate-b --source-commit "$PRODUCT_REF" --source-tree "$TREE" --source-ref release/v2.5.28 >"$RUNNER_TEMP/build-b.json"
python3 - <<'PY'
from pathlib import Path
import hashlib,json
a=Path('build/candidate-a');b=Path('build/candidate-b')
ha={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in a.iterdir() if p.is_file()}
hb={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in b.iterdir() if p.is_file()}
assert ha==hb,(ha,hb)
req={'VF_Library_V2.5.28_UPDATE.zip','VF_Library_V2.5.28_FULL.zip','VF_Library_V2.5.28_ATOMIC.zip','VF_Library_V2.5.28_SOURCE.zip','repair-v2.5.28.php','VF_Library_V2.5.28_RELEASE_NOTES.md','VF_Library_V2.5.28_RELEASE_MANIFEST.json','SHA256SUMS.txt'}
assert req<=set(ha),set(ha)
m=json.load(open('build/candidate-a/VF_Library_V2.5.28_RELEASE_MANIFEST.json',encoding='utf-8'))
assert m['version']=='2.5.28' and m['compatibility']['supported_from']==['2.5.27']
print('DETERMINISTIC_RELEASE_SET=PASS')
for n,h in sorted(ha.items()): print(n,h)
PY
for z in "$UPDATE_NAME" "VF_Library_V2.5.28_FULL.zip" "VF_Library_V2.5.28_ATOMIC.zip"; do unzip -t "build/candidate-a/$z" >/dev/null; done
unzip -p "build/candidate-a/$UPDATE_NAME" atomic-manifest.json | jq -e '.source_version=="2.5.27" and .target_version=="2.5.28" and .source_schema==2401 and .target_schema==2401' >/dev/null
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

cat >"$RUNNER_ROOT/v2528-scratch-nav.mjs" <<'JS'
import {chromium} from 'playwright';
const base=process.env.BASE_URL,password=process.env.TEST_PASSWORD;
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1365,height:900}});
const errors=[];page.on('pageerror',e=>errors.push(String(e)));
await page.goto(base,{waitUntil:'networkidle'});
await page.locator('#accountBtn').click();
await page.locator('#loginForm [name=password]').fill(password);
await page.locator('#loginSubmit').click();
await page.locator('#addContentSplit').waitFor({state:'visible'});
const cases=[
  ['[data-mode="all"]',s=>s.mode==='all'&&s.status==='active','all'],
  ['[data-mode="favorite"]',s=>s.mode==='favorite'&&s.status==='active','favorite'],
  ['[data-mode="recent"]',s=>s.mode==='recent'&&s.status==='active','recent'],
  ['#draftBtn',s=>s.status==='draft','draft'],
  ['#trashBtn',s=>s.status==='trash','trash'],
  ['#settingsBtn',s=>s.mode==='settings','settings']
];
for(const [selector,predicate,label] of cases){
  await page.locator('#addContentBtn').click();
  await page.locator('#scratchWorkspaceV259').waitFor({state:'visible'});
  const marker=`V2528-${label}-${Date.now()}`;
  await page.locator('[data-scratch-editor]').fill(marker);
  await page.waitForTimeout(900);
  await page.locator(selector).click();
  await page.locator('#scratchWorkspaceV259').waitFor({state:'detached',timeout:10000});
  await page.waitForFunction(label=>{
    const s=globalThis.state||{};
    if(label==='all')return s.mode==='all'&&s.status==='active';
    if(label==='favorite')return s.mode==='favorite'&&s.status==='active';
    if(label==='recent')return s.mode==='recent'&&s.status==='active';
    if(label==='draft')return s.status==='draft';
    if(label==='trash')return s.status==='trash';
    if(label==='settings')return s.mode==='settings';
    return false;
  },label,{timeout:10000});
  await page.locator('#addContentBtn').click();
  await page.locator('#scratchWorkspaceV259').waitFor({state:'visible'});
  const persisted=await page.locator('[data-scratch-editor]').inputValue();
  if(persisted!==marker)throw new Error(`scratch auto-save lost before ${label}: ${persisted}`);
  await page.locator('[data-scratch-exit]').click();
  await page.locator('#scratchWorkspaceV259').waitFor({state:'detached'});
}
if(errors.length)throw new Error('browser page errors: '+errors.join(' | '));
console.log('SCRATCH_NAVIGATION_EXIT_MATRIX=PASS');
console.log('SCRATCH_AUTOSAVE_BEFORE_NAVIGATION=PASS');
await browser.close();
JS

# Fresh install + exact regression.
FRESH="$RUNNER_TEMP/fresh2528"; mkdir -p "$FRESH/site"
unzip -q build/candidate-a/VF_Library_V2.5.28_FULL.zip -d "$FRESH/site"
test "$(cat "$FRESH/site/VERSION.txt")" = 2.5.28
setup_site "$FRESH/site" "$FRESH" 18328 "P02-V2528-FRESH-$GITHUB_RUN_ID!"
BASE_URL="http://127.0.0.1:18328/" TEST_PASSWORD="P02-V2528-FRESH-$GITHUB_RUN_ID!" node "$RUNNER_ROOT/v2528-scratch-nav.mjs"
php "$FRESH/site/cli/verify.php" | jq -e '.ok==true and .version=="2.5.28" and .schema_version==2401 and .integrity=="ok" and .foreign_key_errors==0' >/dev/null
kill "$SITE_PID"; wait "$SITE_PID" 2>/dev/null || true
echo FRESH_INSTALL_AND_SCRATCH_NAV=PASS

# Authenticated Production baseline 2.5.27 -> 2.5.28 Atomic update.
UP="$RUNNER_TEMP/up2527"; mkdir -p "$UP"
git worktree add --detach "$UP/source" v2.5.27 >/dev/null
mkdir -p "$UP/site"; bash "$UP/source/scripts/build-deploy-tree.sh" "$UP/site" >/dev/null
test "$(cat "$UP/site/VERSION.txt")" = 2.5.27
setup_site "$UP/site" "$UP" 18327 "P02-V2528-UP-$GITHUB_RUN_ID!"

cat >"$UP/seed.php" <<'PHP'
<?php
$site=$argv[1];$out=$argv[2];require $site.'/app/bootstrap.php';
$db=vftb_db();$org=new VfLibraryOrganizationService($db);$items=new VfLibraryItemService($db);
$cid=$org->save(null,['name'=>'V2528 Preserve']);
$id=$items->saveItem(null,['category_id'=>$cid,'title'=>'Preserve Fixture','content'=>'KEEP_ME_V2528','content_mode'=>'article','content_format'=>'markdown','primary_action'=>'read','status'=>'active']);
file_put_contents($out,json_encode(['id'=>$id]));
PHP
php "$UP/seed.php" "$UP/site" "$UP/seed.json"
PKG="$(pwd)/build/candidate-a/$UPDATE_NAME"; BYTES=$(stat -c%s "$PKG"); SHA=$(sha256sum "$PKG"|awk '{print $1}')
cat >"$UP/upgrade.php" <<'PHP'
<?php
$site=$argv[1];$pkg=$argv[2];$bytes=(int)$argv[3];$sha=$argv[4];$out=$argv[5];
require $site.'/app/bootstrap.php';require_once $site.'/app/CoreUpdates/UpdateAdapter.php';require_once $site.'/app/CoreUpdates/UpdateCore.php';require_once $site.'/app/VfLibraryCoreUpdateAdapter.php';
$m=['schema_version'=>'1.0','project_id'=>'P02','component_id'=>'APP','enabled'=>true,'current_version'=>'2.5.27','target_version'=>'2.5.28','update_type'=>'ATOMIC','from_versions'=>['2.5.27'],'schema_from'=>'2401','schema_to'=>'2401','repository'=>'llhzx2018/vf-library','release_tag'=>'v2.5.28','asset_name'=>'VF_Library_V2.5.28_UPDATE.zip','asset_bytes'=>$bytes,'asset_sha256'=>$sha,'backup_required'=>true,'rollback_supported'=>true,'released_at'=>'2026-08-24T04:00:00Z'];
$c=new CoreUpdates\UpdateCore('P02','APP');if(($c->check('2.5.27','2401',$m)['status']??'')!=='AVAILABLE')exit(2);if(($c->verifyPackage($pkg,$m)['status']??'')!=='VERIFIED')exit(3);$res=$c->upgrade('2.5.27','2401',new VfLibraryCoreUpdateAdapter(),$pkg,$m);file_put_contents($out,json_encode($res));if(!in_array($res['status']??'',['COMMITTED','COMMITTED_WITH_CLEANUP_WARNING'],true)||empty($res['backup_locator']))exit(4);
PHP
php "$UP/upgrade.php" "$UP/site" "$PKG" "$BYTES" "$SHA" "$UP/result.json"
test "$(cat "$UP/site/VERSION.txt")" = 2.5.28
jq -e '.backup_locator|length>0' "$UP/result.json" >/dev/null
cat >"$UP/post.php" <<'PHP'
<?php
$site=$argv[1];$seed=json_decode(file_get_contents($argv[2]),true);require $site.'/app/bootstrap.php';
$item=(new VfTextBoxRepository(vftb_db()))->getItem((int)$seed['id']);if(!$item||$item['content']!=='KEEP_ME_V2528')exit(7);echo json_encode(['data'=>'PRESERVED']);
PHP
php "$UP/post.php" "$UP/site" "$UP/seed.json" | jq -e '.data=="PRESERVED"' >/dev/null
BASE_URL="http://127.0.0.1:18327/" TEST_PASSWORD="P02-V2528-UP-$GITHUB_RUN_ID!" node "$RUNNER_ROOT/v2528-scratch-nav.mjs"
php "$UP/site/cli/verify.php" | jq -e '.ok==true and .version=="2.5.28" and .schema_version==2401 and .integrity=="ok" and .foreign_key_errors==0' >/dev/null
kill "$SITE_PID"; wait "$SITE_PID" 2>/dev/null || true

echo V2527_TO_V2528_ATOMIC_UPGRADE=PASS
echo AUTOMATIC_BACKUP=PASS
echo EXISTING_DATA_PRESERVED=PASS
echo SCRATCH_NAV_REGRESSION_AFTER_UPGRADE=PASS
echo CANDIDATE_SOURCE_COMMIT="$(git rev-parse HEAD)"
echo CANDIDATE_SOURCE_TREE="$TREE"
echo REL_STATE=REL.READY_PREPARE_ONLY_V2527_TO_V2528
echo MAIN_PROMOTION=NO
echo FORMAL_TAG=NO
echo CHANNEL_PUBLICATION=NO
echo PRODUCTION_WRITE=NO
