#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=${ROOT:?}; PORT=${PORT:?}; ADMIN_PASS=${ADMIN_PASS:?}; EVID=${EVID:?}
mkdir -p "$EVID"
COOKIE=/tmp/p01-v2330-final.cookies
PIDFILE=/tmp/p01-v2330-final.pid
cleanup(){ if test -f "$PIDFILE"; then kill "$(cat "$PIDFILE")" >/dev/null 2>&1 || true; rm -f "$PIDFILE"; fi; }
trap cleanup EXIT
start_server(){
  cleanup
  php -S "127.0.0.1:${PORT}" -t "$ROOT" >"$EVID/server.log" 2>&1 & echo $! >"$PIDFILE"
  for i in $(seq 1 80); do curl -fsS "http://127.0.0.1:${PORT}/setup.php" -o /dev/null && return 0 || sleep .25; done
  echo SERVER_START_FAILED; return 1
}

# 1. Build isolated Owner-like V2.32 runtime and install it normally.
rm -rf "$ROOT" "$COOKIE"; cp -a production/src "$ROOT"; start_server
curl -fsS -c "$COOKIE" -b "$COOKIE" "http://127.0.0.1:${PORT}/setup.php" -o /tmp/p01-v2330-final-setup.html
CSRF=$(python3 - <<'PY'
import re
s=open('/tmp/p01-v2330-final-setup.html',encoding='utf-8').read();m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsS -c "$COOKIE" -b "$COOKIE" -X POST "http://127.0.0.1:${PORT}/setup.php" \
  --data-urlencode "setup_csrf=$CSRF" --data-urlencode 'site_title=P01 V2330 Final Remote' \
  --data-urlencode "admin_password=$ADMIN_PASS" --data-urlencode "admin_password_confirm=$ADMIN_PASS" >/dev/null
test "$(tr -d '\r\n' < "$ROOT/VERSION.txt")" = 2.32.0
grep -F "define('VF_VERSION', '2.32.0')" "$ROOT/app/bootstrap.php" >/dev/null
php "$ROOT/cli/verify.php" | tee "$EVID/pre-verify.txt" | grep -Fx VERIFY_PASS=YES

# 2. Seed representative public/private data across all resource domains.
cat >/tmp/p01-v2330-final-seed.php <<'PHP'
<?php
declare(strict_types=1);
$root=getenv('ROOT');require $root.'/app/bootstrap.php';require_once $root.'/app/SurfaceRepository.php';
$r=new VfRepository(vf_db());$s=new VfSurfaceRepository(vf_db());
$pub=$r->createCategory(['name'=>'V233公开导航','description'=>'remote-public','is_private'=>false,'sort_order'=>100]);
$priv=$r->createCategory(['name'=>'V233私人导航','description'=>'remote-private','is_private'=>true,'sort_order'=>90]);
for($i=1;$i<=8;$i++)$r->saveLink(null,['category_id'=>$pub,'title'=>'V233公开导航资源 '.$i,'url'=>'https://v233-public-nav-'.$i.'.example.com','description'=>'preserve','tags'=>'v233,公开','is_private'=>false,'is_favorite'=>$i===1],'manual');
for($i=1;$i<=2;$i++)$r->saveLink(null,['category_id'=>$priv,'title'=>'V233私人导航资源 '.$i,'url'=>'https://v233-private-nav-'.$i.'.example.com','description'=>'private','tags'=>'v233,私人','is_private'=>true],'manual');
foreach([['channels','频道','V233公开频道','V233私人频道'],['watch','电影','V233公开影视','V233私人影视'],['topics','AI','V233公开专题','V233私人专题']] as $cfg){
 [$domain,$kind,$pt,$qt]=$cfg;
 for($i=1;$i<=2;$i++){$x=$r->saveLink(null,['category_id'=>$pub,'title'=>$pt.' '.$i,'url'=>'https://v233-'.$domain.'-public-'.$i.'.example.com','description'=>'public domain','tags'=>'v233,公开','is_private'=>false,'is_favorite'=>$domain==='channels'&&$i===1],'manual');$p=['surface'=>$domain,'resource_kind'=>$kind,'note'=>'public-'.$domain.'-'.$i];if($domain==='channels')$p['background_friendly']=true;if($domain==='watch'){$p['media_year']=2024+$i;$p['media_status']='want';}if($domain==='topics'){$p['source_kind']='remote_url';$p['source_ref'=>'https://invalid.example'];}$s->upsertProfile((int)$x['id'],$p);}
 $x=$r->saveLink(null,['category_id'=>$priv,'title'=>$qt.' 1','url'=>'https://v233-'.$domain.'-private-1.example.com','description'=>'private domain','tags'=>'v233,私人','is_private'=>true],'manual');$p=['surface'=>$domain,'resource_kind'=>$kind,'note'=>'private-'.$domain];if($domain==='channels')$p['background_friendly']=true;if($domain==='watch'){$p['media_year']=2020;$p['media_status']='favorite';}if($domain==='topics'){$p['source_kind']='remote_url';$p['source_ref']='https://v233-'.$domain.'-private-1.example.com';}$s->upsertProfile((int)$x['id'],$p);
}
$db=vf_db();$c=$s->counts(true);$b=['links'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active'")->fetchColumn(),'categories'=>(int)$db->query("SELECT COUNT(*) FROM categories WHERE lifecycle_state='active'")->fetchColumn(),'favorites'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active' AND is_favorite=1")->fetchColumn(),'profiles'=>(int)$db->query('SELECT COUNT(*) FROM resource_domain_profiles')->fetchColumn(),'schema'=>(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status='success'")->fetchColumn(),'surface_counts'=>$c];
if($b['links']!==19||$b['categories']!==2||$b['favorites']!==2||$b['profiles']!==9||$b['schema']!=='2026082901')throw new RuntimeException('seed '.json_encode($b));
foreach(['start'=>10,'channels'=>3,'watch'=>3,'topics'=>3,'total'=>19] as $k=>$v)if((int)($c[$k]??-1)!==$v)throw new RuntimeException('surface '.$k.' '.json_encode($c));
file_put_contents('/tmp/p01-v2330-final-before.json',json_encode($b,JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE));echo "SEED_PASS\n";
PHP
# Fix a literal fixture typo before execution; this keeps the fixture readable above and fail-closed below.
python3 - <<'PY'
p='/tmp/p01-v2330-final-seed.php';s=open(p,encoding='utf-8').read();s=s.replace("$p['source_ref'=>'https://invalid.example'];","$p['source_ref']='https://v233-'.$domain.'-public-'.$i.'.example.com';");open(p,'w',encoding='utf-8').write(s)
PY
ROOT="$ROOT" php /tmp/p01-v2330-final-seed.php | grep -Fx SEED_PASS
cp /tmp/p01-v2330-final-before.json "$EVID/before.json"

