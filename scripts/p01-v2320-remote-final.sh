#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=${ROOT:?}; PORT=${PORT:?}; ADMIN_PASS=${ADMIN_PASS:?}; EVID=${EVID:?}
mkdir -p "$EVID"
COOKIE=/tmp/p01-v2320-final.cookies
PIDFILE=/tmp/p01-v2320-final.pid
cleanup(){ if test -f "$PIDFILE"; then kill "$(cat "$PIDFILE")" >/dev/null 2>&1 || true; rm -f "$PIDFILE"; fi; }
trap cleanup EXIT
start_server(){
  cleanup
  php -S "127.0.0.1:${PORT}" -t "$ROOT" >"$EVID/server.log" 2>&1 & echo $! >"$PIDFILE"
  for i in $(seq 1 80); do curl -fsS "http://127.0.0.1:${PORT}/setup.php" -o /dev/null && return 0 || sleep .25; done
  echo SERVER_START_FAILED; return 1
}

# 1. Build an isolated owner-like runtime from immutable V2.31.0.
rm -rf "$ROOT" "$COOKIE"; cp -a production/src "$ROOT"; start_server
curl -fsS -c "$COOKIE" -b "$COOKIE" "http://127.0.0.1:${PORT}/setup.php" -o /tmp/p01-v2320-final-setup.html
CSRF=$(python3 - <<'PY'
import re
s=open('/tmp/p01-v2320-final-setup.html',encoding='utf-8').read();m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsS -c "$COOKIE" -b "$COOKIE" -X POST "http://127.0.0.1:${PORT}/setup.php" \
  --data-urlencode "setup_csrf=$CSRF" --data-urlencode 'site_title=P01 V2320 Final Remote' \
  --data-urlencode "admin_password=$ADMIN_PASS" --data-urlencode "admin_password_confirm=$ADMIN_PASS" >/dev/null
test "$(tr -d '\r\n' < "$ROOT/VERSION.txt")" = 2.31.0
grep -F "define('VF_VERSION', '2.31.0')" "$ROOT/app/bootstrap.php" >/dev/null
php "$ROOT/cli/verify.php" | tee "$EVID/pre-verify.txt" | grep -Fx VERIFY_PASS=YES

# 2. Seed representative public/private data across all resource domains.
cat >/tmp/p01-v2320-final-seed.php <<'PHP'
<?php
declare(strict_types=1);
$root=getenv('ROOT');require $root.'/app/bootstrap.php';require_once $root.'/app/SurfaceRepository.php';
$r=new VfRepository(vf_db());$s=new VfSurfaceRepository(vf_db());
$pub=$r->createCategory(['name'=>'V232公开导航','description'=>'remote-public','is_private'=>false,'sort_order'=>100]);
$priv=$r->createCategory(['name'=>'V232私人导航','description'=>'remote-private','is_private'=>true,'sort_order'=>90]);
for($i=1;$i<=8;$i++)$r->saveLink(null,['category_id'=>$pub,'title'=>'V232公开导航资源 '.$i,'url'=>'https://v232-public-nav-'.$i.'.example.com','description'=>'preserve','tags'=>'v232,公开','is_private'=>false,'is_favorite'=>$i===1],'manual');
for($i=1;$i<=2;$i++)$r->saveLink(null,['category_id'=>$priv,'title'=>'V232私人导航资源 '.$i,'url'=>'https://v232-private-nav-'.$i.'.example.com','description'=>'private','tags'=>'v232,私人','is_private'=>true],'manual');
foreach([['channels','频道','V232公开频道','V232私人频道'],['watch','电影','V232公开影视','V232私人影视'],['topics','AI','V232公开专题','V232私人专题']] as $cfg){
 [$domain,$kind,$pt,$qt]=$cfg;
 for($i=1;$i<=2;$i++){$x=$r->saveLink(null,['category_id'=>$pub,'title'=>$pt.' '.$i,'url'=>'https://v232-'.$domain.'-public-'.$i.'.example.com','description'=>'public domain','tags'=>'v232,公开','is_private'=>false,'is_favorite'=>$domain==='channels'&&$i===1],'manual');$p=['surface'=>$domain,'resource_kind'=>$kind,'note'=>'public-'.$domain.'-'.$i];if($domain==='channels')$p['background_friendly']=true;if($domain==='watch'){$p['media_year']=2024+$i;$p['media_status']='want';}if($domain==='topics'){$p['source_kind']='remote_url';$p['source_ref']='https://v232-'.$domain.'-public-'.$i.'.example.com';}$s->upsertProfile((int)$x['id'],$p);}
 $x=$r->saveLink(null,['category_id'=>$priv,'title'=>$qt.' 1','url'=>'https://v232-'.$domain.'-private-1.example.com','description'=>'private domain','tags'=>'v232,私人','is_private'=>true],'manual');$p=['surface'=>$domain,'resource_kind'=>$kind,'note'=>'private-'.$domain];if($domain==='channels')$p['background_friendly']=true;if($domain==='watch'){$p['media_year']=2020;$p['media_status']='favorite';}if($domain==='topics'){$p['source_kind']='remote_url';$p['source_ref']='https://v232-'.$domain.'-private-1.example.com';}$s->upsertProfile((int)$x['id'],$p);
}
$db=vf_db();$c=$s->counts(true);$b=['links'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active'")->fetchColumn(),'categories'=>(int)$db->query("SELECT COUNT(*) FROM categories WHERE lifecycle_state='active'")->fetchColumn(),'favorites'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active' AND is_favorite=1")->fetchColumn(),'profiles'=>(int)$db->query('SELECT COUNT(*) FROM resource_domain_profiles')->fetchColumn(),'schema'=>(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status='success'")->fetchColumn(),'surface_counts'=>$c];
if($b['links']!==19||$b['categories']!==2||$b['favorites']!==2||$b['profiles']!==9||$b['schema']!=='2026082901')throw new RuntimeException('seed '.json_encode($b));
foreach(['start'=>10,'channels'=>3,'watch'=>3,'topics'=>3,'total'=>19] as $k=>$v)if((int)($c[$k]??-1)!==$v)throw new RuntimeException('surface '.$k.' '.json_encode($c));
file_put_contents('/tmp/p01-v2320-final-before.json',json_encode($b,JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE));echo "SEED_PASS\n";
PHP
ROOT="$ROOT" php /tmp/p01-v2320-final-seed.php | grep -Fx SEED_PASS
cp /tmp/p01-v2320-final-before.json "$EVID/before.json"

