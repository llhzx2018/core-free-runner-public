#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=${ROOT:?}; PORT=${PORT:?}; ADMIN_PASS=${ADMIN_PASS:?}; EVID=${EVID:?}
mkdir -p "$EVID"
COOKIE=/tmp/p01-v230-final.cookies
PIDFILE=/tmp/p01-v230-final.pid
cleanup(){ if test -f "$PIDFILE"; then kill "$(cat "$PIDFILE")" >/dev/null 2>&1 || true; fi; }
trap cleanup EXIT
start_server(){
  cleanup; php -S "127.0.0.1:${PORT}" -t "$ROOT" >"$EVID/server.log" 2>&1 & echo $! >"$PIDFILE"
  for i in $(seq 1 40); do curl -fsS "http://127.0.0.1:${PORT}/setup.php" -o /dev/null && return 0 || sleep .25; done
  echo SERVER_START_FAILED; return 1
}

# 1. Build an isolated immutable V2.29 Owner-like runtime.
rm -rf "$ROOT" "$COOKIE"; cp -a production/src "$ROOT"; start_server
curl -fsS -c "$COOKIE" -b "$COOKIE" "http://127.0.0.1:${PORT}/setup.php" -o /tmp/p01-v230-final-setup.html
CSRF=$(python3 - <<'PY'
import re
s=open('/tmp/p01-v230-final-setup.html',encoding='utf-8').read();m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsS -c "$COOKIE" -b "$COOKIE" -X POST "http://127.0.0.1:${PORT}/setup.php" --data-urlencode "setup_csrf=$CSRF" --data-urlencode 'site_title=P01 V230 Final Remote' --data-urlencode "admin_password=$ADMIN_PASS" --data-urlencode "admin_password_confirm=$ADMIN_PASS" >/dev/null
test "$(tr -d '\r\n' < "$ROOT/VERSION.txt")" = 2.29.0
php "$ROOT/cli/verify.php" | tee "$EVID/pre-verify.txt" | grep -Fx VERIFY_PASS=YES

# 2. Seed representative public/private data for all four resource domains.
cat >/tmp/p01-v230-final-seed.php <<'PHP'
<?php
declare(strict_types=1);
$root=getenv('ROOT');require $root.'/app/bootstrap.php';require_once $root.'/app/SurfaceRepository.php';
$r=new VfRepository(vf_db());$s=new VfSurfaceRepository(vf_db());
$pub=$r->createCategory(['name'=>'公开导航','description'=>'V230 public','is_private'=>false,'sort_order'=>100]);
$priv=$r->createCategory(['name'=>'私人导航','description'=>'V230 private','is_private'=>true,'sort_order'=>90]);
for($i=1;$i<=12;$i++)$r->saveLink(null,['category_id'=>$pub,'title'=>'公开导航资源 '.str_pad((string)$i,2,'0',STR_PAD_LEFT),'url'=>'https://public-nav-'.$i.'.example.com','description'=>'preserve','tags'=>'authority,公开','is_private'=>false,'is_favorite'=>$i===1],'manual');
for($i=1;$i<=3;$i++)$r->saveLink(null,['category_id'=>$priv,'title'=>'私人导航资源 '.str_pad((string)$i,2,'0',STR_PAD_LEFT),'url'=>'https://private-nav-'.$i.'.example.com','description'=>'private','tags'=>'authority,私人','is_private'=>true],'manual');
foreach([['channels','频道','公开频道','私人频道'],['watch','电影','公开影视','私人影视'],['topics','AI','公开专题','私人专题']] as $cfg){[$domain,$kind,$pt,$qt]=$cfg;for($i=1;$i<=3;$i++){$x=$r->saveLink(null,['category_id'=>$pub,'title'=>$pt.' '.$i,'url'=>'https://'.$domain.'-public-'.$i.'.example.com','description'=>'public domain','tags'=>'authority,公开','is_private'=>false],'manual');$p=['surface'=>$domain,'resource_kind'=>$kind,'note'=>'public-'.$domain.'-'.$i];if($domain==='channels')$p['background_friendly']=true;if($domain==='watch'){$p['media_year']=2020+$i;$p['media_status']='want';}if($domain==='topics'){$p['source_kind']='remote_url';$p['source_ref']='https://'.$domain.'-public-'.$i.'.example.com';}$s->upsertProfile((int)$x['id'],$p);}for($i=1;$i<=2;$i++){$x=$r->saveLink(null,['category_id'=>$priv,'title'=>$qt.' '.$i,'url'=>'https://'.$domain.'-private-'.$i.'.example.com','description'=>'private domain','tags'=>'authority,私人','is_private'=>true],'manual');$p=['surface'=>$domain,'resource_kind'=>$kind,'note'=>'private-'.$domain.'-'.$i];if($domain==='channels')$p['background_friendly']=true;if($domain==='watch'){$p['media_year']=2010+$i;$p['media_status']='favorite';}if($domain==='topics'){$p['source_kind']='remote_url';$p['source_ref']='https://'.$domain.'-private-'.$i.'.example.com';}$s->upsertProfile((int)$x['id'],$p);}}
$db=vf_db();$c=$s->counts(true);$b=['links'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active'")->fetchColumn(),'categories'=>(int)$db->query("SELECT COUNT(*) FROM categories WHERE lifecycle_state='active'")->fetchColumn(),'favorites'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active' AND is_favorite=1")->fetchColumn(),'profiles'=>(int)$db->query('SELECT COUNT(*) FROM resource_domain_profiles')->fetchColumn(),'schema'=>(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status='success'")->fetchColumn(),'surface_counts'=>$c];
if($b['links']!==30||$b['categories']!==2||$b['favorites']!==1||$b['profiles']!==15||$b['schema']!=='2026082901')throw new RuntimeException('seed '.json_encode($b));foreach(['start'=>15,'channels'=>5,'watch'=>5,'topics'=>5,'total'=>30] as $k=>$v)if((int)($c[$k]??-1)!==$v)throw new RuntimeException('surface '.$k);
file_put_contents('/tmp/p01-v230-final-before.json',json_encode($b,JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE));file_put_contents('/tmp/p01-v230-final-ids.json',json_encode(['pub'=>$pub,'priv'=>$priv]));echo "SEED_PASS\n";
PHP
php /tmp/p01-v230-final-seed.php | grep -Fx SEED_PASS
cp /tmp/p01-v230-final-before.json "$EVID/before.json"

