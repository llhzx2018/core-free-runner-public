#!/usr/bin/env bash
set -Eeuo pipefail

FORMAL='28fc399d2d0ccc30531d6421d180db079ec571d9'
TREE='9545d334b626fce3968cdee92f09d13c58b2ae8e'
SRC_TREE='2878bad87c495a42573aa7f71f1cc12cf824d722'
SOURCE='e010d484c8879737503a02612d0ba8cff1d2fd7d'
SOURCE_SCHEMA='2026082801'
TARGET_SCHEMA='2026082901'
ART=/tmp/p01-v229-formal-evidence
rm -rf "$ART" /tmp/p01-v229-*runtime /tmp/p01-v229-browser
mkdir -p "$ART"

test "$(git -C candidate rev-parse HEAD)" = "$FORMAL"
test "$(git -C candidate rev-parse HEAD^{tree})" = "$TREE"
test "$(git -C candidate rev-parse HEAD:src)" = "$SRC_TREE"
test "$(git -C production rev-parse HEAD)" = "$SOURCE"
test "$(cat candidate/VERSION)" = '2.29.0'
test "$(cat candidate/src/VERSION.txt)" = '2.29.0'
grep -F "define('VF_VERSION', '2.29.0')" candidate/src/app/bootstrap.php >/dev/null
grep -F "'version' => '2026082901'" candidate/src/migrations/2026082901_v229_resource_domains.php >/dev/null
while IFS= read -r -d '' f; do php -l "$f" >/dev/null; done < <(find candidate/src -type f -name '*.php' -print0)
for f in candidate/src/assets/*.js candidate/src/plugins/rss/assets/*.js; do node --check "$f" >/dev/null; done
echo P01_V229_FORMAL_SOURCE_SYNTAX=PASS

python3 runner/scripts/p01-v229-build-artifacts.py | tee "$ART/build.json"
REPAIR=/tmp/p01-v229-artifacts/repair-v2.29.0.php
php -l "$REPAIR" >/dev/null
php "$REPAIR" --self-test | tee "$ART/repair-self-test.json" | jq -e '.ok==true and .global_barrier==true and .interruption_recovery==true' >/dev/null
jq -e '.status=="FORMAL_ARTIFACT_BUILD_PASS" and .formal_source=="28fc399d2d0ccc30531d6421d180db079ec571d9" and .formal_tree=="9545d334b626fce3968cdee92f09d13c58b2ae8e" and .source_schema=="2026082801" and .schema=="2026082901" and .schema_change==true and .atomic_schema_migration==true' /tmp/p01-v229-artifacts/P01-V2.29.0-FORMAL-GATE.json >/dev/null
echo P01_V229_FORMAL_ARTIFACT_BUILD=PASS

PIDS=()
cleanup(){ for p in "${PIDS[@]:-}"; do kill "$p" >/dev/null 2>&1 || true; done; }
trap cleanup EXIT
start_server(){
  local root="$1" port="$2" log="$3"
  php -d display_errors=1 -d log_errors=1 -d error_reporting=E_ALL -S "127.0.0.1:${port}" -t "$root" >"$log" 2>&1 &
  local pid=$!; PIDS+=("$pid")
  for i in $(seq 1 40); do curl -fsS "http://127.0.0.1:${port}/setup.php" -o /dev/null && break || sleep 0.25; done
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
    --data-urlencode "setup_csrf=$csrf" --data-urlencode "site_title=P01 V2.29 Formal Gate" \
    --data-urlencode "admin_password=$pass" --data-urlencode "admin_password_confirm=$pass" -o "$ART/${label}-setup-post.html"
  kill "$pid" >/dev/null 2>&1 || true
  php "$root/cli/verify.php" | tee "$ART/${label}-verify.txt" | grep -Fx VERIFY_PASS=YES >/dev/null
}
seed_source(){
  local root="$1" label="$2"
  cat >"$ART/${label}-seed.php" <<'PHP'
<?php
declare(strict_types=1);
$root=getenv('ROOT');require $root.'/app/bootstrap.php';
$r=new VfRepository(vf_db());
$pub=$r->createCategory(['name'=>'正式升级公开分类','is_private'=>false,'sort_order'=>10]);
$priv=$r->createCategory(['name'=>'正式升级私人分类','is_private'=>true,'sort_order'=>20]);
$a=$r->saveLink(null,['category_id'=>$pub,'title'=>'公开导航保留项','url'=>'https://example.com/formal-public','is_private'=>false,'is_favorite'=>true,'tags'=>['正式','公开']]);
$b=$r->saveLink(null,['category_id'=>$priv,'title'=>'私人导航保留项','url'=>'https://example.com/formal-private','is_private'=>true,'tags'=>['正式','私人']]);
$c=$r->saveLink(null,['category_id'=>$priv,'title'=>'公开频道兼容项','url'=>'https://example.com/formal-channel','is_private'=>false,'tags'=>['频道','公开']]);
$d=$r->saveLink(null,['category_id'=>$pub,'title'=>'私人影视兼容项','url'=>'https://example.com/formal-watch','is_private'=>true,'tags'=>['影视','私人']]);
$db=vf_db();$now=gmdate('c');
$ins=$db->prepare("INSERT INTO resource_surface_profiles(link_id,surface,resource_kind,note,background_friendly,media_year,media_status,last_opened_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)");
$ins->execute([(int)$c['id'],'channels','科技频道','legacy-channel',1,null,'','',$now,$now]);
$ins->execute([(int)$d['id'],'watch','电影','legacy-watch',0,2026,'want','',$now,$now]);
$out=['links'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active'")->fetchColumn(),'categories'=>(int)$db->query("SELECT COUNT(*) FROM categories WHERE lifecycle_state='active'")->fetchColumn(),'favorites'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active' AND is_favorite=1")->fetchColumn(),'legacy_profiles'=>(int)$db->query('SELECT COUNT(*) FROM resource_surface_profiles')->fetchColumn(),'schema'=>(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status='success'")->fetchColumn()];
file_put_contents(getenv('OUT'),json_encode($out,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES));echo "P01_V229_SOURCE_SEED=PASS\n";
PHP
  ROOT="$root" OUT="$ART/${label}-before.json" php "$ART/${label}-seed.php" | grep -Fx P01_V229_SOURCE_SEED=PASS >/dev/null
  jq -e '.legacy_profiles==2 and .schema=="2026082801"' "$ART/${label}-before.json" >/dev/null
}
verify_target(){
  local root="$1" label="$2"
  cat >"$ART/${label}-target.php" <<'PHP'
<?php
declare(strict_types=1);
$root=getenv('ROOT');require $root.'/app/bootstrap.php';$db=vf_db();
$head=(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status='success'")->fetchColumn();if($head!=='2026082901')throw new RuntimeException('schema '.$head);
foreach(['resource_domain_profiles','resource_asset_files'] as $t){$q=$db->prepare("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?");$q->execute([$t]);if((int)$q->fetchColumn()!==1)throw new RuntimeException('missing '.$t);}
$links=(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active'")->fetchColumn();$cats=(int)$db->query("SELECT COUNT(*) FROM categories WHERE lifecycle_state='active'")->fetchColumn();$fav=(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active' AND is_favorite=1")->fetchColumn();$profiles=$db->query("SELECT domain_key,resource_kind,note FROM resource_domain_profiles ORDER BY link_id")->fetchAll(PDO::FETCH_ASSOC);
if(count($profiles)!==2||($profiles[0]['domain_key']??'')!=='channels'||($profiles[1]['domain_key']??'')!=='watch')throw new RuntimeException('profile migration');
$pub=$db->query("SELECT l.is_private,c.is_private FROM links l JOIN categories c ON c.id=l.category_id WHERE l.title='公开频道兼容项'")->fetch(PDO::FETCH_NUM);if(!$pub||(int)$pub[0]!==0||(int)$pub[1]!==1)throw new RuntimeException('non-nav privacy fixture lost');
$i=strtolower((string)$db->query('PRAGMA integrity_check')->fetchColumn());$fk=$db->query('PRAGMA foreign_key_check')->fetchAll(PDO::FETCH_ASSOC);if($i!=='ok'||$fk)throw new RuntimeException('db integrity');
file_put_contents(getenv('OUT'),json_encode(['schema'=>$head,'links'=>$links,'categories'=>$cats,'favorites'=>$fav,'profiles'=>$profiles,'integrity'=>$i,'fk'=>count($fk)],JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES));echo "P01_V229_TARGET_VERIFY=PASS\n";
PHP
  ROOT="$root" OUT="$ART/${label}-after.json" php "$ART/${label}-target.php" | grep -Fx P01_V229_TARGET_VERIFY=PASS >/dev/null
  local before="$ART/${label}-before.json"
  test "$(jq -r .links "$before")" = "$(jq -r .links "$ART/${label}-after.json")"
  test "$(jq -r .categories "$before")" = "$(jq -r .categories "$ART/${label}-after.json")"
  test "$(jq -r .favorites "$before")" = "$(jq -r .favorites "$ART/${label}-after.json")"
  php "$root/cli/verify.php" | grep -Fx VERIFY_PASS=YES >/dev/null
}
verify_source_rollback(){
  local root="$1"
  test "$(cat "$root/VERSION.txt")" = '2.28.0'
  ROOT="$root" php -r 'require getenv("ROOT")."/app/bootstrap.php";$db=vf_db();$h=(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status=\"success\"")->fetchColumn();if($h!=="2026082801")exit(2);$q=$db->query("SELECT COUNT(*) FROM sqlite_master WHERE type=\"table\" AND name=\"resource_domain_profiles\"");if((int)$q->fetchColumn()!==0)exit(3);echo "P01_V229_SOURCE_ROLLBACK=PASS\n";' | grep -Fx P01_V229_SOURCE_ROLLBACK=PASS >/dev/null
}

PASS='P01V229Formal!2026'
UP=/tmp/p01-v229-upgrade-runtime
setup_root "$UP" production/src 18529 "$PASS" upgrade
seed_source "$UP" upgrade
php "$REPAIR" --verify-source="$UP" | jq -e '.ok==true' >/dev/null
php "$REPAIR" --run="$UP" | tee "$ART/upgrade-run.json" | jq -e '.ok==true and .already_current==false and .schema=="2026082901"' >/dev/null
verify_target "$UP" upgrade
php "$REPAIR" --run="$UP" | tee "$ART/upgrade-idempotent.json" | jq -e '.ok==true and .already_current==true and .schema=="2026082901"' >/dev/null
php "$REPAIR" --verify-target="$UP" | jq -e '.ok==true' >/dev/null
echo P01_V228_TO_V229_ACTUAL_UPGRADE=PASS

FAILROOT=/tmp/p01-v229-fail-runtime
setup_root "$FAILROOT" production/src 18530 "$PASS" fail
seed_source "$FAILROOT" fail
set +e
VF_ATOMIC_TEST_FAIL_AFTER_MIGRATION=1 php "$REPAIR" --run="$FAILROOT" >"$ART/fail-run.out" 2>"$ART/fail-run.err"
RC=$?
set -e
test "$RC" -ne 0
verify_source_rollback "$FAILROOT"
test ! -f "$FAILROOT/private_data/updates/p01-atomic-transaction.json"
echo P01_V229_SCHEMA_FAILURE_ROLLBACK=PASS

HARD=/tmp/p01-v229-hard-runtime
setup_root "$HARD" production/src 18531 "$PASS" hard
seed_source "$HARD" hard
set +e
VF_ATOMIC_TEST_HARD_EXIT_AFTER_MIGRATION=1 php "$REPAIR" --run="$HARD" >"$ART/hard-run.out" 2>"$ART/hard-run.err"
RC=$?
set -e
test "$RC" = 98
find "$HARD" -path '*/updates/p01-atomic-transaction.json' -type f | grep . >/dev/null
php "$REPAIR" --run="$HARD" | tee "$ART/hard-recovery.json" | jq -e '.ok==true and .interrupted_recovered==true and .schema=="2026082901"' >/dev/null
verify_target "$HARD" hard
echo P01_V229_SCHEMA_INTERRUPTION_RECOVERY=PASS

