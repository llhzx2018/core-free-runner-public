#!/usr/bin/env bash
set -Eeuo pipefail
PRODUCT=${PRODUCT:?}; ROOT=${ROOT:?}; PORT=${PORT:?}; ADMIN_PASS=${ADMIN_PASS:?}; EVID=${EVID:?}; SOURCE=${SOURCE:?}; SOURCE_TREE=${SOURCE_TREE:?}; BASE_SOURCE=${BASE_SOURCE:?}
mkdir -p "$EVID"; PIDFILE=/tmp/p01-v232-home-v2.pid
cleanup(){ if test -f "$PIDFILE"; then kill "$(cat "$PIDFILE")" >/dev/null 2>&1 || true; fi; }; trap cleanup EXIT

# Exact source, intended delta and syntax.
test "$(git -C "$PRODUCT" rev-parse HEAD)" = "$SOURCE"
test "$(git -C "$PRODUCT" rev-parse HEAD^{tree})" = "$SOURCE_TREE"
test "$(tr -d '\r\n' < "$ROOT/VERSION.txt")" = 2.31.0
git -C "$PRODUCT" diff --name-only "$BASE_SOURCE"...HEAD | sort >"$EVID/actual-diff.txt"
printf '%s\n' src/app/FunctionalHome.php src/app/FunctionalWorkspaceShell.php src/assets/workspace-home.css src/home.php | sort >"$EVID/expected-diff.txt"
diff -u "$EVID/expected-diff.txt" "$EVID/actual-diff.txt"
php -l "$ROOT/home.php" >/dev/null; php -l "$ROOT/app/FunctionalHome.php" >/dev/null; php -l "$ROOT/app/FunctionalWorkspaceShell.php" >/dev/null
printf '%s\n' P01_V232_HOME_SOURCE_FENCE=PASS P01_V232_FOUR_FILE_DELTA=PASS P01_V232_VERSION_UNCHANGED_2.31.0=PASS | tee "$EVID/source.txt"