# 3. Real online updater: public core-updates/main discovery + published GitHub Release asset.
cat >/tmp/p01-v2320-final-update.php <<'PHP'
<?php
declare(strict_types=1);
$root=getenv('ROOT');require $root.'/app/bootstrap.php';require_once $root.'/app/UpdateManager.php';
$m=new VfUpdateManager(vf_db(),['root'=>$root,'private_root'=>VF_PRIVATE_ROOT,'current_version'=>'2.31.0']);
$c=$m->check(true);
if(($c['ok']??false)!==true||($c['current_version']??'')!=='2.31.0'||($c['latest_version']??'')!=='2.32.0'||($c['available']??false)!==true||($c['can_update']??false)!==true)throw new RuntimeException('check '.json_encode($c));
$s=$c['requirements']['schema']??[];if(($s['current']??'')!=='2026082901'||($s['from']??'')!=='2026082901'||($s['target']??'')!=='2026082901'||($s['ok']??false)!==true)throw new RuntimeException('schema '.json_encode($s));
$p=$m->prepare();
if(($p['ok']??false)!==true||($p['from_version']??'')!=='2.31.0'||($p['to_version']??'')!=='2.32.0'||($p['release_tag']??'')!=='v2.32.0'||($p['asset_name']??'')!=='VF_Start_V2.32.0_UPDATE.zip'||(int)($p['update_package_bytes']??0)!==1351066||($p['update_package_sha256']??'')!=='262efaf80564f7c5942c37e1ba797434da277a8344b92cd0a7783edb90f1725a')throw new RuntimeException('prepare '.json_encode($p));
foreach(['manifest_identity','release_tag','release_asset','bytes','sha256','atomic_self_test','recovery_point'] as $k)if(($p['checks'][$k]??'')!=='pass')throw new RuntimeException('prepare '.$k.' '.json_encode($p['checks']??[]));
$i=$m->install((string)$p['operation_id']);
if(($i['ok']??false)!==true||($i['updated']??false)!==true||($i['from_version']??'')!=='2.31.0'||($i['to_version']??'')!=='2.32.0')throw new RuntimeException('install '.json_encode($i));
foreach(['release_identity','atomic_handoff','activation','cleanup'] as $k)if(($i['checks'][$k]??'')!=='pass')throw new RuntimeException('install '.$k.' '.json_encode($i['checks']??[]));
file_put_contents(getenv('EVID').'/update.json',json_encode(['check'=>$c,'prepare'=>$p,'install'=>$i],JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES));echo "REMOTE_UPDATE_PASS\n";
PHP
ROOT="$ROOT" EVID="$EVID" php /tmp/p01-v2320-final-update.php | grep -Fx REMOTE_UPDATE_PASS