FRESH=/tmp/p01-v229-fresh-runtime
setup_root "$FRESH" candidate/src 18532 "$PASS" fresh
ROOT="$FRESH" php -r 'require getenv("ROOT")."/app/bootstrap.php";$db=vf_db();$h=(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status=\"success\"")->fetchColumn();if($h!=="2026082901")exit(2);foreach(["resource_domain_profiles","resource_asset_files"] as $t){$q=$db->prepare("SELECT COUNT(*) FROM sqlite_master WHERE type=\"table\" AND name=?");$q->execute([$t]);if((int)$q->fetchColumn()!==1)exit(3);}echo "P01_V229_FRESH_SCHEMA=PASS\n";' | grep -Fx P01_V229_FRESH_SCHEMA=PASS >/dev/null

PID=$(start_server "$FRESH" 18532 "$ART/fresh-browser-server.log")
mkdir -p /tmp/p01-v229-browser && cd /tmp/p01-v229-browser
npm init -y >/dev/null 2>&1
npm install playwright@1.55.0 --no-save >/dev/null 2>&1
npx playwright install chromium >/dev/null 2>&1
cat > smoke.mjs <<'JS'
import { chromium } from 'playwright';
const base='http://127.0.0.1:18532', pass='P01V229Formal!2026';
const browser=await chromium.launch({headless:true});
const ctx=await browser.newContext({viewport:{width:1440,height:900}});
const login=await ctx.request.post(base+'/api.php?action=login',{data:{password:pass}});if(!login.ok())throw new Error('login');
const p=await ctx.newPage();
for(const [path,label] of [['/surfaces.php','全部资源'],['/start.php','导航'],['/channels.php','频道'],['/watch.php','影视'],['/topics.php','专题']]){await p.goto(base+path,{waitUntil:'networkidle'});if(!(await p.locator('body').innerText()).includes(label))throw new Error(path+' missing '+label);}
await p.goto(base+'/topics.php',{waitUntil:'networkidle'});await p.screenshot({path:'/tmp/p01-v229-formal-evidence/desktop-topics.png',fullPage:true});
const mobile=await browser.newContext({viewport:{width:390,height:844}});const ml=await mobile.request.post(base+'/api.php?action=login',{data:{password:pass}});if(!ml.ok())throw new Error('mobile login');const mp=await mobile.newPage();await mp.goto(base+'/surfaces.php',{waitUntil:'networkidle'});const overflow=await mp.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+2);if(overflow)throw new Error('mobile horizontal overflow');await mp.goto(base+'/topics.php',{waitUntil:'networkidle'});await mp.screenshot({path:'/tmp/p01-v229-formal-evidence/mobile-topics.png',fullPage:true});await mobile.close();await browser.close();console.log('P01_V229_BROWSER_UI=PASS');
JS
node smoke.mjs | grep -Fx P01_V229_BROWSER_UI=PASS >/dev/null
cd "$GITHUB_WORKSPACE"
kill "$PID" >/dev/null 2>&1 || true

