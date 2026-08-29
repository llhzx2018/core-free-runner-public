#!/usr/bin/env bash
set -Eeuo pipefail
PRODUCT=${PRODUCT:?}
ROOT=${ROOT:?}
PORT=${PORT:?}
ADMIN_PASS=${ADMIN_PASS:?}
EVID=${EVID:?}
SOURCE=${SOURCE:?}
SOURCE_TREE=${SOURCE_TREE:?}
BASE_SOURCE=${BASE_SOURCE:?}
mkdir -p "$EVID"
COOKIE=/tmp/p01-v232-home.cookies
PIDFILE=/tmp/p01-v232-home.pid
cleanup(){ if test -f "$PIDFILE"; then kill "$(cat "$PIDFILE")" >/dev/null 2>&1 || true; fi; }
trap cleanup EXIT
start_server(){
  cleanup
  php -S "127.0.0.1:${PORT}" -t "$ROOT" >"$EVID/server.log" 2>&1 & echo $! >"$PIDFILE"
  for i in $(seq 1 50); do curl -fsS "http://127.0.0.1:${PORT}/setup.php" -o /dev/null && return 0 || sleep .25; done
  echo SERVER_START_FAILED; return 1
}

# 1. Exact source / delta / syntax fence.
test "$(git -C "$PRODUCT" rev-parse HEAD)" = "$SOURCE"
test "$(git -C "$PRODUCT" rev-parse HEAD^{tree})" = "$SOURCE_TREE"
test "$(tr -d '\r\n' < "$PRODUCT/VERSION")" = "2.31.0"
test "$(tr -d '\r\n' < "$ROOT/VERSION.txt")" = "2.31.0"
git -C "$PRODUCT" diff --name-only "$BASE_SOURCE"...HEAD | sort >"$EVID/actual-diff.txt"
cat >"$EVID/expected-diff.txt" <<'EOF'
src/app/FunctionalHome.php
src/app/FunctionalWorkspaceShell.php
src/assets/workspace-home.css
src/home.php
EOF
diff -u "$EVID/expected-diff.txt" "$EVID/actual-diff.txt"
php -l "$ROOT/home.php" >/dev/null
php -l "$ROOT/app/FunctionalHome.php" >/dev/null
php -l "$ROOT/app/FunctionalWorkspaceShell.php" >/dev/null
grep -F "['home', '首页']" "$ROOT/app/FunctionalWorkspaceShell.php" >/dev/null
grep -F 'href="home.php" aria-label="VF Start 首页"' "$ROOT/app/FunctionalWorkspaceShell.php" >/dev/null
grep -F '.surface-home .vf-sidebar-scope-section{display:none!important}' "$ROOT/assets/workspace-home.css" >/dev/null
printf '%s\n' 'P01_V232_HOME_SOURCE_FENCE=PASS' 'P01_V232_FOUR_FILE_DELTA=PASS' 'P01_V232_VERSION_UNCHANGED_2.31.0=PASS' | tee "$EVID/source.txt"

