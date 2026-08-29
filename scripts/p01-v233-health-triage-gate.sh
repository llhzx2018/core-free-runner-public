#!/usr/bin/env bash
set -Eeuo pipefail
PRODUCT=${PRODUCT:?}; ROOT=${ROOT:?}; PORT=${PORT:?}; ADMIN_PASS=${ADMIN_PASS:?}; EVID=${EVID:?}; SOURCE=${SOURCE:?}; SOURCE_TREE=${SOURCE_TREE:?}; BASE_SOURCE=${BASE_SOURCE:?}
mkdir -p "$EVID"
COOKIE=/tmp/p01-v233-health.cookies
PIDFILE=/tmp/p01-v233-health.pid
cleanup(){ rm -f "$ROOT/__p01_v233_category_seed.php" "$ROOT/__p01_v233_health_fixture.php"; if test -f "$PIDFILE"; then kill "$(cat "$PIDFILE")" >/dev/null 2>&1 || true; fi; }
trap cleanup EXIT

# 1. Exact source / strict four-file delta / syntax / version.
test "$(git -C "$PRODUCT" rev-parse HEAD)" = "$SOURCE"
test "$(git -C "$PRODUCT" rev-parse HEAD^{tree})" = "$SOURCE_TREE"
test "$(tr -d '\r\n' < "$PRODUCT/VERSION")" = 2.32.0
test "$(tr -d '\r\n' < "$ROOT/VERSION.txt")" = 2.32.0
git -C "$PRODUCT" diff --name-only "$BASE_SOURCE"...HEAD | sort >"$EVID/actual-diff.txt"
printf '%s\n' src/app/FunctionalHome.php src/app/LinkHealth.php src/assets/health.js src/health.php | sort >"$EVID/expected-diff.txt"
diff -u "$EVID/expected-diff.txt" "$EVID/actual-diff.txt"
php -l "$ROOT/app/FunctionalHome.php" >/dev/null
php -l "$ROOT/app/LinkHealth.php" >/dev/null
php -l "$ROOT/health.php" >/dev/null
node -e "new Function(require('fs').readFileSync(process.env.ROOT+'/assets/health.js','utf8')); console.log('HEALTH_JS_SYNTAX=PASS')" | tee "$EVID/js-syntax.txt"
git -C "$PRODUCT" diff --check "$BASE_SOURCE"...HEAD
printf '%s\n' P01_V233_HEALTH_SOURCE_FENCE=PASS P01_V233_HEALTH_FOUR_FILE_DELTA=PASS P01_V233_VERSION_UNCHANGED_2.32.0=PASS | tee "$EVID/source.txt"