# 3. Exercise the real online updater against formal core-updates + GitHub Release.
cat >/tmp/p01-v230-final-update.php <<'PHP'
<?php
declare(strict_types=1);
$root=getenv('ROOT');require $root.'/app/bootstrap.php';require_once $root.'/app/UpdateManager.php';
$m=new VfUpdateManager(vf_db(),['root'=>$root,'private_root'=>VF_PRIVATE_ROOT,'current_version'=>'2.29.0']);$c=$m->check(true);
if(($c['ok']??false)!==true||($c['current_version']??'')!=='2.29.0'||($c['latest_version']??'')!=='2.30.0'||($c['available']??false)!==true||($c['can_update']??false)!==true)throw new RuntimeException('check '.json_encode($c));$s=$c['requirements']['schema']??[];if(($s['current']??'')!=='2026082901'||($s['from']??'')!=='2026082901'||($s['target']??'')!=='2026082901'||($s['ok']??false)!==true)throw new RuntimeException('schema');
$p=$m->prepare();if(($p['ok']??false)!==true||($p['from_version']??'')!=='2.29.0'||($p['to_version']??'')!=='2.30.0'||($p['release_tag']??'')!=='v2.30.0'||($p['asset_name']??'')!=='VF_Start_V2.30.0_UPDATE.zip'||(int)($p['update_package_bytes']??0)!==1328072||($p['update_package_sha256']??'')!=='65869be49eb094d2be97609aa4fd588aeed737b97695882fc3b216eaf20edcb0')throw new RuntimeException('prepare '.json_encode($p));foreach(['manifest_identity','release_tag','release_asset','bytes','sha256','atomic_self_test','recovery_point'] as $k)if(($p['checks'][$k]??'')!=='pass')throw new RuntimeException('prepare '.$k);
$i=$m->install((string)$p['operation_id']);if(($i['ok']??false)!==true||($i['updated']??false)!==true||($i['from_version']??'')!=='2.29.0'||($i['to_version']??'')!=='2.30.0')throw new RuntimeException('install '.json_encode($i));foreach(['release_identity','atomic_handoff','activation','cleanup'] as $k)if(($i['checks'][$k]??'')!=='pass')throw new RuntimeException('install '.$k);file_put_contents(getenv('EVID').'/update.json',json_encode(['check'=>$c,'prepare'=>$p,'install'=>$i],JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES));echo "REMOTE_UPDATE_PASS\n";
PHP
php /tmp/p01-v230-final-update.php | grep -Fx REMOTE_UPDATE_PASS