echo P01_V229_FRESH_INSTALL_UI=PASS

grep -F "sandbox allow-scripts" candidate/src/resource-html.php >/dev/null
grep -F "connect-src 'none'" candidate/src/resource-html.php >/dev/null
! grep -F "allow-same-origin" candidate/src/resource-html.php >/dev/null
php "$FRESH/cli/verify.php" | grep -Fx VERIFY_PASS=YES >/dev/null
ROOT="$FRESH" php -r 'require getenv("ROOT")."/app/bootstrap.php";$db=vf_db();if(strtolower((string)$db->query("PRAGMA integrity_check")->fetchColumn())!=="ok")exit(2);if($db->query("PRAGMA foreign_key_check")->fetchAll(PDO::FETCH_ASSOC))exit(3);echo "P01_V229_FINAL_SQLITE=PASS\n";' | grep -Fx P01_V229_FINAL_SQLITE=PASS >/dev/null

echo "FORMAL_SOURCE=$FORMAL" > "$ART/verdict.txt"
echo "FORMAL_TREE=$TREE" >> "$ART/verdict.txt"
echo "SOURCE_VERSION=2.28.0" >> "$ART/verdict.txt"
echo "TARGET_VERSION=2.29.0" >> "$ART/verdict.txt"
echo "SOURCE_SCHEMA=$SOURCE_SCHEMA" >> "$ART/verdict.txt"
echo "TARGET_SCHEMA=$TARGET_SCHEMA" >> "$ART/verdict.txt"
echo 'P01_V229_FORMAL_ARTIFACT_GATE=PASS' >> "$ART/verdict.txt"
echo 'P01_V229_READY_FOR_MAIN_PROMOTION=YES' >> "$ART/verdict.txt"
cat "$ART/verdict.txt"