# 2. Fresh isolated runtime.
start_server
curl -fsS -c "$COOKIE" -b "$COOKIE" "http://127.0.0.1:${PORT}/setup.php" -o /tmp/p01-v232-setup.html
CSRF=$(python3 - <<'PY'
import re
s=open('/tmp/p01-v232-setup.html',encoding='utf-8').read();m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsS -c "$COOKIE" -b "$COOKIE" -X POST "http://127.0.0.1:${PORT}/setup.php" \
  --data-urlencode "setup_csrf=$CSRF" \
  --data-urlencode 'site_title=P01 V232 Home Gate' \
  --data-urlencode "admin_password=$ADMIN_PASS" \
  --data-urlencode "admin_password_confirm=$ADMIN_PASS" >/dev/null
php "$ROOT/cli/verify.php" | tee "$EVID/fresh-verify.txt" | grep -Fx VERIFY_PASS=YES
php -r 'require getenv("ROOT")."/app/bootstrap.php";$db=vf_db();echo "SCHEMA=".(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status=\"success\"")->fetchColumn().PHP_EOL;echo "SQLITE=".strtolower((string)$db->query("PRAGMA integrity_check")->fetchColumn()).PHP_EOL;echo "FK=".count($db->query("PRAGMA foreign_key_check")->fetchAll(PDO::FETCH_ASSOC)).PHP_EOL;' | tee "$EVID/runtime.txt"
grep -Fx SCHEMA=2026082901 "$EVID/runtime.txt"
grep -Fx SQLITE=ok "$EVID/runtime.txt"
grep -Fx FK=0 "$EVID/runtime.txt"

# 3. Browser + real endpoint contract.
mkdir -p /tmp/p01-v232-browser && cd /tmp/p01-v232-browser
npm init -y >/dev/null 2>&1
npm install playwright@1.55.0 --no-save >/dev/null 2>&1
npx playwright install chromium --with-deps >/dev/null 2>&1
cat >gate.mjs <<'JS'
import{chromium}from'playwright';import fs from'fs';
const base='http://127.0.0.1:18642',pass='P01V232!HomeGate',e='/tmp/p01-v232-home-evidence';
const browser=await chromium.launch({headless:true});
const login=async(context)=>{const r=await context.request.post(base+'/api.php?action=login',{data:{password:pass}});if(!r.ok())throw new Error('login '+r.status())};
const d=await browser.newContext({viewport:{width:1440,height:960}});await login(d);const p=await d.newPage();
await p.goto(base+'/home.php',{waitUntil:'networkidle'});
if(!p.url().endsWith('/home.php'))throw new Error('home route '+p.url());
const nav=await p.locator('.vf-global-domain-nav a:visible').allTextContents();
const clean=nav.map(x=>x.trim());if(JSON.stringify(clean)!==JSON.stringify(['首页','导航','频道','影视','专题']))throw new Error('nav '+JSON.stringify(clean));
const homeLink=p.locator('.vf-global-domain-nav a').filter({hasText:'首页'});if(!(await homeLink.getAttribute('href'))?.endsWith('home.php'))throw new Error('home href');if(!(await homeLink.evaluate(el=>el.classList.contains('active'))))throw new Error('home active');
if(await p.locator('.vf-home-command').count()!==1)throw new Error('home command missing');
if(await p.locator('a[href="surfaces.php"]:visible').count()<1)throw new Error('all resources entry missing');
if(await p.locator('.vf-sidebar-scope-section:visible').count()!==0)throw new Error('home scope should be hidden');

// Home keeps the intentional cross-domain Add form.
await p.locator('[data-open-add]:visible').first().click();await p.locator('[data-panel="add"]:visible').waitFor();
const surfaceVisible=await p.locator('[data-add-form] select[name="surface"]').evaluate(el=>{const box=el.closest('label')||el;const s=getComputedStyle(box);return s.display!=='none'&&!box.hidden});if(!surfaceVisible)throw new Error('home surface selector hidden');
const payload=await p.locator('#vf-workspace-data').evaluate(n=>JSON.parse(n.textContent||'{}'));const cat=String(payload.categories?.[0]?.id||'');if(!cat)throw new Error('category missing');
await p.locator('[data-close-panel]:visible').first().click();
const post=async(fields)=>await p.evaluate(async(fields)=>{const state=JSON.parse(document.getElementById('vf-workspace-data')?.textContent||'{}');const fd=new FormData();fd.set('csrf',state.csrf||'');for(const[k,v]of Object.entries(fields))fd.set(k,String(v));const r=await fetch('workspace-create.php',{method:'POST',body:fd,credentials:'same-origin',headers:{'X-Requested-With':'XMLHttpRequest'}});const j=await r.json();if(!r.ok||!j.ok)throw new Error(j.error||String(r.status));return j;},fields);
const common=(title,url,surface)=>({category_id:cat,title,url,surface,resource_kind:'Home Gate',description:'home gate',tags:'v232',is_private:'1',is_favorite:'0',source_kind:'remote_url'});
const a=await post({...common('V232 Home Navigation','https://v232-home-nav.example.com','start'),is_favorite:'1'});
await post(common('V232 Home Channel','https://v232-home-channel.example.com','channels'));
await post({...common('V232 Home Watch','https://v232-home-watch.example.com','watch'),media_year:'2026',media_status:'watching'});
await post(common('V232 Home Topic','https://v232-home-topic.example.com','topics'));
fs.writeFileSync('/tmp/p01-v232-created-id.txt',String(a.id));
await p.screenshot({path:e+'/home-desktop-before-reload.png',fullPage:true});
await browser.close();
JS
node gate.mjs | tee "$EVID/browser-seed.txt"
cd /

# Give one seeded asset real usage truth through the canonical links counter.
CREATED_ID=$(cat /tmp/p01-v232-created-id.txt)
php -r 'require getenv("ROOT")."/app/bootstrap.php";$id=(int)getenv("CREATED_ID");$s=vf_db()->prepare("UPDATE links SET click_count=5 WHERE id=?");$s->execute([$id]);if($s->rowCount()!==1)exit(2);echo "RECENT_SEED_PASS\n";' | tee "$EVID/recent-seed.txt" | grep -Fx RECENT_SEED_PASS

# 4. Browser truth after seeded data, including mobile and anonymous boundary.
cd /tmp/p01-v232-browser
cat >verify.mjs <<'JS'
import{chromium}from'playwright';import fs from'fs';
const base='http://127.0.0.1:18642',pass='P01V232!HomeGate',e='/tmp/p01-v232-home-evidence';
const browser=await chromium.launch({headless:true});
const login=async(context)=>{const r=await context.request.post(base+'/api.php?action=login',{data:{password:pass}});if(!r.ok())throw new Error('login '+r.status())};
const d=await browser.newContext({viewport:{width:1440,height:960}});await login(d);const p=await d.newPage();await p.goto(base+'/home.php',{waitUntil:'networkidle'});
const text=await p.locator('.vf-home-command').innerText();for(const x of ['待整理','最近使用','我的收藏','全部资源','导航','频道','影视','专题'])if(!text.includes(x))throw new Error('missing '+x);
if(!text.includes('V232 Home Navigation'))throw new Error('recent seeded resource missing');
const domainRows=await p.locator('.vf-home-domain-list a').allTextContents();for(const row of domainRows){const m=row.match(/(\d+)\s*$/);if(!m||Number(m[1])<1)throw new Error('domain count '+row)}
const totalCard=p.locator('.vf-home-status-grid a').filter({hasText:'全部资源'});const totalText=await totalCard.innerText();const tm=totalText.match(/\b(\d+)\b/);if(!tm||Number(tm[1])<4)throw new Error('total '+totalText);
const favoriteCard=p.locator('.vf-home-status-grid a').filter({hasText:'我的收藏'});if(!/\b1\b/.test(await favoriteCard.innerText()))throw new Error('favorite count');
await p.screenshot({path:e+'/home-desktop.png',fullPage:true});
await p.getByRole('link',{name:'查看全部资源'}).click();await p.waitForLoadState('networkidle');if(!p.url().includes('/surfaces.php'))throw new Error('all route');if(!(await p.locator('h1').first().innerText()).includes('全部资源'))throw new Error('all title');if(await p.locator('.vf-global-domain-nav a.active').count()!==0)throw new Error('all should not impersonate a domain/home');
await p.goto(base+'/start.php',{waitUntil:'networkidle'});const startActive=await p.locator('.vf-global-domain-nav a.active').innerText();if(startActive.trim()!=='导航')throw new Error('start active '+startActive);if(!(await p.locator('.vf-global-domain-nav a').filter({hasText:'首页'}).getAttribute('href'))?.endsWith('home.php'))throw new Error('home link from start');await p.locator('[data-open-add]:visible').first().click();await p.locator('[data-panel="add"]:visible').waitFor();const hidden=await p.locator('[data-add-form] select[name="surface"]').evaluate(el=>{const box=el.closest('label')||el;return getComputedStyle(box).display==='none'||box.hidden});if(!hidden)throw new Error('specific domain surface selector should remain locked');

const m=await browser.newContext({viewport:{width:390,height:844},isMobile:true});await login(m);const mp=await m.newPage();await mp.goto(base+'/home.php',{waitUntil:'networkidle'});if(await mp.locator('.vf-home-mobile-command:visible').count()!==1)throw new Error('mobile command missing');const overflow=await mp.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth);if(overflow>2)throw new Error('mobile overflow '+overflow);await mp.screenshot({path:e+'/home-mobile.png',fullPage:true});

