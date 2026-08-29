#!/usr/bin/env bash
set -Eeuo pipefail

CANDIDATE='8b4f3483579bf2d286c551c1f33e876e4e7aec16'
CANDIDATE_TREE='8e693bda3a16ad1e0952314858227ffbffd59897'
RUNTIME_TREE='f348cb314623906acc851cb79d75b1c8f6637aff'
PRODUCT='8944677974e3a512d846f0740897a7a98e4b7b53'
PRODUCT_TREE='09412d1b7df21deb01a45e3069ecd48e564fb458'
V9_PRODUCT='79740ff6cd6b1be7b6e5c0c2a1cdf6bb91edee8a'
SOURCE='0dfc6c7b1b76ca3cec750daed97f5c4ba51b47f4'
SOURCE_TREE='f568820198afde57fe3c1522820f45bbbf6e0c96'
SOURCE_RUNTIME_TREE='772d51ebbc9f8cd6791c0601d29f6b3b2a95a086'
SCHEMA='2026082901'
ART=/tmp/p01-v2320-candidate-evidence
OUT=/tmp/p01-v2320-candidate-artifacts
rm -rf "$ART" "$OUT" /tmp/p01-v2320-*runtime /tmp/p01-v2320-browser
mkdir -p "$ART"

# 1. Immutable source / version / runtime-delta authority.
test "$(git -C candidate rev-parse HEAD)" = "$CANDIDATE"
test "$(git -C candidate rev-parse HEAD^{tree})" = "$CANDIDATE_TREE"
test "$(git -C candidate rev-parse HEAD:src)" = "$RUNTIME_TREE"
test "$(git -C candidate rev-parse "$PRODUCT^{tree}")" = "$PRODUCT_TREE"
test "$(git -C production rev-parse HEAD)" = "$SOURCE"
test "$(git -C production rev-parse HEAD^{tree})" = "$SOURCE_TREE"
test "$(git -C production rev-parse HEAD:src)" = "$SOURCE_RUNTIME_TREE"
test "$(cat candidate/VERSION)" = '2.32.0'
test "$(cat candidate/src/VERSION.txt)" = '2.32.0'
test "$(cat production/VERSION)" = '2.31.0'
test "$(cat production/src/VERSION.txt)" = '2.31.0'
grep -Fx "define('VF_VERSION', '2.32.0');" candidate/src/app/bootstrap.php >/dev/null
grep -Fx "define('VF_VERSION', '2.31.0');" production/src/app/bootstrap.php >/dev/null
if git -C candidate diff --name-only "$SOURCE"..."$CANDIDATE" -- src/migrations/ | grep .; then echo UNEXPECTED_MIGRATION; exit 1; fi

# Candidate only changes version identity over the final machine-proven Home product bytes.
for f in \
  src/app/FunctionalHome.php \
  src/app/FunctionalWorkspaceShell.php \
  src/app/SurfaceRepository.php \
  src/assets/workspace-home.css \
  src/home.php \
  src/index.php; do
  cmp <(git -C candidate show "$V9_PRODUCT:$f") "candidate/$f"
done
cat >"$ART/v9-binding.txt" <<'EOF'
V9_RUN=33262598059 PASS
V9_PRODUCT_SOURCE=79740ff6cd6b1be7b6e5c0c2a1cdf6bb91edee8a
V9_PRODUCT_TREE=09412d1b7df21deb01a45e3069ecd48e564fb458
V9_ARTIFACT=9717686987
V9_SHA256=3d309065c03ed4845bb347aa3aa2e69f0febb92d87645db1580e3bdc4053266c
CANDIDATE_HOME_BYTES_MATCH_V9=PASS
EOF

while IFS= read -r -d '' f; do php -l "$f" >/dev/null; done < <(find candidate/src -type f -name '*.php' -print0)
while IFS= read -r -d '' f; do node --check "$f" >/dev/null; done < <(find candidate/src -type f -name '*.js' -print0)
printf '%s\n' \
  P01_V2320_EXACT_CANDIDATE_SOURCE=PASS \
  P01_V2320_VERSION_TRIPLE_BINDING=PASS \
  P01_V2320_SCHEMA_UNCHANGED=PASS \
  P01_V2320_NO_MIGRATION=PASS \
  P01_V2320_HOME_BYTES_BOUND_TO_V9=PASS | tee "$ART/source-fence.txt"