# 4. Re-read data/schema/integrity and regenerate public SEO projection on upgraded code.
cat >/tmp/p01-v230-final-post.php <<'PHP'
<?php
declare(strict_types=1);
$root=getenv('ROOT');$before=json_decode((string)file_get_contents('/tmp/p01-v230-final-before.json'),true,512,JSON_THROW_ON_ERROR);require $root.'/app/bootstrap.php';require_once $root.'/app/SurfaceRepository.php';
$db=vf_db();$s=new VfSurfaceRepository($db);$a=['links'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active'")->fetchColumn(),'categories'=>(int)$db->query("SELECT COUNT(*) FROM categories WHERE lifecycle_state='active'")->fetchColumn(),'favorites'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active' AND is_favorite=1")->fetchColumn(),'profiles'=>(int)$db->query('SELECT COUNT(*) FROM resource_domain_profiles')->fetchColumn(),'schema'=>(string)$db->query("SELECT COALESCE(MAX(version),'') FROM schema_migrations WHERE status='success'")->fetchColumn(),'integrity'=>strtolower((string)$db->query('PRAGMA integrity_check')->fetchColumn()),'fk'=>count($db->query('PRAGMA foreign_key_check')->fetchAll(PDO::FETCH_ASSOC)),'surface_counts'=>$s->counts(true)];if($a['schema']!=='2026082901'||$a['integrity']!=='ok'||$a['fk']!==0)throw new RuntimeException('db');foreach(['links','categories','favorites','profiles'] as $k)if($a[$k]!==$before[$k])throw new RuntimeException('preserve '.$k);foreach($before['surface_counts'] as $k=>$v)if((int)($a['surface_counts'][$k]??-1)!==(int)$v)throw new RuntimeException('surface '.$k);
$ids=json_decode((string)file_get_contents('/tmp/p01-v230-final-ids.json'),true,512,JSON_THROW_ON_ERROR);$r=new VfRepository($db);$x=$r->saveLink(null,['category_id'=>(int)$ids['pub'],'title'=>'升级后新增专题','url'=>'https://post-v230-topic.example.com','description'=>'post','tags'=>'升级后','is_private'=>false],'manual');$s->upsertProfile((int)$x['id'],['surface'=>'topics','resource_kind'=>'AI','source_kind'=>'remote_url','source_ref'=>'https://post-v230-topic.example.com']);if((int)$s->collection('topics',true)['count']!==6)throw new RuntimeException('post write');vf_seo_rebuild($db,vf_config(),null,vf_seo_base_url(),VF_VERSION);file_put_contents(getenv('EVID').'/post.json',json_encode($a,JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE));echo "POST_PASS\n";
PHP
test "$(tr -d '\r\n' < "$ROOT/VERSION.txt")" = 2.30.0
grep -Fx "define('VF_VERSION', '2.30.0');" "$ROOT/app/bootstrap.php" >/dev/null
test -f "$ROOT/assets/workspace-domain-nav.css"
php "$ROOT/cli/verify.php" | tee "$EVID/post-verify.txt" | grep -Fx VERIFY_PASS=YES
php /tmp/p01-v230-final-post.php | grep -Fx POST_PASS

# 5. Validate anonymous HTTP according to real IA: Start=public directory; domains=public resource lists.
start_server
IDS=$(cat /tmp/p01-v230-final-ids.json); PUB=$(jq -r .pub <<<"$IDS"); PRIV=$(jq -r .priv <<<"$IDS")
fetch200(){ local url="$1" out="$2"; local code; code=$(curl -sS -o "$out" -w '%{http_code}' "$url"); test "$code" = 200 || { echo "HTTP_STATUS:$url:$code" | tee -a "$EVID/http.txt"; return 20; }; }
visible_not_private(){ local file="$1" pub="$2" priv="$3" label="$4"; grep -F "$pub" "$file" >/dev/null || { echo "MISSING_PUBLIC:$label:$pub" | tee -a "$EVID/http.txt"; return 21; }; if grep -F "$priv" "$file" >/dev/null; then echo "PRIVATE_LEAK:$label:$priv" | tee -a "$EVID/http.txt"; return 22; fi; echo "HTTP_BOUNDARY_PASS:$label" | tee -a "$EVID/http.txt"; }
fetch200 "http://127.0.0.1:${PORT}/start.php" "$EVID/start-anonymous.html"
visible_not_private "$EVID/start-anonymous.html" '公开导航' '私人导航' start-directory
fetch200 "http://127.0.0.1:${PORT}/category/${PUB}/" "$EVID/category-public.html"
visible_not_private "$EVID/category-public.html" '公开导航资源 01' '私人导航资源 01' start-public-category
PRIV_CODE=$(curl -sS -o "$EVID/category-private-response.html" -w '%{http_code}' "http://127.0.0.1:${PORT}/category/${PRIV}/")
test "$PRIV_CODE" = 404 || { echo "PRIVATE_CATEGORY_HTTP_STATUS:$PRIV_CODE" | tee -a "$EVID/http.txt"; exit 23; }
for domain in channels watch topics; do fetch200 "http://127.0.0.1:${PORT}/${domain}.php" "$EVID/${domain}-anonymous.html"; done
visible_not_private "$EVID/channels-anonymous.html" '公开频道 1' '私人频道 1' channels
visible_not_private "$EVID/watch-anonymous.html" '公开影视 1' '私人影视 1' watch
visible_not_private "$EVID/topics-anonymous.html" '公开专题 1' '私人专题 1' topics
echo P01_V230_FINAL_HTTP_PUBLIC_PRIVATE=PASS | tee -a "$EVID/http.txt"

# 6. Authenticated desktop/mobile V2.30 UX after the real remote upgrade.
mkdir -p /tmp/p01-v230-final-browser; cd /tmp/p01-v230-final-browser
npm init -y >/dev/null 2>&1; npm install playwright@1.55.0 --no-save >/dev/null 2>&1; npx playwright install chromium --with-deps >/dev/null 2>&1
cat >gate.mjs <<'JS'
import{chromium}from'playwright';import fs from'fs';
const base='http://127.0.0.1:18634',pass='P01V230!FinalRemote',e='/tmp/p01-v230-final-evidence';const b=await chromium.launch({headless:true});
const d=await b.newContext({viewport:{width:1440,height:960}});let r=await d.request.post(base+'/api.php?action=login',{data:{password:pass}});if(!r.ok())throw Error('desktop login');const p=await d.newPage();
for(const [path,pub,priv]of[['start.php','公开导航资源 01','私人导航资源 01'],['channels.php','公开频道 1','私人频道 1'],['watch.php','公开影视 1','私人影视 1'],['topics.php','公开专题 1','私人专题 1']]){await p.goto(base+'/'+path,{waitUntil:'networkidle'});const t=await p.locator('body').innerText();if(!t.includes(pub)||!t.includes(priv))throw Error(path+' admin data');if(await p.locator('.vf-global-domain-nav a').count()!=5)throw Error(path+' nav');if(await p.locator('.vf-global-domain-nav a.active').count()!=1)throw Error(path+' active');if(await p.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth)>1)throw Error(path+' overflow')}
await p.goto(base+'/start.php',{waitUntil:'networkidle'});if(await p.locator('.vf-asset-row').count()<15)throw Error('start density');await p.screenshot({path:e+'/desktop-start.png',fullPage:true});for(const x of['channels','watch','topics']){await p.goto(base+'/'+x+'.php',{waitUntil:'networkidle'});await p.screenshot({path:e+'/desktop-'+x+'.png',fullPage:true})}await d.close();
const m=await b.newContext({viewport:{width:390,height:844}});r=await m.request.post(base+'/api.php?action=login',{data:{password:pass}});if(!r.ok())throw Error('mobile login');const q=await m.newPage();await q.goto(base+'/start.php',{waitUntil:'networkidle'});await q.locator('.vf-mobile-command-row').waitFor({state:'visible'});const tr=q.locator('.vf-mobile-category-trigger');await tr.waitFor({state:'visible'});await tr.click();const o=q.locator('.vf-mobile-category-overlay');await o.waitFor({state:'visible'});await o.locator('input[type=search]').fill('私人导航');if(await o.locator('[data-category-picker-item]',{hasText:'私人导航'}).count()!=1)throw Error('picker');if(await q.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth)>1)throw Error('mobile start overflow');await q.screenshot({path:e+'/mobile-start.png',fullPage:true});for(const x of['channels.php','watch.php','topics.php']){await q.goto(base+'/'+x,{waitUntil:'networkidle'});if(await q.locator('.vf-global-domain-nav a').count()!=5)throw Error(x+' mobile nav');if(await q.locator('.vf-global-domain-nav a.active').count()!=1)throw Error(x+' mobile active');if(await q.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth)>1)throw Error(x+' mobile overflow')}await q.screenshot({path:e+'/mobile-topics.png',fullPage:true});await m.close();await b.close();fs.writeFileSync(e+'/browser.txt','P01_V230_FINAL_DESKTOP_MOBILE=PASS\n');
JS
node gate.mjs
grep -Fx P01_V230_FINAL_DESKTOP_MOBILE=PASS "$EVID/browser.txt"
echo P01_V229_TO_V230_REMOTE_ONLINE_UPDATE_FINAL_GATE=PASS