# 3. Real online updater: published core-updates/main discovery + published V2.33 Release asset.
cat >/tmp/p01-v2330-final-update.php <<'PHP'
<?php
declare(strict_types=1);
$root=getenv('ROOT');require $root.'/app/bootstrap.php';require_once $root.'/app/UpdateManager.php';
$m=new VfUpdateManager(vf_db(),['root'=>$root,'private_root'=>VF_PRIVATE_ROOT,'current_version'=>'2.32.0']);
$c=$m->check(true);
if(($c['ok']??false)!==true||($c['current_version']??'')!=='2.32.0'||($c['latest_version']??'')!=='2.33.0'||($c['available']??false)!==true||($c['can_update']??false)!==true)throw new RuntimeException('check '.json_encode($c));
$s=$c['requirements']['schema']??[];if(($s['current']??'')!=='2026082901'||($s['from']??'')!=='2026082901'||($s['target']??'')!=='2026082901'||($s['ok']??false)!==true)throw new RuntimeException('schema '.json_encode($s));
$p=$m->prepare();
if(($p['ok']??false)!==true||($p['from_version']??'')!=='2.32.0'||($p['to_version']??'')!=='2.33.0'||($p['release_tag']??'')!=='v2.33.0'||($p['asset_name']??'')!=='VF_Start_V2.33.0_UPDATE.zip'||(int)($p['update_package_bytes']??0)!==1343451||($p['update_package_sha256']??'')!=='9520e7f45b37341456fe9f1dba1f248fe02e84143c52230760fcddb307226a9c')throw new RuntimeException('prepare '.json_encode($p));
foreach(['manifest_identity','release_tag','release_asset','bytes','sha256','atomic_self_test','recovery_point'] as $k)if(($p['checks'][$k]??'')!=='pass')throw new RuntimeException('prepare '.$k.' '.json_encode($p['checks']??[]));
$i=$m->install((string)$p['operation_id']);
if(($i['ok']??false)!==true||($i['updated']??false)!==true||($i['from_version']??'')!=='2.32.0'||($i['to_version']??'')!=='2.33.0')throw new RuntimeException('install '.json_encode($i));
foreach(['release_identity','atomic_handoff','activation','cleanup'] as $k)if(($i['checks'][$k]??'')!=='pass')throw new RuntimeException('install '.$k.' '.json_encode($i['checks']??[]));
file_put_contents(getenv('EVID').'/update.json',json_encode(['check'=>$c,'prepare'=>$p,'install'=>$i],JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES));echo "REMOTE_UPDATE_PASS\n";
PHP
ROOT="$ROOT" EVID="$EVID" php /tmp/p01-v2330-final-update.php | grep -Fx REMOTE_UPDATE_PASS