# 2. Build deterministic, unpublished candidate FULL/UPDATE artifacts.
python3 runner/scripts/p01-v2320-build-candidate-artifacts.py | tee "$ART/build-1.json"
REPAIR="$OUT/repair-v2.32.0.php"
FULL="$OUT/VF-Start-V2.32.0-FULL.zip"
UPDATE="$OUT/VF_Start_V2.32.0_UPDATE.zip"
php -l "$REPAIR" >/dev/null
php "$REPAIR" --self-test | tee "$ART/repair-self-test.json" | jq -e '.ok==true and .global_barrier==true and .interruption_recovery==true' >/dev/null
jq -e '.status=="CANDIDATE_ARTIFACT_BUILD_PASS" and .candidate_source=="8b4f3483579bf2d286c551c1f33e876e4e7aec16" and .source_commit=="0dfc6c7b1b76ca3cec750daed97f5c4ba51b47f4" and .schema=="2026082901" and .schema_change==false and .runtime_delta_count==8 and (.runtime_added|length)==3 and (.runtime_removed|length)==0 and .owner_production_write==false' "$OUT/P01-V2.32.0-CANDIDATE-GATE.json" >/dev/null
sha256sum "$FULL" "$UPDATE" "$REPAIR" > "$ART/artifacts-sha-1.txt"
python3 runner/scripts/p01-v2320-build-candidate-artifacts.py | tee "$ART/build-2.json"
sha256sum "$FULL" "$UPDATE" "$REPAIR" > "$ART/artifacts-sha-2.txt"
diff -u "$ART/artifacts-sha-1.txt" "$ART/artifacts-sha-2.txt"
unzip -Z1 "$UPDATE" | grep -Fx repair-v2.32.0.php >/dev/null
echo P01_V2320_DETERMINISTIC_CANDIDATE_ARTIFACTS=PASS | tee "$ART/artifact-verdict.txt"

