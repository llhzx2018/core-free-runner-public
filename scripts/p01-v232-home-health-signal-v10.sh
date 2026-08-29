#!/usr/bin/env bash
set -Eeuo pipefail
PRODUCT=${PRODUCT:?}; ROOT=${ROOT:?}; PORT=${PORT:?}; ADMIN_PASS=${ADMIN_PASS:?}; EVID=${EVID:?}; SOURCE=${SOURCE:?}; SOURCE_TREE=${SOURCE_TREE:?}; DEVELOP_SOURCE=${DEVELOP_SOURCE:?}
mkdir -p "$EVID"
COOKIE=/tmp/p01-v232-health-v10.cookies
PIDFILE=/tmp/p01-v232-health-v10.pid
cleanup(){ rm -f "$ROOT/__p01_v232_health_seed.php" "$ROOT/__p01_v232_health_state.php"; if test -f "$PIDFILE"; then kill "$(cat "$PIDFILE")" >/dev/null 2>&1 || true; fi; }
trap cleanup EXIT

# 1. Exact source / two-file delta / syntax / version.
test "$(git -C "$PRODUCT" rev-parse HEAD)" = "$SOURCE"
test "$(git -C "$PRODUCT" rev-parse HEAD^{tree})" = "$SOURCE_TREE"
test "$(tr -d '\r\n' < "$PRODUCT/VERSION")" = 2.31.0
test "$(tr -d '\r\n' < "$ROOT/VERSION.txt")" = 2.31.0
git -C "$PRODUCT" diff --name-only "$DEVELOP_SOURCE"...HEAD | sort >"$EVID/actual-diff.txt"
printf '%s\n' src/app/FunctionalHome.php src/assets/workspace-home.css | sort >"$EVID/expected-diff.txt"
diff -u "$EVID/expected-diff.txt" "$EVID/actual-diff.txt"
php -l "$ROOT/app/FunctionalHome.php" >/dev/null
git -C "$PRODUCT" diff --check "$DEVELOP_SOURCE"...HEAD
printf '%s\n' P01_V232_HOME_HEALTH_SOURCE_FENCE=PASS P01_V232_HOME_HEALTH_TWO_FILE_DELTA=PASS P01_V232_VERSION_UNCHANGED_2.31.0=PASS | tee "$EVID/source.txt"