# Fresh isolated runtime.
php -S "127.0.0.1:${PORT}" -t "$ROOT" >"$EVID/server.log" 2>&1 & echo $! >"$PIDFILE"
for i in $(seq 1 50); do curl -fsS "http://127.0.0.1:${PORT}/setup.php" -o /tmp/p01-v232-v2-setup.html && break || sleep .25; done
CSRF=$(python3 - <<'PY'
import re
s=open('/tmp/p01-v232-v2-setup.html',encoding='utf-8').read();m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsS -X POST "http://127.0.0.1:${PORT}/setup.php" --data-urlencode "setup_csrf=$CSRF" --data-urlencode 'site_title=P01 V232 Home Gate V2' --data-urlencode "admin_password=$ADMIN_PASS" --data-urlencode "admin_password_confirm=$ADMIN_PASS" >/dev/null
php "$ROOT/cli/verify.php" | tee "$EVID/fresh-verify.txt" | grep -Fx VERIFY_PASS=YES
cat >/tmp/p01-v232-v2-seed.php <<'PHP'
<?php
declare(strict_types=1);$root=getenv('ROOT');require $root.'/app/bootstrap.php';$r=new VfRepository(vf_db());$id=$r->createCategory(['name'=>'V232 Home Gate 分类','description'=>'home gate','is_private'=>false,'sort_order'=>100]);if($id<=0)throw new RuntimeException('category');echo "CATEGORY_SEED_PASS\n";
PHP
php /tmp/p01-v232-v2-seed.php | tee "$EVID/category-seed.txt" | grep -Fx CATEGORY_SEED_PASS
php -r 'require getenv("ROOT")."/app/bootstrap.php";$db=vf_db();echo "SCHEMA=".(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status=\"success\"")->fetchColumn().PHP_EOL;echo "SQLITE=".strtolower((string)$db->query("PRAGMA integrity_check")->fetchColumn()).PHP_EOL;echo "FK=".count($db->query("PRAGMA foreign_key_check")->fetchAll(PDO::FETCH_ASSOC)).PHP_EOL;' | tee "$EVID/runtime.txt"
grep -Fx SCHEMA=2026082901 "$EVID/runtime.txt"; grep -Fx SQLITE=ok "$EVID/runtime.txt"; grep -Fx FK=0 "$EVID/runtime.txt"

# Real desktop/mobile browser gate.
mkdir -p /tmp/p01-v232-browser-v2 && cd /tmp/p01-v232-browser-v2
npm init -y >/dev/null 2>&1; npm install playwright@1.55.0 --no-save >/dev/null 2>&1; npx playwright install chromium --with-deps >/dev/null 2>&1
cat >gate.mjs <<'JS'
import{chromium}from'playwright';import fs from'fs';
const base='http://127.0.0.1:18642',pass='P01V232!HomeGate',e='/tmp/p01-v232-home-evidence';
const browser=await chromium.launch({headless:true});
const login=async c=>{const r=await c.request.post(base+'/api.php?action=login',{data:{password:pass}});if(!r.ok())throw new Error('login '+r.status())};
const d=await browser.newContext({viewport:{width:1440,height:960}});await login(d);const p=await d.newPage();
await p.goto(base+'/home.php',{waitUntil:'networkidle'});if(!p.url().endsWith('/home.php'))throw new Error('home route '+p.url());
const nav=(await p.locator('.vf-global-domain-nav a:visible').allTextContents()).map(x=>x.trim());if(JSON.stringify(nav)!==JSON.stringify(['首页','导航','频道','影视','专题']))throw new Error('nav '+JSON.stringify(nav));
const home=p.locator('.vf-global-domain-nav a').filter({hasText:'首页'});if(!(await home.getAttribute('href'))?.endsWith('home.php')||!(await home.evaluate(el=>el.classList.contains('active'))))throw new Error('home nav authority');
if(await p.locator('.vf-home-command').count()!==1)throw new Error('home command missing');if(await p.locator('.vf-sidebar-scope-section:visible').count()!==0)throw new Error('home scope visible');
await p.locator('[data-open-add]:visible').first().click();await p.locator('[data-panel="add"]:visible').waitFor();const surfaceVisible=await p.locator('[data-add-form] select[name="surface"]').evaluate(el=>{const box=el.closest('label')||el;return getComputedStyle(box).display!=='none'&&!box.hidden});if(!surfaceVisible)throw new Error('home surface selector hidden');
const payload=await p.locator('#vf-workspace-data').evaluate(n=>JSON.parse(n.textContent||'{}'));const cat=String(payload.categories?.[0]?.id||'');if(!cat)throw new Error('seed category unavailable');await p.locator('[data-close-panel]:visible').first().click();
const post=async fields=>await p.evaluate(async fields=>{const state=JSON.parse(document.getElementById('vf-workspace-data')?.textContent||'{}');const fd=new FormData();fd.set('csrf',state.csrf||'');for(const[k,v]of Object.entries(fields))fd.set(k,String(v));const r=await fetch('workspace-create.php',{method:'POST',body:fd,credentials:'same-origin',headers:{'X-Requested-With':'XMLHttpRequest'}});const j=await r.json();if(!r.ok||!j.ok)throw new Error(j.error||String(r.status));return j;},fields);
const common=(title,url,surface)=>({category_id:cat,title,url,surface,resource_kind:'Home Gate',description:'home gate',tags:'v232',is_private:'1',is_favorite:'0',source_kind:'remote_url'});
const a=await post({...common('V232 Home Navigation','https://v232-home-nav.example.com','start'),is_favorite:'1'});await post(common('V232 Home Channel','https://v232-home-channel.example.com','channels'));await post({...common('V232 Home Watch','https://v232-home-watch.example.com','watch'),media_year:'2026',media_status:'watching'});await post(common('V232 Home Topic','https://v232-home-topic.example.com','topics'));
const opened=await d.request.get(base+'/surface-open.php?id='+a.id,{maxRedirects:0});if(opened.status()!==302)throw new Error('tracked open '+opened.status());
await p.goto(base+'/home.php',{waitUntil:'networkidle'});const text=await p.locator('.vf-home-command').innerText();for(const x of ['待整理','最近使用','我的收藏','全部资源','导航','频道','影视','专题','V232 Home Navigation'])if(!text.includes(x))throw new Error('missing '+x);
for(const row of await p.locator('.vf-home-domain-list a').allTextContents()){const m=row.match(/(\d+)\s*$/);if(!m||Number(m[1])<1)throw new Error('domain count '+row)}
const total=await p.locator('.vf-home-status-grid a').filter({hasText:'全部资源'}).innerText();if(!/\b4\b/.test(total))throw new Error('total '+total);const fav=await p.locator('.vf-home-status-grid a').filter({hasText:'我的收藏'}).innerText();if(!/\b1\b/.test(fav))throw new Error('favorite '+fav);
await p.screenshot({path:e+'/home-desktop.png',fullPage:true});await p.getByRole('link',{name:'查看全部资源'}).click();await p.waitForLoadState('networkidle');if(!p.url().includes('/surfaces.php')||!(await p.locator('h1').first().innerText()).includes('全部资源'))throw new Error('all resources separation');if(await p.locator('.vf-global-domain-nav a.active').count()!==0)throw new Error('all impersonates home/domain');
await p.goto(base+'/start.php',{waitUntil:'networkidle'});if((await p.locator('.vf-global-domain-nav a.active').innerText()).trim()!=='导航')throw new Error('start active');if(!(await p.locator('.vf-global-domain-nav a').filter({hasText:'首页'}).getAttribute('href'))?.endsWith('home.php'))throw new Error('home link from domain');await p.locator('[data-open-add]:visible').first().click();await p.locator('[data-panel="add"]:visible').waitFor();const locked=await p.locator('[data-add-form] select[name="surface"]').evaluate(el=>{const box=el.closest('label')||el;return getComputedStyle(box).display==='none'||box.hidden});if(!locked)throw new Error('domain add not locked');
const m=await browser.newContext({viewport:{width:390,height:844},isMobile:true});await login(m);const mp=await m.newPage();await mp.goto(base+'/home.php',{waitUntil:'networkidle'});if(await mp.locator('.vf-home-mobile-command:visible').count()!==1)throw new Error('mobile command');const overflow=await mp.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth);if(overflow>2)throw new Error('overflow '+overflow);await mp.screenshot({path:e+'/home-mobile.png',fullPage:true});
const anon=await browser.newContext();const hr=await anon.request.get(base+'/home.php',{maxRedirects:0});if(hr.status()!==302||(hr.headers()['location']||'').indexOf('index.php')<0)throw new Error('anonymous home boundary');const pr=await anon.request.get(base+'/',{maxRedirects:0});if(pr.status()!==200||(await pr.text()).includes('vf-home-command'))throw new Error('public root regression');
await browser.close();fs.writeFileSync(e+'/browser-verdict.txt','P01_V232_HOME_DESKTOP=PASS\nP01_V232_HOME_MOBILE=PASS\nP01_V232_HOME_RECENT_REAL_DATA=PASS\nP01_V232_HOME_ALL_RESOURCES_SEPARATION=PASS\nP01_V232_HOME_ADD_CROSS_DOMAIN=PASS\nP01_V232_DOMAIN_ADD_LOCK_REGRESSION=PASS\nP01_V232_ANONYMOUS_BOUNDARY=PASS\n');console.log('HOME_BROWSER_PASS');
JS
node gate.mjs | tee "$EVID/browser.txt" | grep -Fx HOME_BROWSER_PASS
cd /; php "$ROOT/cli/verify.php" | tee "$EVID/post-verify.txt" | grep -Fx VERIFY_PASS=YES
cat >"$EVID/verdict.txt" <<EOF
P01_V232_HOME_SOURCE=$SOURCE
P01_V232_HOME_TREE=$SOURCE_TREE
P01_V232_HOME_COMMAND_CENTER=PASS
P01_V232_HOME_REAL_DATA_ONLY=PASS
P01_V232_HOME_ALL_RESOURCES_SEPARATION=PASS
P01_V232_HOME_ADD_CROSS_DOMAIN=PASS
P01_V232_DOMAIN_ADD_LOCK_REGRESSION=PASS
P01_V232_ANONYMOUS_PUBLIC_ROOT_UNCHANGED=PASS
P01_V232_DESKTOP_MOBILE=PASS
P01_V232_SCHEMA_UNCHANGED_2026082901=PASS
P01_V232_VERSION_UNCHANGED_2.31.0=PASS
OWNER_PRODUCTION_WRITE=NO
RELEASE=NO
EOF
cat "$EVID/verdict.txt"