# 4. Post-upgrade version/schema/data/integrity.
test "$(tr -d '\r\n' < "$ROOT/VERSION.txt")" = 2.33.0
grep -F "define('VF_VERSION', '2.33.0')" "$ROOT/app/bootstrap.php" >/dev/null
php "$ROOT/cli/verify.php" | tee "$EVID/post-verify.txt" | grep -Fx VERIFY_PASS=YES
cat >/tmp/p01-v2330-final-post.php <<'PHP'
<?php
declare(strict_types=1);
$root=getenv('ROOT');$before=json_decode((string)file_get_contents('/tmp/p01-v2330-final-before.json'),true,512,JSON_THROW_ON_ERROR);require $root.'/app/bootstrap.php';require_once $root.'/app/SurfaceRepository.php';
$db=vf_db();$s=new VfSurfaceRepository($db);$a=['links'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active'")->fetchColumn(),'categories'=>(int)$db->query("SELECT COUNT(*) FROM categories WHERE lifecycle_state='active'")->fetchColumn(),'favorites'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active' AND is_favorite=1")->fetchColumn(),'profiles'=>(int)$db->query('SELECT COUNT(*) FROM resource_domain_profiles')->fetchColumn(),'schema'=>(string)$db->query("SELECT COALESCE(MAX(version),'') FROM schema_migrations WHERE status='success'")->fetchColumn(),'integrity'=>strtolower((string)$db->query('PRAGMA integrity_check')->fetchColumn()),'fk'=>count($db->query('PRAGMA foreign_key_check')->fetchAll(PDO::FETCH_ASSOC)),'surface_counts'=>$s->counts(true)];
if($a['schema']!=='2026082901'||$a['integrity']!=='ok'||$a['fk']!==0)throw new RuntimeException('db '.json_encode($a));foreach(['links','categories','favorites','profiles'] as $k)if($a[$k]!==$before[$k])throw new RuntimeException('preserve '.$k);foreach($before['surface_counts'] as $k=>$v)if((int)($a['surface_counts'][$k]??-1)!==(int)$v)throw new RuntimeException('surface '.$k);
file_put_contents(getenv('EVID').'/post.json',json_encode($a,JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE));echo "POST_PASS\n";
PHP
ROOT="$ROOT" EVID="$EVID" php /tmp/p01-v2330-final-post.php | grep -Fx POST_PASS

# 5. Anonymous public boundary after the real remote update.
start_server
fetch200(){ local url="$1" out="$2"; local code; code=$(curl -sSL -o "$out" -w '%{http_code}' "$url"); test "$code" = 200; }
visible_not_private(){ local file="$1" pub="$2" priv="$3"; grep -F "$pub" "$file" >/dev/null; ! grep -F "$priv" "$file" >/dev/null; }
fetch200 "http://127.0.0.1:${PORT}/" "$EVID/root-anonymous.html"; visible_not_private "$EVID/root-anonymous.html" 'V233公开导航' 'V233私人导航'
fetch200 "http://127.0.0.1:${PORT}/start.php" "$EVID/start-anonymous.html"; visible_not_private "$EVID/start-anonymous.html" 'V233公开导航' 'V233私人导航'
fetch200 "http://127.0.0.1:${PORT}/channels.php" "$EVID/channels-anonymous.html"; visible_not_private "$EVID/channels-anonymous.html" 'V233公开频道 1' 'V233私人频道 1'
fetch200 "http://127.0.0.1:${PORT}/watch.php" "$EVID/watch-anonymous.html"; visible_not_private "$EVID/watch-anonymous.html" 'V233公开影视 1' 'V233私人影视 1'
fetch200 "http://127.0.0.1:${PORT}/topics.php" "$EVID/topics-anonymous.html"; visible_not_private "$EVID/topics-anonymous.html" 'V233公开专题 1' 'V233私人专题 1'
echo P01_V2330_REMOTE_PUBLIC_PRIVATE_HTTP=PASS | tee "$EVID/http.txt"

# 6. Seed deterministic V2.33 health-triage fixture into the upgraded runtime.
cat >/tmp/p01-v2330-health-fixture.php <<'PHP'
<?php
declare(strict_types=1);
$root=getenv('ROOT');require $root.'/app/bootstrap.php';require_once $root.'/app/LinkHealth.php';
$r=new VfRepository(vf_db());$cat=$r->createCategory(['name'=>'V233 Health Triage Remote','description'=>'runner-only fixture','is_private'=>true,'sort_order'=>10]);
for($i=1;$i<=43;$i++)$r->saveLink(null,['category_id'=>$cat,'title'=>'V233 Health Restricted '.str_pad((string)$i,2,'0',STR_PAD_LEFT),'url'=>'https://restricted-'.$i.'.v233-health.example.com','is_private'=>true,'tags'=>'v233-health'],'manual');
for($i=1;$i<=5;$i++)$r->saveLink(null,['category_id'=>$cat,'title'=>'V233 Health Temporary '.str_pad((string)$i,2,'0',STR_PAD_LEFT),'url'=>'https://temporary-'.$i.'.v233-health.example.com','is_private'=>true,'tags'=>'v233-health'],'manual');
$r->saveLink(null,['category_id'=>$cat,'title'=>'V233 Health Suspected 01','url'=>'https://suspected-1.v233-health.example.com','is_private'=>true,'tags'=>'v233-health'],'manual');
$db=vf_db();$rows=$db->query("SELECT id,title FROM links WHERE lifecycle_state='active' AND title LIKE 'V233 Health %' ORDER BY id ASC")->fetchAll(PDO::FETCH_ASSOC);if(count($rows)!==49)throw new RuntimeException('health rows '.count($rows));$now=gmdate('c');
$stmt=$db->prepare("INSERT INTO link_health(link_id,status,http_status,final_url,redirect_count,response_ms,error_kind,last_error,last_success_at,last_checked_at,consecutive_failures,manual_confirmed,ignore_auto,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(link_id) DO UPDATE SET status=excluded.status,http_status=excluded.http_status,final_url=excluded.final_url,redirect_count=excluded.redirect_count,response_ms=excluded.response_ms,error_kind=excluded.error_kind,last_error=excluded.last_error,last_success_at=excluded.last_success_at,last_checked_at=excluded.last_checked_at,consecutive_failures=excluded.consecutive_failures,manual_confirmed=excluded.manual_confirmed,ignore_auto=excluded.ignore_auto,updated_at=excluded.updated_at");
$db->beginTransaction();try{foreach($rows as $row){$title=(string)$row['title'];$status='restricted';$http=403;$kind='http';$error='HTTP 403 / runner fixture';$fail=1;$ignore=0;if(str_contains($title,'Temporary')){$status='temporary';$http=0;$kind='timeout';$error='timeout / runner fixture';}elseif(str_contains($title,'Suspected')){$status='suspected';$http=404;$error='HTTP 404 / runner fixture';$fail=2;}elseif($title==='V233 Health Restricted 43'){$ignore=1;}$stmt->execute([(int)$row['id'],$status,$http,'',0,120,$kind,$error,'',$now,$fail,0,$ignore,$now]);}$db->commit();}catch(Throwable $e){if($db->inTransaction())$db->rollBack();throw $e;}
$status=(new VfLinkHealth($db))->status();foreach(['restricted'=>43,'restrictedReview'=>42,'temporary'=>5,'temporaryReview'=>5,'suspected'=>1,'suspectedReview'=>1,'ignored'=>1,'problems'=>49,'attention'=>1,'needsAction'=>6] as $k=>$v)if((int)($status[$k]??-1)!==$v)throw new RuntimeException($k.' '.json_encode($status));file_put_contents(getenv('EVID').'/health-status.json',json_encode($status,JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE));echo "HEALTH_FIXTURE_PASS\n";
PHP
ROOT="$ROOT" EVID="$EVID" php /tmp/p01-v2330-health-fixture.php | grep -Fx HEALTH_FIXTURE_PASS

# 7. Authenticated Desktop/Mobile V2.33 Home + Health Triage semantics on the remote-upgraded runtime.
mkdir -p /tmp/p01-v2330-final-browser; cd /tmp/p01-v2330-final-browser
npm init -y >/dev/null 2>&1
npm install playwright@1.55.0 --no-save >/dev/null 2>&1
npx playwright install chromium --with-deps >/dev/null 2>&1
cat >gate.mjs <<'JS'
import{chromium}from'playwright';import fs from'fs';
const base='http://127.0.0.1:18685',pass='P01V2330!FinalRemote',e='/tmp/p01-v2330-final-evidence';
const browser=await chromium.launch({headless:true});
async function authed(viewport){const c=await browser.newContext({viewport});const r=await c.request.post(base+'/api.php?action=login',{data:{password:pass}});if(!r.ok())throw new Error('login '+r.status());return c;}
const c=await authed({width:1440,height:1000});const p=await c.newPage();
await p.goto(base+'/home.php',{waitUntil:'networkidle'});const home=p.locator('.vf-home-health-section');if(await home.count()!==1)throw new Error('home health missing');const ht=(await home.innerText()).trim();for(const x of ['有 6 个网址需要处理','疑似失效','暂时异常','访问受限（人工确认）','42','进入网址健康治理'])if(!ht.includes(x))throw new Error('home missing '+x+'\n'+ht);if(ht.includes('49 个网址需要处理')||ht.includes('48 个网址需要处理'))throw new Error('raw problems leaked '+ht);await p.screenshot({path:e+'/home-health-triage-desktop.png',fullPage:true});
await p.goto(base+'/health.php',{waitUntil:'networkidle'});await p.waitForFunction(()=>document.querySelector('#summary')?.textContent.includes('访问受限（需人工确认）'));const summary=(await p.locator('#summary').innerText()).trim();for(const x of ['1\n疑似失效','5\n暂时异常','42\n访问受限（需人工确认）','1\n已忽略自动'])if(!summary.includes(x))throw new Error('summary missing '+x+'\n'+summary);
await p.selectOption('#status','restricted');await p.waitForFunction(()=>{const rows=[...document.querySelectorAll('#list tbody tr')];const text=document.querySelector('#list')?.textContent||'';return document.querySelector('#status')?.value==='restricted'&&rows.length>0&&rows.every(row=>row.textContent.includes('访问受限'))&&!text.includes('V233 Health Suspected');});const first=p.locator('#list tbody tr').first();const rowText=(await first.innerText()).trim();if(!rowText.includes('不要直接判定失效'))throw new Error('restricted guidance');const open=first.locator('a',{hasText:'打开网址'});if(await open.count()!==1||await open.getAttribute('target')!=='_blank')throw new Error('open action');const rel=String(await open.getAttribute('rel')||'');if(!rel.includes('noopener')||!rel.includes('noreferrer'))throw new Error('open rel');for(const action of ['retry','history','ignore','confirm','pending','trash'])if(await first.locator('[data-action="'+action+'"]').count()!==1)throw new Error('legacy '+action);
const ignore=first.locator('[data-action="ignore"]');const firstId=Number(await ignore.getAttribute('data-id'));const csrf=await p.locator('meta[name="csrf-token"]').getAttribute('content');const ir=await c.request.post(base+'/api.php?action=link_health_ignore',{data:{id:firstId,ignore:true},headers:{'X-CSRF-Token':String(csrf||'')}});if(!ir.ok())throw new Error('ignore '+ir.status());await p.reload({waitUntil:'networkidle'});let st=await(await c.request.get(base+'/api.php?action=link_health_status')).json();if(Number(st.status?.needsAction)!==6||Number(st.status?.restrictedReview)!==41||Number(st.status?.ignored)!==2)throw new Error('ignore authority '+JSON.stringify(st.status));
await p.selectOption('#status','restricted');await p.waitForFunction(()=>document.querySelectorAll('#list tbody tr').length>0);const restore=p.locator('#list tbody tr').filter({has:p.locator('[data-id="'+firstId+'"]')}).first().locator('[data-action="ignore"]');if(!String(await restore.textContent()).includes('恢复自动检查'))throw new Error('restore copy');const rr=await c.request.post(base+'/api.php?action=link_health_ignore',{data:{id:firstId,ignore:false},headers:{'X-CSRF-Token':String(csrf||'')}});if(!rr.ok())throw new Error('restore '+rr.status());await p.reload({waitUntil:'networkidle'});st=await(await c.request.get(base+'/api.php?action=link_health_status')).json();if(Number(st.status?.restrictedReview)!==42||Number(st.status?.ignored)!==1)throw new Error('restore authority '+JSON.stringify(st.status));await p.screenshot({path:e+'/health-triage-desktop.png',fullPage:true});
const m=await authed({width:390,height:844});const mp=await m.newPage();await mp.goto(base+'/home.php',{waitUntil:'networkidle'});if(!(await mp.locator('.vf-home-health-section').innerText()).includes('有 6 个网址需要处理'))throw new Error('mobile home triage');let overflow=await mp.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth);if(overflow>2)throw new Error('mobile home overflow '+overflow);await mp.screenshot({path:e+'/home-health-triage-mobile.png',fullPage:true});await mp.goto(base+'/health.php',{waitUntil:'networkidle'});await mp.waitForFunction(()=>document.querySelector('#summary')?.textContent.includes('访问受限（需人工确认）'));overflow=await mp.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth);if(overflow>2)throw new Error('mobile health overflow '+overflow);await mp.screenshot({path:e+'/health-triage-mobile.png',fullPage:true});
const anon=await browser.newContext({viewport:{width:1280,height:800}});const ap=await anon.newPage();const ar=await ap.goto(base+'/',{waitUntil:'networkidle'});if(!ar||ar.status()!==200)throw new Error('anon root');const at=await ap.locator('body').innerText();if(at.includes('V233 Health Restricted')||at.includes('V233 Health Temporary')||at.includes('V233 Health Suspected'))throw new Error('private health leak');
await anon.close();await m.close();await c.close();await browser.close();fs.writeFileSync(e+'/browser-verdict.txt','P01_V2330_REMOTE_HOME_NEEDS_ACTION_6=PASS\nP01_V2330_REMOTE_RESTRICTED_REVIEW_42=PASS\nP01_V2330_REMOTE_RESTRICTED_NOT_INVALID=PASS\nP01_V2330_REMOTE_OPEN_URL_ACTION=PASS\nP01_V2330_REMOTE_IGNORE_RESTORE_AUTHORITY=PASS\nP01_V2330_REMOTE_LEGACY_HEALTH_ACTIONS=PASS\nP01_V2330_REMOTE_DESKTOP_MOBILE=PASS\nP01_V2330_REMOTE_ANONYMOUS_BOUNDARY=PASS\n');console.log('V233_REMOTE_BROWSER_PASS');
JS
node gate.mjs | tee "$EVID/browser.txt" | grep -Fx V233_REMOTE_BROWSER_PASS
cat "$EVID/browser-verdict.txt"

cat >"$EVID/runtime-verdict.txt" <<EOF
P01_V2320_TO_V2330_REMOTE_ONLINE_UPDATE=PASS
P01_V2330_REMOTE_SCHEMA=2026082901
P01_V2330_REMOTE_DATA_PRESERVATION=PASS
P01_V2330_REMOTE_SQLITE_INTEGRITY=PASS
P01_V2330_REMOTE_PUBLIC_PRIVATE_BOUNDARY=PASS
P01_V2330_REMOTE_HEALTH_TRIAGE=PASS
P01_V2330_REMOTE_HOME_DESKTOP_MOBILE=PASS
OWNER_PRODUCTION_WRITE=NO
EOF
cat "$EVID/runtime-verdict.txt"