# 2. Fresh runtime.
rm -f "$COOKIE"
php -S "127.0.0.1:${PORT}" -t "$ROOT" >"$EVID/server.log" 2>&1 & echo $! >"$PIDFILE"
for i in $(seq 1 50); do if curl -fsS -c "$COOKIE" -b "$COOKIE" "http://127.0.0.1:${PORT}/setup.php" -o /tmp/p01-v232-health-setup.html; then break; fi; sleep .25; done
test -s /tmp/p01-v232-health-setup.html
CSRF=$(python3 - <<'PY'
import re
s=open('/tmp/p01-v232-health-setup.html',encoding='utf-8').read();m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsS -c "$COOKIE" -b "$COOKIE" -X POST "http://127.0.0.1:${PORT}/setup.php" --data-urlencode "setup_csrf=$CSRF" --data-urlencode 'site_title=P01 V232 Health Gate V10' --data-urlencode "admin_password=$ADMIN_PASS" --data-urlencode "admin_password_confirm=$ADMIN_PASS" -o "$EVID/setup-post.html"
test -f "$ROOT/app/.runtime.php"
php "$ROOT/cli/verify.php" | tee "$EVID/fresh-verify.txt" | grep -Fx VERIFY_PASS=YES
php -r 'require getenv("ROOT")."/app/bootstrap.php";$db=vf_db();$db->exec("DELETE FROM link_health");echo "SCHEMA=".(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status=\"success\"")->fetchColumn().PHP_EOL;echo "SQLITE=".strtolower((string)$db->query("PRAGMA integrity_check")->fetchColumn()).PHP_EOL;echo "FK=".count($db->query("PRAGMA foreign_key_check")->fetchAll(PDO::FETCH_ASSOC)).PHP_EOL;' | tee "$EVID/runtime.txt"
grep -Fx SCHEMA=2026082901 "$EVID/runtime.txt"; grep -Fx SQLITE=ok "$EVID/runtime.txt"; grep -Fx FK=0 "$EVID/runtime.txt"

# 3. Runner-only authenticated category seed and health state helper.
cat >"$ROOT/__p01_v232_health_seed.php" <<'PHP'
<?php
declare(strict_types=1);
require __DIR__ . '/app/bootstrap.php';
header('Content-Type: text/plain; charset=utf-8');header('Cache-Control: no-store');
if (!vf_is_admin()) { http_response_code(403); echo "FORBIDDEN\n"; exit; }
try { $id=(new VfRepository(vf_db()))->createCategory(['name'=>'V232 Health Gate 分类','description'=>'runner-only fixture','is_private'=>false,'sort_order'=>100]); echo "CATEGORY_ID=".(int)$id."\n"; }
finally { @unlink(__FILE__); }
PHP
cat >"$ROOT/__p01_v232_health_state.php" <<'PHP'
<?php
declare(strict_types=1);
require __DIR__ . '/app/bootstrap.php';
header('Content-Type: application/json; charset=utf-8');header('Cache-Control: no-store');
if (!vf_is_admin()) { http_response_code(403); echo json_encode(['ok'=>false]); exit; }
$id=max(0,(int)($_GET['id']??0));$state=(string)($_GET['state']??'');
if($id<=0){http_response_code(400);echo json_encode(['ok'=>false,'error'=>'id']);exit;}
$db=vf_db();$health=new VfLinkHealth($db);
if($state==='confirmed'){$health->confirmInvalid($id,true);}
elseif($state==='clear'){$stmt=$db->prepare('DELETE FROM link_health WHERE link_id=?');$stmt->execute([$id]);}
else{http_response_code(400);echo json_encode(['ok'=>false,'error'=>'state']);exit;}
echo json_encode(['ok'=>true,'status'=>$health->status()],JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);
PHP
php -l "$ROOT/__p01_v232_health_seed.php" >/dev/null
php -l "$ROOT/__p01_v232_health_state.php" >/dev/null

# 4. Browser: unchecked is quiet; confirmed is visible; clear returns quiet.
mkdir -p /tmp/p01-v232-health-browser && cd /tmp/p01-v232-health-browser
npm init -y >/dev/null 2>&1; npm install playwright@1.55.0 --no-save >/dev/null 2>&1; npx playwright install chromium --with-deps >/dev/null 2>&1
cat >gate.mjs <<'JS'
import{chromium}from'playwright';import fs from'fs';
const base='http://127.0.0.1:18642',pass='P01V232!HomeGate',e='/tmp/p01-v232-health-evidence';
const browser=await chromium.launch({headless:true});
const c=await browser.newContext({viewport:{width:1440,height:960}});
const login=await c.request.post(base+'/api.php?action=login',{data:{password:pass}});if(!login.ok())throw new Error('login '+login.status());
const seed=await c.request.get(base+'/__p01_v232_health_seed.php');const seedText=(await seed.text()).trim();if(seed.status()!==200||!/^CATEGORY_ID=\d+$/.test(seedText))throw new Error('seed '+seed.status()+' '+seedText);const cat=seedText.split('=')[1];
const p=await c.newPage();await p.goto(base+'/home.php',{waitUntil:'networkidle'});
const post=async fields=>await p.evaluate(async fields=>{const state=JSON.parse(document.getElementById('vf-workspace-data')?.textContent||'{}');const fd=new FormData();fd.set('csrf',state.csrf||'');for(const[k,v]of Object.entries(fields))fd.set(k,String(v));const r=await fetch('workspace-create.php',{method:'POST',body:fd,credentials:'same-origin',headers:{'X-Requested-With':'XMLHttpRequest'}});const j=await r.json();if(!r.ok||!j.ok)throw new Error(j.error||String(r.status));return j;},fields);
const created=await post({category_id:cat,title:'V232 Health Signal Target',url:'https://v232-health-signal.example.com',surface:'start',resource_kind:'Health Gate',description:'runner-only health target',tags:'v232-health',is_private:'1',is_favorite:'0',source_kind:'remote_url'});const id=Number(created.id||0);if(!id)throw new Error('created id');
const status=async()=>{const r=await c.request.get(base+'/api.php?action=link_health_status');if(!r.ok())throw new Error('health status '+r.status());return await r.json()};
await p.goto(base+'/home.php',{waitUntil:'networkidle'});let s=await status();if(Number(s.status?.problems||0)!==0)throw new Error('initial problems '+JSON.stringify(s.status));if(Number(s.status?.unchecked||0)<1)throw new Error('initial unchecked '+JSON.stringify(s.status));if(await p.locator('.vf-home-health-section').count()!==0)throw new Error('unchecked rendered as anomaly');await p.screenshot({path:e+'/home-health-zero.png',fullPage:true});
const mark=await c.request.get(base+'/__p01_v232_health_state.php?id='+id+'&state=confirmed');if(!mark.ok())throw new Error('confirm '+mark.status());s=await mark.json();if(Number(s.status?.problems||0)!==1||Number(s.status?.confirmed||0)!==1)throw new Error('confirmed authority '+JSON.stringify(s.status));
await p.reload({waitUntil:'networkidle'});const card=p.locator('.vf-home-health-section');if(await card.count()!==1)throw new Error('health card missing');const text=(await card.innerText()).trim();for(const x of ['有 1 个网址需要检查','确认失效','查看网址健康'])if(!text.includes(x))throw new Error('health copy missing '+x+' '+text);if(text.includes('未检查')||text.includes('已跳转'))throw new Error('non-problem leaked '+text);const href=await card.locator('.vf-home-health-link').getAttribute('href');if(href!=='health.php')throw new Error('health href '+href);await p.screenshot({path:e+'/home-health-problem.png',fullPage:true});
const m=await browser.newContext({viewport:{width:390,height:844},isMobile:true});const ml=await m.request.post(base+'/api.php?action=login',{data:{password:pass}});if(!ml.ok())throw new Error('mobile login');const mp=await m.newPage();await mp.goto(base+'/home.php',{waitUntil:'networkidle'});if(await mp.locator('.vf-home-health-section:visible').count()!==1)throw new Error('mobile health missing');const overflow=await mp.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth);if(overflow>2)throw new Error('mobile overflow '+overflow);await mp.screenshot({path:e+'/home-health-mobile.png',fullPage:true});
const clear=await c.request.get(base+'/__p01_v232_health_state.php?id='+id+'&state=clear');if(!clear.ok())throw new Error('clear '+clear.status());s=await clear.json();if(Number(s.status?.problems||0)!==0||Number(s.status?.unchecked||0)<1)throw new Error('clear authority '+JSON.stringify(s.status));await p.reload({waitUntil:'networkidle'});if(await p.locator('.vf-home-health-section').count()!==0)throw new Error('zero problems still visible');
await browser.close();fs.writeFileSync(e+'/browser-verdict.txt','P01_V232_HOME_HEALTH_UNCHECKED_NOT_ANOMALY=PASS\nP01_V232_HOME_HEALTH_CANONICAL_PROBLEMS=PASS\nP01_V232_HOME_HEALTH_CONFIRMED_VISIBLE=PASS\nP01_V232_HOME_HEALTH_ZERO_HIDDEN=PASS\nP01_V232_HOME_HEALTH_EXISTING_ROUTE=PASS\nP01_V232_HOME_HEALTH_MOBILE=PASS\n');console.log('HOME_HEALTH_BROWSER_PASS');
JS
node gate.mjs | tee "$EVID/browser.txt" | grep -Fx HOME_HEALTH_BROWSER_PASS
cd /
rm -f "$ROOT/__p01_v232_health_state.php"
test ! -e "$ROOT/__p01_v232_health_seed.php"; test ! -e "$ROOT/__p01_v232_health_state.php"
php "$ROOT/cli/verify.php" | tee "$EVID/post-verify.txt" | grep -Fx VERIFY_PASS=YES
cat >"$EVID/verdict.txt" <<EOF
P01_V232_HOME_HEALTH_SOURCE=$SOURCE
P01_V232_HOME_HEALTH_TREE=$SOURCE_TREE
P01_V232_HOME_HEALTH_SIGNAL=PASS
P01_V232_HOME_HEALTH_TWO_FILE_DELTA=PASS
P01_V232_HOME_HEALTH_UNCHECKED_NOT_ANOMALY=PASS
P01_V232_HOME_HEALTH_CANONICAL_PROBLEMS=PASS
P01_V232_HOME_HEALTH_CONFIRMED_VISIBLE=PASS
P01_V232_HOME_HEALTH_ZERO_HIDDEN=PASS
P01_V232_HOME_HEALTH_EXISTING_ROUTE=PASS
P01_V232_HOME_HEALTH_MOBILE=PASS
P01_V232_SCHEMA_UNCHANGED_2026082901=PASS
P01_V232_VERSION_UNCHANGED_2.31.0=PASS
OWNER_PRODUCTION_WRITE=NO
RELEASE=NO
EOF
cat "$EVID/verdict.txt"