const anon=await browser.newContext();const r=await anon.request.get(base+'/home.php',{maxRedirects:0});if(r.status()!==302)throw new Error('anon home status '+r.status());const loc=r.headers()['location']||'';if(!loc.includes('index.php'))throw new Error('anon home location '+loc);const publicRoot=await anon.request.get(base+'/',{maxRedirects:0});if(publicRoot.status()!==200)throw new Error('public root '+publicRoot.status());const publicText=await publicRoot.text();if(publicText.includes('vf-home-command'))throw new Error('public home leak');
await browser.close();fs.writeFileSync(e+'/browser-verdict.txt','P01_V232_HOME_DESKTOP=PASS\nP01_V232_HOME_MOBILE=PASS\nP01_V232_HOME_RECENT_REAL_DATA=PASS\nP01_V232_HOME_ALL_RESOURCES_SEPARATION=PASS\nP01_V232_HOME_ADD_CROSS_DOMAIN=PASS\nP01_V232_DOMAIN_ADD_LOCK_REGRESSION=PASS\nP01_V232_ANONYMOUS_BOUNDARY=PASS\n');console.log('HOME_BROWSER_PASS');
JS
node verify.mjs | tee "$EVID/browser.txt" | grep -Fx HOME_BROWSER_PASS
cd /
php "$ROOT/cli/verify.php" | tee "$EVID/post-verify.txt" | grep -Fx VERIFY_PASS=YES
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