# 4. Post-upgrade version/schema/data/integrity.
test "$(tr -d '\r\n' < "$ROOT/VERSION.txt")" = 2.32.0
grep -F "define('VF_VERSION', '2.32.0')" "$ROOT/app/bootstrap.php" >/dev/null
test -f "$ROOT/home.php"
test -f "$ROOT/app/FunctionalHome.php"
test -f "$ROOT/assets/workspace-home.css"
php "$ROOT/cli/verify.php" | tee "$EVID/post-verify.txt" | grep -Fx VERIFY_PASS=YES
cat >/tmp/p01-v2320-final-post.php <<'PHP'
<?php
declare(strict_types=1);
$root=getenv('ROOT');$before=json_decode((string)file_get_contents('/tmp/p01-v2320-final-before.json'),true,512,JSON_THROW_ON_ERROR);require $root.'/app/bootstrap.php';require_once $root.'/app/SurfaceRepository.php';
$db=vf_db();$s=new VfSurfaceRepository($db);$a=['links'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active'")->fetchColumn(),'categories'=>(int)$db->query("SELECT COUNT(*) FROM categories WHERE lifecycle_state='active'")->fetchColumn(),'favorites'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active' AND is_favorite=1")->fetchColumn(),'profiles'=>(int)$db->query('SELECT COUNT(*) FROM resource_domain_profiles')->fetchColumn(),'schema'=>(string)$db->query("SELECT COALESCE(MAX(version),'') FROM schema_migrations WHERE status='success'")->fetchColumn(),'integrity'=>strtolower((string)$db->query('PRAGMA integrity_check')->fetchColumn()),'fk'=>count($db->query('PRAGMA foreign_key_check')->fetchAll(PDO::FETCH_ASSOC)),'surface_counts'=>$s->counts(true)];
if($a['schema']!=='2026082901'||$a['integrity']!=='ok'||$a['fk']!==0)throw new RuntimeException('db '.json_encode($a));foreach(['links','categories','favorites','profiles'] as $k)if($a[$k]!==$before[$k])throw new RuntimeException('preserve '.$k);foreach($before['surface_counts'] as $k=>$v)if((int)($a['surface_counts'][$k]??-1)!==(int)$v)throw new RuntimeException('surface '.$k);
file_put_contents(getenv('EVID').'/post.json',json_encode($a,JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE));echo "POST_PASS\n";
PHP
ROOT="$ROOT" EVID="$EVID" php /tmp/p01-v2320-final-post.php | grep -Fx POST_PASS

# 5. Anonymous public boundary after remote upgrade.
start_server
fetch200(){ local url="$1" out="$2"; local code; code=$(curl -sSL -o "$out" -w '%{http_code}' "$url"); test "$code" = 200 || { echo "HTTP_STATUS:$url:$code" | tee -a "$EVID/http.txt"; return 20; }; }
visible_not_private(){ local file="$1" pub="$2" priv="$3" label="$4"; grep -F "$pub" "$file" >/dev/null || { echo "MISSING_PUBLIC:$label:$pub" | tee -a "$EVID/http.txt"; return 21; }; if grep -F "$priv" "$file" >/dev/null; then echo "PRIVATE_LEAK:$label:$priv" | tee -a "$EVID/http.txt"; return 22; fi; echo "HTTP_BOUNDARY_PASS:$label" | tee -a "$EVID/http.txt"; }
fetch200 "http://127.0.0.1:${PORT}/" "$EVID/root-anonymous.html"; visible_not_private "$EVID/root-anonymous.html" 'V232公开导航' 'V232私人导航' root-public-navigator
fetch200 "http://127.0.0.1:${PORT}/start.php" "$EVID/start-anonymous.html"; visible_not_private "$EVID/start-anonymous.html" 'V232公开导航' 'V232私人导航' start
fetch200 "http://127.0.0.1:${PORT}/channels.php" "$EVID/channels-anonymous.html"; visible_not_private "$EVID/channels-anonymous.html" 'V232公开频道 1' 'V232私人频道 1' channels
fetch200 "http://127.0.0.1:${PORT}/watch.php" "$EVID/watch-anonymous.html"; visible_not_private "$EVID/watch-anonymous.html" 'V232公开影视 1' 'V232私人影视 1' watch
fetch200 "http://127.0.0.1:${PORT}/topics.php" "$EVID/topics-anonymous.html"; visible_not_private "$EVID/topics-anonymous.html" 'V232公开专题 1' 'V232私人专题 1' topics
echo P01_V2320_REMOTE_PUBLIC_PRIVATE_HTTP=PASS | tee -a "$EVID/http.txt"

# 6. Authenticated Home Command Center desktop/mobile after the real remote update.
mkdir -p /tmp/p01-v2320-final-browser; cd /tmp/p01-v2320-final-browser
npm init -y >/dev/null 2>&1
npm install playwright@1.55.0 --no-save >/dev/null 2>&1
npx playwright install chromium --with-deps >/dev/null 2>&1
cat >gate.mjs <<'JS'
import { chromium } from 'playwright';
import fs from 'fs';
const base='http://127.0.0.1:18655', pass='P01V2320!FinalRemote', evid='/tmp/p01-v2320-final-evidence';
const browser=await chromium.launch({headless:true});
async function authed(viewport){
  const context=await browser.newContext({viewport});
  const r=await context.request.post(base+'/api.php?action=login',{data:{password:pass}});
  if(!r.ok()) throw new Error('login '+r.status());
  return context;
}
async function assertHome(viewport,label){
  const c=await authed(viewport); const p=await c.newPage();
  const r=await p.goto(base+'/',{waitUntil:'networkidle'}); if(!r||!r.ok())throw new Error(label+' root '+(r?.status()));
  if(await p.locator('.vf-home-command').count()!==1)throw new Error(label+' missing home');
  if((await p.locator('.vf-home-command h1').innerText()).trim()!=='首页')throw new Error(label+' h1');
  const body=await p.locator('body').innerText();
  for(const text of ['待整理','最近使用','我的收藏','全部资源','从哪里继续','最近操作','V232公开导航资源 1'])if(!body.includes(text))throw new Error(label+' missing '+text);
  const overflow=await p.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth); if(overflow>1)throw new Error(label+' overflow '+overflow);
  if(label==='mobile' && !(await p.locator('.vf-home-mobile-command [data-open-add]').isVisible()))throw new Error('mobile add not visible');
  await p.screenshot({path:evid+'/home-'+label+'.png',fullPage:true});
  await p.goto(base+'/surfaces.php',{waitUntil:'networkidle'});
  if(await p.locator('.vf-home-command').count()!==0)throw new Error(label+' all resources collapsed into home');
  const allBody=await p.locator('body').innerText();
  if(!allBody.includes('全部资源'))throw new Error(label+' all resources missing');
  if(!allBody.includes('V232私人导航资源 1'))throw new Error(label+' owner private missing in all resources');
  await c.close();
}
await assertHome({width:1440,height:1000},'desktop');
await assertHome({width:390,height:844},'mobile');
await browser.close();
fs.writeFileSync(evid+'/browser.txt','P01_V2320_REMOTE_HOME_DESKTOP=PASS\nP01_V2320_REMOTE_HOME_MOBILE=PASS\nP01_V2320_REMOTE_ALL_RESOURCES_SEPARATE=PASS\nP01_V2320_REMOTE_NO_HORIZONTAL_OVERFLOW=PASS\n');
JS
node gate.mjs
cat "$EVID/browser.txt"

cat >"$EVID/runtime-verdict.txt" <<EOF
P01_V2310_TO_V2320_REMOTE_ONLINE_UPDATE=PASS
P01_V2320_REMOTE_SCHEMA=2026082901
P01_V2320_REMOTE_DATA_PRESERVATION=PASS
P01_V2320_REMOTE_SQLITE_INTEGRITY=PASS
P01_V2320_REMOTE_PUBLIC_PRIVATE_BOUNDARY=PASS
P01_V2320_REMOTE_HOME_DESKTOP_MOBILE=PASS
P01_V2320_REMOTE_ALL_RESOURCES_SEPARATE=PASS
OWNER_PRODUCTION_WRITE=NO
EOF
cat "$EVID/runtime-verdict.txt"