# 2. Fresh runtime and integrity.
rm -f "$COOKIE"
php -S "127.0.0.1:${PORT}" -t "$ROOT" >"$EVID/server.log" 2>&1 & echo $! >"$PIDFILE"
for i in $(seq 1 50); do if curl -fsS -c "$COOKIE" -b "$COOKIE" "http://127.0.0.1:${PORT}/setup.php" -o /tmp/p01-v233-health-setup.html; then break; fi; sleep .25; done
test -s /tmp/p01-v233-health-setup.html
CSRF=$(python3 - <<'PY'
import re
s=open('/tmp/p01-v233-health-setup.html',encoding='utf-8').read();m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsS -c "$COOKIE" -b "$COOKIE" -X POST "http://127.0.0.1:${PORT}/setup.php" --data-urlencode "setup_csrf=$CSRF" --data-urlencode 'site_title=P01 V233 Health Triage Gate' --data-urlencode "admin_password=$ADMIN_PASS" --data-urlencode "admin_password_confirm=$ADMIN_PASS" -o "$EVID/setup-post.html"
test -f "$ROOT/app/.runtime.php"
php "$ROOT/cli/verify.php" | tee "$EVID/fresh-verify.txt" | grep -Fx VERIFY_PASS=YES
php -r 'require getenv("ROOT")."/app/bootstrap.php";$db=vf_db();echo "SCHEMA=".(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status=\"success\"")->fetchColumn().PHP_EOL;echo "SQLITE=".strtolower((string)$db->query("PRAGMA integrity_check")->fetchColumn()).PHP_EOL;echo "FK=".count($db->query("PRAGMA foreign_key_check")->fetchAll(PDO::FETCH_ASSOC)).PHP_EOL;' | tee "$EVID/runtime.txt"
grep -Fx SCHEMA=2026082901 "$EVID/runtime.txt"; grep -Fx SQLITE=ok "$EVID/runtime.txt"; grep -Fx FK=0 "$EVID/runtime.txt"

# 3. Runner-only authenticated fixture helpers. They never ship with product source.
cat >"$ROOT/__p01_v233_category_seed.php" <<'PHP'
<?php
declare(strict_types=1);
require __DIR__ . '/app/bootstrap.php';
header('Content-Type: text/plain; charset=utf-8');header('Cache-Control: no-store');
if (!vf_is_admin()) { http_response_code(403); echo "FORBIDDEN\n"; exit; }
try { $id=(new VfRepository(vf_db()))->createCategory(['name'=>'V233 Health Triage','description'=>'runner-only fixture','is_private'=>false,'sort_order'=>100]); echo "CATEGORY_ID=".(int)$id."\n"; }
finally { @unlink(__FILE__); }
PHP
cat >"$ROOT/__p01_v233_health_fixture.php" <<'PHP'
<?php
declare(strict_types=1);
require __DIR__ . '/app/bootstrap.php';
header('Content-Type: application/json; charset=utf-8');header('Cache-Control: no-store');
if (!vf_is_admin()) { http_response_code(403); echo json_encode(['ok'=>false]); exit; }
$db=vf_db();$rows=$db->query("SELECT id,title FROM links WHERE lifecycle_state='active' AND title LIKE 'V233 Health %' ORDER BY id ASC")->fetchAll(PDO::FETCH_ASSOC);
if(count($rows)!==49){http_response_code(409);echo json_encode(['ok'=>false,'count'=>count($rows)]);exit;}
$now=gmdate('c');
$stmt=$db->prepare("INSERT INTO link_health(link_id,status,http_status,final_url,redirect_count,response_ms,error_kind,last_error,last_success_at,last_checked_at,consecutive_failures,manual_confirmed,ignore_auto,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(link_id) DO UPDATE SET status=excluded.status,http_status=excluded.http_status,final_url=excluded.final_url,redirect_count=excluded.redirect_count,response_ms=excluded.response_ms,error_kind=excluded.error_kind,last_error=excluded.last_error,last_success_at=excluded.last_success_at,last_checked_at=excluded.last_checked_at,consecutive_failures=excluded.consecutive_failures,manual_confirmed=excluded.manual_confirmed,ignore_auto=excluded.ignore_auto,updated_at=excluded.updated_at");
$db->beginTransaction();
try{
  foreach($rows as $row){
    $title=(string)$row['title'];$status='restricted';$http=403;$kind='http';$error='HTTP 403 / runner fixture';$fail=1;$ignore=0;
    if(str_contains($title,'Temporary')){$status='temporary';$http=0;$kind='timeout';$error='timeout / runner fixture';$fail=1;}
    elseif(str_contains($title,'Suspected')){$status='suspected';$http=404;$kind='http';$error='HTTP 404 / runner fixture';$fail=2;}
    elseif($title==='V233 Health Restricted 43'){$ignore=1;}
    $stmt->execute([(int)$row['id'],$status,$http,'',0,120,$kind,$error,'',$now,$fail,0,$ignore,$now]);
  }
  $db->commit();
}catch(Throwable $e){if($db->inTransaction())$db->rollBack();throw $e;}
$status=(new VfLinkHealth($db))->status();
@unlink(__FILE__);
echo json_encode(['ok'=>true,'status'=>$status],JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);
PHP
php -l "$ROOT/__p01_v233_category_seed.php" >/dev/null
php -l "$ROOT/__p01_v233_health_fixture.php" >/dev/null

# 4. Deterministic Browser gate: 43 restricted (1 ignored), 5 temporary, 1 suspected.
mkdir -p /tmp/p01-v233-health-browser && cd /tmp/p01-v233-health-browser
npm init -y >/dev/null 2>&1; npm install playwright@1.55.0 --no-save >/dev/null 2>&1; npx playwright install chromium --with-deps >/dev/null 2>&1
cat >gate.mjs <<'JS'
import{chromium}from'playwright';import fs from'fs';
const base='http://127.0.0.1:18673',pass='P01V233!HealthGate',e='/tmp/p01-v233-health-evidence';
const browser=await chromium.launch({headless:true});
const c=await browser.newContext({viewport:{width:1440,height:1000}});
const login=await c.request.post(base+'/api.php?action=login',{data:{password:pass}});if(!login.ok())throw new Error('login '+login.status());
const seed=await c.request.get(base+'/__p01_v233_category_seed.php');const seedText=(await seed.text()).trim();if(seed.status()!==200||!/^CATEGORY_ID=\d+$/.test(seedText))throw new Error('seed '+seed.status()+' '+seedText);const cat=seedText.split('=')[1];
const p=await c.newPage();await p.goto(base+'/home.php',{waitUntil:'networkidle'});
const create=async(title,url)=>await p.evaluate(async({title,url,cat})=>{const state=JSON.parse(document.getElementById('vf-workspace-data')?.textContent||'{}');const fd=new FormData();for(const[k,v]of Object.entries({csrf:state.csrf||'',category_id:cat,title,url,surface:'start',resource_kind:'Health Gate',description:'runner-only health triage fixture',tags:'v233-health',is_private:'1',is_favorite:'0',source_kind:'remote_url'}))fd.set(k,String(v));const r=await fetch('workspace-create.php',{method:'POST',body:fd,credentials:'same-origin',headers:{'X-Requested-With':'XMLHttpRequest'}});const j=await r.json();if(!r.ok||!j.ok)throw new Error(j.error||String(r.status));return j;},{title,url,cat});
for(let i=1;i<=43;i++)await create('V233 Health Restricted '+String(i).padStart(2,'0'),'https://restricted-'+i+'.v233-health.example.com');
for(let i=1;i<=5;i++)await create('V233 Health Temporary '+String(i).padStart(2,'0'),'https://temporary-'+i+'.v233-health.example.com');
await create('V233 Health Suspected 01','https://suspected-1.v233-health.example.com');
const fixture=await c.request.get(base+'/__p01_v233_health_fixture.php');if(!fixture.ok())throw new Error('fixture '+fixture.status()+' '+await fixture.text());const fj=await fixture.json();const s=fj.status||{};
const expectNum=(key,n)=>{if(Number(s[key]??-1)!==n)throw new Error(key+' expected '+n+' got '+JSON.stringify(s))};
expectNum('restricted',43);expectNum('restrictedReview',42);expectNum('temporary',5);expectNum('temporaryReview',5);expectNum('suspected',1);expectNum('suspectedReview',1);expectNum('ignored',1);expectNum('problems',49);expectNum('attention',1);expectNum('needsAction',6);
await p.goto(base+'/home.php',{waitUntil:'networkidle'});const home=p.locator('.vf-home-health-section');if(await home.count()!==1)throw new Error('home health missing');const ht=(await home.innerText()).trim();for(const x of ['有 6 个网址需要处理','疑似失效','暂时异常','访问受限（人工确认）','42','进入网址健康治理'])if(!ht.includes(x))throw new Error('home missing '+x+'\n'+ht);if(ht.includes('49 个网址需要处理')||ht.includes('48 个网址需要处理'))throw new Error('raw problems leaked into headline '+ht);await p.screenshot({path:e+'/home-health-triage-desktop.png',fullPage:true});
await p.goto(base+'/health.php',{waitUntil:'networkidle'});await p.waitForFunction(()=>document.querySelector('#summary')?.textContent.includes('访问受限（需人工确认）'));const summary=(await p.locator('#summary').innerText()).trim();for(const x of ['1\n疑似失效','5\n暂时异常','42\n访问受限（需人工确认）','1\n已忽略自动'])if(!summary.includes(x))throw new Error('summary missing '+x+'\n'+summary);
await p.selectOption('#status','restricted');await p.waitForFunction(()=>document.querySelector('#list')?.textContent.includes('V233 Health Restricted'));const first=p.locator('#list tbody tr').first();const rowText=(await first.innerText()).trim();if(!rowText.includes('不要直接判定失效'))throw new Error('restricted guidance missing '+rowText);const open=first.locator('a',{hasText:'打开网址'});if(await open.count()!==1)throw new Error('open url action missing');if(await open.getAttribute('target')!=='_blank')throw new Error('open target');const rel=await open.getAttribute('rel');if(!String(rel||'').includes('noopener')||!String(rel||'').includes('noreferrer'))throw new Error('open rel '+rel);
for(const action of ['retry','history','ignore','confirm','pending','trash'])if(await first.locator('[data-action="'+action+'"]').count()!==1)throw new Error('legacy action missing '+action);
const ignore=first.locator('[data-action="ignore"]');await ignore.click();await p.waitForFunction(()=>document.querySelector('#summary')?.textContent.includes('41')&&document.querySelector('#summary')?.textContent.includes('2'));let st=await (await c.request.get(base+'/api.php?action=link_health_status')).json();if(Number(st.status?.needsAction)!==6||Number(st.status?.restrictedReview)!==41||Number(st.status?.ignored)!==2)throw new Error('ignore triage authority '+JSON.stringify(st.status));
const restore=p.locator('#list tbody tr').first().locator('[data-action="ignore"]');if(!(await restore.innerText()).includes('恢复自动检查'))throw new Error('restore copy');await restore.click();await p.waitForFunction(()=>document.querySelector('#summary')?.textContent.includes('42')&&document.querySelector('#summary')?.textContent.includes('1'));
await p.screenshot({path:e+'/health-triage-desktop.png',fullPage:true});
const m=await browser.newContext({viewport:{width:390,height:844},isMobile:true});const ml=await m.request.post(base+'/api.php?action=login',{data:{password:pass}});if(!ml.ok())throw new Error('mobile login');const mp=await m.newPage();await mp.goto(base+'/home.php',{waitUntil:'networkidle'});if(!(await mp.locator('.vf-home-health-section').innerText()).includes('有 6 个网址需要处理'))throw new Error('mobile home triage');let overflow=await mp.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth);if(overflow>2)throw new Error('mobile home overflow '+overflow);await mp.screenshot({path:e+'/home-health-triage-mobile.png',fullPage:true});await mp.goto(base+'/health.php',{waitUntil:'networkidle'});await mp.waitForFunction(()=>document.querySelector('#summary')?.textContent.includes('访问受限（需人工确认）'));overflow=await mp.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth);if(overflow>2)throw new Error('mobile health overflow '+overflow);await mp.screenshot({path:e+'/health-triage-mobile.png',fullPage:true});
const anon=await browser.newContext({viewport:{width:1280,height:800}});const ap=await anon.newPage();const ar=await ap.goto(base+'/',{waitUntil:'networkidle'});if(!ar||ar.status()!==200)throw new Error('anonymous root '+(ar&&ar.status()));const at=await ap.locator('body').innerText();if(at.includes('V233 Health Restricted')||at.includes('V233 Health Temporary')||at.includes('V233 Health Suspected'))throw new Error('private fixture leaked anonymous');
await anon.close();await m.close();await c.close();await browser.close();
fs.writeFileSync(e+'/browser-verdict.txt','P01_V233_RAW_PROBLEMS_COMPAT_49=PASS\nP01_V233_HOME_NEEDS_ACTION_6=PASS\nP01_V233_RESTRICTED_REVIEW_42=PASS\nP01_V233_RESTRICTED_NOT_INVALID=PASS\nP01_V233_OPEN_URL_ACTION=PASS\nP01_V233_IGNORE_EXCLUDED_FROM_REVIEW=PASS\nP01_V233_LEGACY_HEALTH_ACTIONS=PASS\nP01_V233_DESKTOP_MOBILE=PASS\nP01_V233_ANONYMOUS_BOUNDARY=PASS\n');console.log('HEALTH_TRIAGE_BROWSER_PASS');
JS
node gate.mjs | tee "$EVID/browser.txt" | grep -Fx HEALTH_TRIAGE_BROWSER_PASS
cd /
test ! -e "$ROOT/__p01_v233_category_seed.php"; test ! -e "$ROOT/__p01_v233_health_fixture.php"
php "$ROOT/cli/verify.php" | tee "$EVID/post-verify.txt" | grep -Fx VERIFY_PASS=YES
cat >"$EVID/verdict.txt" <<EOF
P01_V233_HEALTH_TRIAGE_SOURCE=$SOURCE
P01_V233_HEALTH_TRIAGE_TREE=$SOURCE_TREE
P01_V233_HEALTH_TRIAGE=PASS
P01_V233_HEALTH_FOUR_FILE_DELTA=PASS
P01_V233_RAW_PROBLEMS_COMPAT_49=PASS
P01_V233_HOME_NEEDS_ACTION_6=PASS
P01_V233_RESTRICTED_REVIEW_42=PASS
P01_V233_RESTRICTED_NOT_INVALID=PASS
P01_V233_OPEN_URL_ACTION=PASS
P01_V233_IGNORE_EXCLUDED_FROM_REVIEW=PASS
P01_V233_LEGACY_HEALTH_ACTIONS=PASS
P01_V233_DESKTOP_MOBILE=PASS
P01_V233_ANONYMOUS_BOUNDARY=PASS
P01_V233_SCHEMA_UNCHANGED_2026082901=PASS
P01_V233_VERSION_UNCHANGED_2.32.0=PASS
OWNER_PRODUCTION_WRITE=NO
RELEASE=NO
EOF
cat "$EVID/verdict.txt"