PIDS=()
cleanup(){ for p in "${PIDS[@]:-}"; do kill "$p" >/dev/null 2>&1 || true; done; }
trap cleanup EXIT
start_server(){
  local root="$1" port="$2" log="$3"
  php -d display_errors=1 -d log_errors=1 -d error_reporting=E_ALL -S "127.0.0.1:${port}" -t "$root" >"$log" 2>&1 &
  local pid=$!; PIDS+=("$pid")
  for i in $(seq 1 50); do if curl -fsS "http://127.0.0.1:${port}/setup.php" -o /dev/null; then break; fi; sleep .25; done
  echo "$pid"
}
setup_root(){
  local root="$1" source_dir="$2" port="$3" pass="$4" label="$5"
  rm -rf "$root"; cp -a "$source_dir" "$root"
  local pid; pid=$(start_server "$root" "$port" "$ART/${label}-server.log")
  local cookie="$ART/${label}.cookies" page="$ART/${label}-setup.html"
  curl -fsS -c "$cookie" -b "$cookie" "http://127.0.0.1:${port}/setup.php" -o "$page"
  local csrf; csrf=$(python3 - "$page" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
  curl -fsS -c "$cookie" -b "$cookie" -X POST "http://127.0.0.1:${port}/setup.php" \
    --data-urlencode "setup_csrf=$csrf" --data-urlencode "site_title=P01 V2.32 Candidate Gate" \
    --data-urlencode "admin_password=$pass" --data-urlencode "admin_password_confirm=$pass" -o "$ART/${label}-setup-post.html"
  kill "$pid" >/dev/null 2>&1 || true
  php "$root/cli/verify.php" | tee "$ART/${label}-verify.txt" | grep -Fx VERIFY_PASS=YES >/dev/null
}
seed_source(){
  local root="$1" label="$2"
  ROOT="$root" OUT="$ART/${label}-before.json" php <<'PHP' | grep -Fx P01_V2320_SOURCE_SEED=PASS >/dev/null
<?php
declare(strict_types=1);
$root=getenv('ROOT');require $root.'/app/bootstrap.php';$r=new VfRepository(vf_db());
$pub=$r->createCategory(['name'=>'V232公开分类','is_private'=>false,'sort_order'=>20]);
$priv=$r->createCategory(['name'=>'V232私人分类','is_private'=>true,'sort_order'=>10]);
$r->saveLink(null,['category_id'=>$pub,'title'=>'V232公开保留项','url'=>'https://example.com/v232-public','is_private'=>false,'is_favorite'=>true,'tags'=>['V232','公开']]);
$r->saveLink(null,['category_id'=>$priv,'title'=>'V232私人保留项','url'=>'https://example.com/v232-private','is_private'=>true,'tags'=>['V232','私人']]);
$db=vf_db();$out=['links'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active'")->fetchColumn(),'categories'=>(int)$db->query("SELECT COUNT(*) FROM categories WHERE lifecycle_state='active'")->fetchColumn(),'favorites'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active' AND is_favorite=1")->fetchColumn(),'schema'=>(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status='success'")->fetchColumn()];
file_put_contents(getenv('OUT'),json_encode($out,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES));echo "P01_V2320_SOURCE_SEED=PASS\n";
PHP
  jq -e '.schema=="2026082901" and .links>=2 and .categories>=2 and .favorites>=1' "$ART/${label}-before.json" >/dev/null
}
verify_target(){
  local root="$1" label="$2"
  ROOT="$root" OUT="$ART/${label}-after.json" php <<'PHP' | grep -Fx P01_V2320_TARGET_VERIFY=PASS >/dev/null
<?php
declare(strict_types=1);
$root=getenv('ROOT');require $root.'/app/bootstrap.php';$db=vf_db();
$head=(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status='success'")->fetchColumn();if($head!=='2026082901')throw new RuntimeException('schema '.$head);
$i=strtolower((string)$db->query('PRAGMA integrity_check')->fetchColumn());$fk=$db->query('PRAGMA foreign_key_check')->fetchAll(PDO::FETCH_ASSOC);if($i!=='ok'||$fk)throw new RuntimeException('db integrity');
$out=['schema'=>$head,'links'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active'")->fetchColumn(),'categories'=>(int)$db->query("SELECT COUNT(*) FROM categories WHERE lifecycle_state='active'")->fetchColumn(),'favorites'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active' AND is_favorite=1")->fetchColumn(),'private'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE title='V232私人保留项' AND is_private=1")->fetchColumn(),'public'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE title='V232公开保留项' AND is_private=0")->fetchColumn(),'integrity'=>$i,'fk'=>count($fk)];
file_put_contents(getenv('OUT'),json_encode($out,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES));echo "P01_V2320_TARGET_VERIFY=PASS\n";
PHP
  local before="$ART/${label}-before.json"
  test "$(jq -r .links "$before")" = "$(jq -r .links "$ART/${label}-after.json")"
  test "$(jq -r .categories "$before")" = "$(jq -r .categories "$ART/${label}-after.json")"
  test "$(jq -r .favorites "$before")" = "$(jq -r .favorites "$ART/${label}-after.json")"
  jq -e '.schema=="2026082901" and .private==1 and .public==1 and .integrity=="ok" and .fk==0' "$ART/${label}-after.json" >/dev/null
  test "$(cat "$root/VERSION.txt")" = '2.32.0'
  grep -Fx "define('VF_VERSION', '2.32.0');" "$root/app/bootstrap.php" >/dev/null
  php "$root/cli/verify.php" | grep -Fx VERIFY_PASS=YES >/dev/null
}
verify_source_rollback(){
  local root="$1"
  test "$(cat "$root/VERSION.txt")" = '2.31.0'
  grep -Fx "define('VF_VERSION', '2.31.0');" "$root/app/bootstrap.php" >/dev/null
  ROOT="$root" php -r 'require getenv("ROOT")."/app/bootstrap.php";$db=vf_db();$h=(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status=\"success\"")->fetchColumn();if($h!=="2026082901")exit(2);if((int)$db->query("SELECT COUNT(*) FROM links WHERE title=\"V232私人保留项\" AND is_private=1")->fetchColumn()!==1)exit(3);echo "P01_V2320_SOURCE_ROLLBACK=PASS\n";' | grep -Fx P01_V2320_SOURCE_ROLLBACK=PASS >/dev/null
}

# 3. Real non-production V2.31 -> V2.32 update + data preservation + idempotence.
PASS='P01V2320Candidate!2026'
UP=/tmp/p01-v2320-upgrade-runtime
setup_root "$UP" production/src 18650 "$PASS" upgrade
seed_source "$UP" upgrade
php "$REPAIR" --verify-source="$UP" | tee "$ART/verify-source.json" | jq -e '.ok==true' >/dev/null
php "$REPAIR" --run="$UP" | tee "$ART/upgrade-run.json" | jq -e '.ok==true and .already_current==false and .schema=="2026082901"' >/dev/null
verify_target "$UP" upgrade
php "$REPAIR" --run="$UP" | tee "$ART/upgrade-idempotent.json" | jq -e '.ok==true and .already_current==true and .schema=="2026082901"' >/dev/null
php "$REPAIR" --verify-target="$UP" | tee "$ART/verify-target.json" | jq -e '.ok==true' >/dev/null
echo P01_V2310_TO_V2320_ACTUAL_UPGRADE_DATA=PASS | tee "$ART/upgrade-verdict.txt"

# 4. Failure rollback.
FAILROOT=/tmp/p01-v2320-fail-runtime
setup_root "$FAILROOT" production/src 18651 "$PASS" fail
seed_source "$FAILROOT" fail
set +e
VF_ATOMIC_TEST_FAIL_AFTER_APPLY=1 php "$REPAIR" --run="$FAILROOT" >"$ART/fail-run.out" 2>"$ART/fail-run.err"
RC=$?
set -e
test "$RC" -ne 0
verify_source_rollback "$FAILROOT"
if find "$FAILROOT" -path '*/updates/p01-atomic-transaction.json' -type f | grep .; then echo STALE_ATOMIC_TRANSACTION; exit 1; fi
echo P01_V2320_FAILURE_ROLLBACK=PASS | tee "$ART/rollback-verdict.txt"

# 5. Hard interruption and automatic recovery.
HARD=/tmp/p01-v2320-hard-runtime
setup_root "$HARD" production/src 18652 "$PASS" hard
seed_source "$HARD" hard
set +e
VF_ATOMIC_TEST_HARD_EXIT_AFTER_APPLY=1 php "$REPAIR" --run="$HARD" >"$ART/hard-run.out" 2>"$ART/hard-run.err"
RC=$?
set -e
test "$RC" = 97
find "$HARD" -path '*/updates/p01-atomic-transaction.json' -type f | grep . >/dev/null
php "$REPAIR" --run="$HARD" | tee "$ART/hard-recovery.json" | jq -e '.ok==true and .interrupted_recovered==true and .schema=="2026082901"' >/dev/null
verify_target "$HARD" hard
echo P01_V2320_INTERRUPTION_RECOVERY=PASS | tee "$ART/interruption-verdict.txt"

# 6. Fresh V2.32 runtime + deterministic Home fixtures.
FRESH=/tmp/p01-v2320-fresh-runtime
setup_root "$FRESH" candidate/src 18653 "$PASS" fresh
ROOT="$FRESH" OUT="$ART/home-fixture.json" php <<'PHP' | grep -Fx P01_V2320_HOME_FIXTURE=PASS >/dev/null
<?php
declare(strict_types=1);
$root=getenv('ROOT');require $root.'/app/bootstrap.php';$r=new VfRepository(vf_db());
$cat=$r->createCategory(['name'=>'V232 Home 分类','description'=>'candidate browser fixture','is_private'=>false,'sort_order'=>100]);
$id=$r->saveLink(null,['category_id'=>$cat,'title'=>'V232 Candidate Home Item','url'=>'https://example.com/v232-home','is_private'=>true,'is_favorite'=>true,'tags'=>['v232','home']]);
(new VfOperationHistory(vf_db()))->record('update','link',(int)$id,null,['title'=>'V232 Candidate Home Item'],'runner','',false);
(new VfLinkHealth(vf_db()))->confirmInvalid((int)$id,true);
file_put_contents(getenv('OUT'),json_encode(['id'=>(int)$id,'category_id'=>(int)$cat],JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES));
echo "P01_V2320_HOME_FIXTURE=PASS\n";
PHP
ROOT="$FRESH" php -r 'require getenv("ROOT")."/app/bootstrap.php";$db=vf_db();$h=(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status=\"success\"")->fetchColumn();if($h!=="2026082901"||VF_VERSION!=="2.32.0")exit(2);if(strtolower((string)$db->query("PRAGMA integrity_check")->fetchColumn())!=="ok")exit(3);if($db->query("PRAGMA foreign_key_check")->fetchAll(PDO::FETCH_ASSOC))exit(4);echo "P01_V2320_FRESH_RUNTIME=PASS\n";' | tee "$ART/fresh-runtime.txt" | grep -Fx P01_V2320_FRESH_RUNTIME=PASS >/dev/null

# 7. Candidate Desktop/Mobile Home smoke plus public/private root boundary.
php -S 127.0.0.1:18654 -t "$FRESH" >"$ART/browser-server.log" 2>&1 & BROWSER_PID=$!; PIDS+=("$BROWSER_PID")
for i in $(seq 1 50); do if curl -fsS http://127.0.0.1:18654/ -o /dev/null; then break; fi; sleep .25; done
mkdir -p /tmp/p01-v2320-browser && cd /tmp/p01-v2320-browser
npm init -y >/dev/null 2>&1
npm install playwright@1.55.0 --no-save >/dev/null 2>&1
npx playwright install chromium --with-deps >/dev/null 2>&1
cat >gate.mjs <<'JS'
import{chromium}from'playwright';import fs from'fs';
const base='http://127.0.0.1:18654',pass='P01V2320Candidate!2026',e='/tmp/p01-v2320-candidate-evidence';
const fixture=JSON.parse(fs.readFileSync(e+'/home-fixture.json','utf8'));const b=await chromium.launch({headless:true});
const login=async c=>{const r=await c.request.post(base+'/api.php?action=login',{data:{password:pass}});if(!r.ok())throw Error('login '+r.status())};
const d=await b.newContext({viewport:{width:1440,height:960}});await login(d);const root=await d.request.get(base+'/',{maxRedirects:0});if(root.status()!==302||!(root.headers()['location']||'').includes('home.php'))throw Error('admin root');
const opened=await d.request.get(base+'/surface-open.php?id='+fixture.id,{maxRedirects:0});if(![302,303].includes(opened.status()))throw Error('open '+opened.status());
const p=await d.newPage();await p.goto(base+'/home.php',{waitUntil:'networkidle'});if(await p.locator('.vf-home-command').count()!==1)throw Error('home');const text=await p.locator('.vf-home-command').innerText();for(const x of ['最近使用','我的收藏','全部资源','V232 Candidate Home Item','最近操作','网址需要检查','确认失效'])if(!text.includes(x))throw Error('missing '+x);if(await p.locator('.vf-home-action-section:visible').count()!==0)throw Error('zero pending placeholder');if(await p.locator('.vf-home-activity-item').count()<1)throw Error('activity');const activity=await p.locator('.vf-home-activity-section').innerText();if(!/(刚刚|分钟前|小时前|天前)/.test(activity))throw Error('relative time');await p.screenshot({path:e+'/candidate-home-desktop.png',fullPage:true});
const m=await b.newContext({viewport:{width:390,height:844},isMobile:true});await login(m);const mp=await m.newPage();await mp.goto(base+'/home.php',{waitUntil:'networkidle'});if(await mp.locator('.vf-home-mobile-command:visible').count()!==1)throw Error('mobile command');const overflow=await mp.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth);if(overflow>2)throw Error('overflow '+overflow);await mp.screenshot({path:e+'/candidate-home-mobile.png',fullPage:true});
const anon=await b.newContext();const ar=await anon.request.get(base+'/',{maxRedirects:0});if(ar.status()!==200)throw Error('anonymous root '+ar.status());const body=await ar.text();if(body.includes('vf-home-command')||body.includes('V232 Candidate Home Item'))throw Error('anonymous leakage');const hr=await anon.request.get(base+'/home.php',{maxRedirects:0});if(hr.status()!==302||(hr.headers()['location']||'').indexOf('index.php')<0)throw Error('anonymous home boundary');await b.close();console.log('P01_V2320_BROWSER_PASS');
JS
node gate.mjs | tee "$ART/browser.txt" | grep -Fx P01_V2320_BROWSER_PASS >/dev/null
cd /
php "$FRESH/cli/verify.php" | tee "$ART/post-browser-verify.txt" | grep -Fx VERIFY_PASS=YES >/dev/null
printf '%s\n' \
  P01_V2320_FRESH_INSTALL=PASS \
  P01_V2320_HOME_DESKTOP=PASS \
  P01_V2320_HOME_MOBILE=PASS \
  P01_V2320_HOME_RECENT_FAVORITE=PASS \
  P01_V2320_HOME_ACTIVITY=PASS \
  P01_V2320_HOME_HEALTH_SIGNAL=PASS \
  P01_V2320_ZERO_PENDING_NO_PLACEHOLDER=PASS \
  P01_V2320_ADMIN_ROOT_HOME=PASS \
  P01_V2320_ANONYMOUS_PUBLIC_ROOT=PASS \
  P01_V2320_NO_HORIZONTAL_OVERFLOW=PASS | tee "$ART/browser-verdict.txt"

# Final machine verdict. Candidate artifacts remain CI-only and unpublished.
FULL_SHA=$(sha256sum "$FULL" | awk '{print $1}')
UPDATE_SHA=$(sha256sum "$UPDATE" | awk '{print $1}')
REPAIR_SHA=$(sha256sum "$REPAIR" | awk '{print $1}')
cat >"$ART/verdict.txt" <<EOF
P01_V2320_CANDIDATE_SOURCE=$CANDIDATE
P01_V2320_CANDIDATE_TREE=$CANDIDATE_TREE
P01_V2320_RUNTIME_TREE=$RUNTIME_TREE
P01_V2320_SOURCE_VERSION=2.31.0
P01_V2320_TARGET_VERSION=2.32.0
P01_V2320_SCHEMA=$SCHEMA
P01_V2320_VERSION_TRIPLE_BINDING=PASS
P01_V2320_RUNTIME_DELTA_8=PASS
P01_V2320_HOME_BYTES_BOUND_TO_V9=PASS
P01_V2320_DETERMINISTIC_ARTIFACTS=PASS
P01_V2320_ACTUAL_UPGRADE=PASS
P01_V2320_DATA_PRESERVATION=PASS
P01_V2320_IDEMPOTENCE=PASS
P01_V2320_FAILURE_ROLLBACK=PASS
P01_V2320_INTERRUPTION_RECOVERY=PASS
P01_V2320_FRESH_RUNTIME=PASS
P01_V2320_DESKTOP_MOBILE_HOME=PASS
P01_V2320_PUBLIC_PRIVATE_BOUNDARY=PASS
P01_V2320_FULL_SHA256=$FULL_SHA
P01_V2320_UPDATE_SHA256=$UPDATE_SHA
P01_V2320_REPAIR_SHA256=$REPAIR_SHA
P01_V2320_READY_FOR_METADATA_CLOSURE=YES
FORMAL_RELEASE=NOT_STARTED
OWNER_PRODUCTION_WRITE=NO
EOF
cat "$ART/verdict.txt"
