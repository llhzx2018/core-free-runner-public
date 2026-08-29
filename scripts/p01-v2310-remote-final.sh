#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=${ROOT:?}; PORT=${PORT:?}; ADMIN_PASS=${ADMIN_PASS:?}; EVID=${EVID:?}
mkdir -p "$EVID"
COOKIE=/tmp/p01-v2310-final.cookies
PIDFILE=/tmp/p01-v2310-final.pid
cleanup(){ if test -f "$PIDFILE"; then kill "$(cat "$PIDFILE")" >/dev/null 2>&1 || true; rm -f "$PIDFILE"; fi; }
trap cleanup EXIT
start_server(){
  cleanup
  php -S "127.0.0.1:${PORT}" -t "$ROOT" >"$EVID/server.log" 2>&1 & echo $! >"$PIDFILE"
  for i in $(seq 1 60); do curl -fsS "http://127.0.0.1:${PORT}/setup.php" -o /dev/null && return 0 || sleep .25; done
  echo SERVER_START_FAILED; return 1
}

# 1. Isolated immutable V2.30 owner-like runtime.
rm -rf "$ROOT" "$COOKIE"; cp -a production/src "$ROOT"; start_server
curl -fsS -c "$COOKIE" -b "$COOKIE" "http://127.0.0.1:${PORT}/setup.php" -o /tmp/p01-v2310-final-setup.html
CSRF=$(python3 - <<'PY'
import re
s=open('/tmp/p01-v2310-final-setup.html',encoding='utf-8').read();m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsS -c "$COOKIE" -b "$COOKIE" -X POST "http://127.0.0.1:${PORT}/setup.php" \
  --data-urlencode "setup_csrf=$CSRF" --data-urlencode 'site_title=P01 V2310 Final Remote' \
  --data-urlencode "admin_password=$ADMIN_PASS" --data-urlencode "admin_password_confirm=$ADMIN_PASS" >/dev/null
test "$(tr -d '\r\n' < "$ROOT/VERSION.txt")" = 2.30.0
grep -F "define('VF_VERSION', '2.30.0')" "$ROOT/app/bootstrap.php" >/dev/null
php "$ROOT/cli/verify.php" | tee "$EVID/pre-verify.txt" | grep -Fx VERIFY_PASS=YES

# 2. Representative public/private data across all four resource domains.
cat >/tmp/p01-v2310-final-seed.php <<'PHP'
<?php
declare(strict_types=1);
$root=getenv('ROOT');require $root.'/app/bootstrap.php';require_once $root.'/app/SurfaceRepository.php';
$r=new VfRepository(vf_db());$s=new VfSurfaceRepository(vf_db());
$pub=$r->createCategory(['name'=>'公开导航','description'=>'V2310 public','is_private'=>false,'sort_order'=>100]);
$priv=$r->createCategory(['name'=>'私人导航','description'=>'V2310 private','is_private'=>true,'sort_order'=>90]);
for($i=1;$i<=12;$i++)$r->saveLink(null,['category_id'=>$pub,'title'=>'公开导航资源 '.str_pad((string)$i,2,'0',STR_PAD_LEFT),'url'=>'https://v2310-public-nav-'.$i.'.example.com','description'=>'preserve','tags'=>'authority,公开','is_private'=>false,'is_favorite'=>$i===1],'manual');
for($i=1;$i<=3;$i++)$r->saveLink(null,['category_id'=>$priv,'title'=>'私人导航资源 '.str_pad((string)$i,2,'0',STR_PAD_LEFT),'url'=>'https://v2310-private-nav-'.$i.'.example.com','description'=>'private','tags'=>'authority,私人','is_private'=>true],'manual');
foreach([['channels','频道','公开频道','私人频道'],['watch','电影','公开影视','私人影视'],['topics','AI','公开专题','私人专题']] as $cfg){
 [$domain,$kind,$pt,$qt]=$cfg;
 for($i=1;$i<=3;$i++){$x=$r->saveLink(null,['category_id'=>$pub,'title'=>$pt.' '.$i,'url'=>'https://v2310-'.$domain.'-public-'.$i.'.example.com','description'=>'public domain','tags'=>'authority,公开','is_private'=>false],'manual');$p=['surface'=>$domain,'resource_kind'=>$kind,'note'=>'public-'.$domain.'-'.$i];if($domain==='channels')$p['background_friendly']=true;if($domain==='watch'){$p['media_year']=2020+$i;$p['media_status']='want';}if($domain==='topics'){$p['source_kind']='remote_url';$p['source_ref']='https://v2310-'.$domain.'-public-'.$i.'.example.com';}$s->upsertProfile((int)$x['id'],$p);}
 for($i=1;$i<=2;$i++){$x=$r->saveLink(null,['category_id'=>$priv,'title'=>$qt.' '.$i,'url'=>'https://v2310-'.$domain.'-private-'.$i.'.example.com','description'=>'private domain','tags'=>'authority,私人','is_private'=>true],'manual');$p=['surface'=>$domain,'resource_kind'=>$kind,'note'=>'private-'.$domain.'-'.$i];if($domain==='channels')$p['background_friendly']=true;if($domain==='watch'){$p['media_year']=2010+$i;$p['media_status']='favorite';}if($domain==='topics'){$p['source_kind']='remote_url';$p['source_ref']='https://v2310-'.$domain.'-private-'.$i.'.example.com';}$s->upsertProfile((int)$x['id'],$p);}
}
$db=vf_db();$c=$s->counts(true);$b=['links'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active'")->fetchColumn(),'categories'=>(int)$db->query("SELECT COUNT(*) FROM categories WHERE lifecycle_state='active'")->fetchColumn(),'favorites'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active' AND is_favorite=1")->fetchColumn(),'profiles'=>(int)$db->query('SELECT COUNT(*) FROM resource_domain_profiles')->fetchColumn(),'schema'=>(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status='success'")->fetchColumn(),'surface_counts'=>$c];
if($b['links']!==30||$b['categories']!==2||$b['favorites']!==1||$b['profiles']!==15||$b['schema']!=='2026082901')throw new RuntimeException('seed '.json_encode($b));foreach(['start'=>15,'channels'=>5,'watch'=>5,'topics'=>5,'total'=>30] as $k=>$v)if((int)($c[$k]??-1)!==$v)throw new RuntimeException('surface '.$k);
file_put_contents('/tmp/p01-v2310-final-before.json',json_encode($b,JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE));file_put_contents('/tmp/p01-v2310-final-ids.json',json_encode(['pub'=>$pub,'priv'=>$priv]));echo "SEED_PASS\n";
PHP
ROOT="$ROOT" php /tmp/p01-v2310-final-seed.php | grep -Fx SEED_PASS
cp /tmp/p01-v2310-final-before.json "$EVID/before.json"

# 3. Real online updater against published core-updates/main + GitHub Release.
cat >/tmp/p01-v2310-final-update.php <<'PHP'
<?php
declare(strict_types=1);
$root=getenv('ROOT');require $root.'/app/bootstrap.php';require_once $root.'/app/UpdateManager.php';
$m=new VfUpdateManager(vf_db(),['root'=>$root,'private_root'=>VF_PRIVATE_ROOT,'current_version'=>'2.30.0']);$c=$m->check(true);
if(($c['ok']??false)!==true||($c['current_version']??'')!=='2.30.0'||($c['latest_version']??'')!=='2.31.0'||($c['available']??false)!==true||($c['can_update']??false)!==true)throw new RuntimeException('check '.json_encode($c));
$s=$c['requirements']['schema']??[];if(($s['current']??'')!=='2026082901'||($s['from']??'')!=='2026082901'||($s['target']??'')!=='2026082901'||($s['ok']??false)!==true)throw new RuntimeException('schema '.json_encode($s));
$p=$m->prepare();if(($p['ok']??false)!==true||($p['from_version']??'')!=='2.30.0'||($p['to_version']??'')!=='2.31.0'||($p['release_tag']??'')!=='v2.31.0'||($p['asset_name']??'')!=='VF_Start_V2.31.0_UPDATE.zip'||(int)($p['update_package_bytes']??0)!==1324509||($p['update_package_sha256']??'')!=='41228689f1abb2bf7d774ac3600be18726d128d9911341318e95f7e00562a774')throw new RuntimeException('prepare '.json_encode($p));
foreach(['manifest_identity','release_tag','release_asset','bytes','sha256','atomic_self_test','recovery_point'] as $k)if(($p['checks'][$k]??'')!=='pass')throw new RuntimeException('prepare '.$k);
$i=$m->install((string)$p['operation_id']);if(($i['ok']??false)!==true||($i['updated']??false)!==true||($i['from_version']??'')!=='2.30.0'||($i['to_version']??'')!=='2.31.0')throw new RuntimeException('install '.json_encode($i));foreach(['release_identity','atomic_handoff','activation','cleanup'] as $k)if(($i['checks'][$k]??'')!=='pass')throw new RuntimeException('install '.$k);
file_put_contents(getenv('EVID').'/update.json',json_encode(['check'=>$c,'prepare'=>$p,'install'=>$i],JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES));echo "REMOTE_UPDATE_PASS\n";
PHP
ROOT="$ROOT" EVID="$EVID" php /tmp/p01-v2310-final-update.php | grep -Fx REMOTE_UPDATE_PASS

# 4. Post-upgrade version, schema, data preservation, integrity and SEO projection.
test "$(tr -d '\r\n' < "$ROOT/VERSION.txt")" = 2.31.0
grep -F "define('VF_VERSION', '2.31.0')" "$ROOT/app/bootstrap.php" >/dev/null
php "$ROOT/cli/verify.php" | tee "$EVID/post-verify.txt" | grep -Fx VERIFY_PASS=YES
cat >/tmp/p01-v2310-final-post.php <<'PHP'
<?php
declare(strict_types=1);
$root=getenv('ROOT');$before=json_decode((string)file_get_contents('/tmp/p01-v2310-final-before.json'),true,512,JSON_THROW_ON_ERROR);require $root.'/app/bootstrap.php';require_once $root.'/app/SurfaceRepository.php';
$db=vf_db();$s=new VfSurfaceRepository($db);$a=['links'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active'")->fetchColumn(),'categories'=>(int)$db->query("SELECT COUNT(*) FROM categories WHERE lifecycle_state='active'")->fetchColumn(),'favorites'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active' AND is_favorite=1")->fetchColumn(),'profiles'=>(int)$db->query('SELECT COUNT(*) FROM resource_domain_profiles')->fetchColumn(),'schema'=>(string)$db->query("SELECT COALESCE(MAX(version),'') FROM schema_migrations WHERE status='success'")->fetchColumn(),'integrity'=>strtolower((string)$db->query('PRAGMA integrity_check')->fetchColumn()),'fk'=>count($db->query('PRAGMA foreign_key_check')->fetchAll(PDO::FETCH_ASSOC)),'surface_counts'=>$s->counts(true)];
if($a['schema']!=='2026082901'||$a['integrity']!=='ok'||$a['fk']!==0)throw new RuntimeException('db '.json_encode($a));foreach(['links','categories','favorites','profiles'] as $k)if($a[$k]!==$before[$k])throw new RuntimeException('preserve '.$k);foreach($before['surface_counts'] as $k=>$v)if((int)($a['surface_counts'][$k]??-1)!==(int)$v)throw new RuntimeException('surface '.$k);
vf_seo_rebuild($db,vf_config(),null,vf_seo_base_url(),VF_VERSION);file_put_contents(getenv('EVID').'/post.json',json_encode($a,JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE));echo "POST_PASS\n";
PHP
ROOT="$ROOT" EVID="$EVID" php /tmp/p01-v2310-final-post.php | grep -Fx POST_PASS

# 5. Anonymous HTTP: Start is public category directory; domain pages are public lists; private remains hidden.
start_server
IDS=$(cat /tmp/p01-v2310-final-ids.json); PUB=$(jq -r .pub <<<"$IDS"); PRIV=$(jq -r .priv <<<"$IDS")
fetch200(){ local url="$1" out="$2"; local code; code=$(curl -sS -o "$out" -w '%{http_code}' "$url"); test "$code" = 200 || { echo "HTTP_STATUS:$url:$code" | tee -a "$EVID/http.txt"; return 20; }; }
visible_not_private(){ local file="$1" pub="$2" priv="$3" label="$4"; grep -F "$pub" "$file" >/dev/null || { echo "MISSING_PUBLIC:$label:$pub" | tee -a "$EVID/http.txt"; return 21; }; if grep -F "$priv" "$file" >/dev/null; then echo "PRIVATE_LEAK:$label:$priv" | tee -a "$EVID/http.txt"; return 22; fi; echo "HTTP_BOUNDARY_PASS:$label" | tee -a "$EVID/http.txt"; }
fetch200 "http://127.0.0.1:${PORT}/start.php" "$EVID/start-anonymous.html"; visible_not_private "$EVID/start-anonymous.html" '公开导航' '私人导航' start-directory
fetch200 "http://127.0.0.1:${PORT}/category/${PUB}/" "$EVID/category-public.html"; visible_not_private "$EVID/category-public.html" '公开导航资源 01' '私人导航资源 01' start-public-category
PRIV_CODE=$(curl -sS -o "$EVID/category-private-response.html" -w '%{http_code}' "http://127.0.0.1:${PORT}/category/${PRIV}/"); test "$PRIV_CODE" = 404 || { echo "PRIVATE_CATEGORY_HTTP_STATUS:$PRIV_CODE" | tee -a "$EVID/http.txt"; exit 23; }
for domain in channels watch topics; do fetch200 "http://127.0.0.1:${PORT}/${domain}.php" "$EVID/${domain}-anonymous.html"; done
visible_not_private "$EVID/channels-anonymous.html" '公开频道 1' '私人频道 1' channels
visible_not_private "$EVID/watch-anonymous.html" '公开影视 1' '私人影视 1' watch
visible_not_private "$EVID/topics-anonymous.html" '公开专题 1' '私人专题 1' topics
echo P01_V2310_FINAL_HTTP_PUBLIC_PRIVATE=PASS | tee -a "$EVID/http.txt"

# 6. Authenticated desktop/mobile baseline + V2.31 contextual form/copy/private-state contracts.
mkdir -p /tmp/p01-v2310-final-browser; cd /tmp/p01-v2310-final-browser
npm init -y >/dev/null 2>&1; npm install playwright@1.55.0 --no-save >/dev/null 2>&1; npx playwright install chromium --with-deps >/dev/null 2>&1
cat >gate.mjs <<'JS'
import{chromium}from'playwright';import fs from'fs';
const base='http://127.0.0.1:18645',pass='P01V2310!FinalRemote',e='/tmp/p01-v2310-final-evidence';
const browser=await chromium.launch({headless:true});
const login=async c=>{const r=await c.request.post(base+'/api.php?action=login',{data:{password:pass}});if(!r.ok())throw Error('login '+r.status())};
const overflow=async p=>(await p.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth))>1;
const fieldState=async(page,name)=>page.locator('[data-add-form]').evaluate((form,name)=>{const control=form.elements.namedItem(name);if(!control)return{exists:false};const box=control.closest('[data-surface-field],[data-html-field],[data-url-field],label')||control;const css=getComputedStyle(box);return{exists:true,visible:!box.hidden&&css.display!=='none'&&css.visibility!=='hidden'}},name);
const assertField=async(p,n,w)=>{const s=await fieldState(p,n);if(!s.exists||s.visible!==w)throw Error(`field ${n} expected ${w} got ${JSON.stringify(s)}`)};
const modes={
 'start.php':{noun:'网址',pub:'公开导航资源 01',priv:'私人导航资源 01',show:['category_id'],hide:['surface','source_kind','html','resource_kind','cover','media_year','media_status','background_friendly']},
 'channels.php':{noun:'频道',pub:'公开频道 1',priv:'私人频道 1',show:['resource_kind','cover','background_friendly'],hide:['surface','category_id','source_kind','html','media_year','media_status']},
 'watch.php':{noun:'影视',pub:'公开影视 1',priv:'私人影视 1',show:['resource_kind','cover','media_year','media_status'],hide:['surface','category_id','source_kind','html','background_friendly']},
 'topics.php':{noun:'专题',pub:'公开专题 1',priv:'私人专题 1',show:['source_kind','resource_kind','cover'],hide:['surface','category_id','html','media_year','media_status','background_friendly']}
};
const common=['url','title','tags','description','is_private','is_favorite'];
const openAndCheck=async(p,path,cfg,suffix)=>{await p.goto(base+'/'+path,{waitUntil:'networkidle'});const body=await p.locator('body').innerText();if(!body.includes(cfg.pub)||!body.includes(cfg.priv))throw Error(path+' admin data');if(await p.locator('.vf-global-domain-nav a').count()!=5||await p.locator('.vf-global-domain-nav a.active').count()!=1)throw Error(path+' global nav');if(await overflow(p))throw Error(path+' overflow');const add=p.locator('[data-open-add]:visible').first();const trigger=(await add.innerText()).replace(/\s+/g,' ').trim();if(!trigger.includes('添加'+cfg.noun))throw Error(path+' trigger '+trigger);await add.click();const panel=p.locator('[data-panel="add"]:visible');await panel.waitFor();for(const [k,v] of Object.entries({aria:await panel.getAttribute('aria-label'),title:(await panel.locator('header strong').innerText()).trim(),primary:(await panel.locator('button[type="submit"]:not([data-add-continue])').innerText()).trim()}))if(v!=='添加'+cfg.noun)throw Error(path+' '+k+' '+v);for(const f of common)await assertField(p,f,true);for(const f of cfg.show)await assertField(p,f,true);for(const f of cfg.hide)await assertField(p,f,false);await p.screenshot({path:`${e}/${path.replace('.php','')}-${suffix}.png`,fullPage:true});await p.locator('[data-close-panel]:visible').first().click()};

const d=await browser.newContext({viewport:{width:1440,height:960}});await login(d);const p=await d.newPage();for(const [path,cfg] of Object.entries(modes))await openAndCheck(p,path,cfg,'desktop');
// All Resources remains the intentional cross-domain add entry.
await p.goto(base+'/surfaces.php',{waitUntil:'networkidle'});const all=p.locator('[data-open-add]:visible').first();if(!(await all.innerText()).includes('添加资源'))throw Error('all trigger');await all.click();const allPanel=p.locator('[data-panel="add"]:visible');await allPanel.waitFor();if((await allPanel.locator('header strong').innerText()).trim()!=='添加资源')throw Error('all title');await assertField(p,'surface',true);await p.screenshot({path:e+'/all-resources-desktop.png',fullPage:true});await p.locator('[data-close-panel]:visible').first().click();
// Private state is a protected teal semantic, not a warning; explicitly toggle to make the assertion deterministic.
await p.goto(base+'/start.php',{waitUntil:'networkidle'});await p.locator('[data-open-add]:visible').first().click();const form=p.locator('[data-add-form]');const box=form.locator('input[name="is_private"]');const hint=form.locator('[data-privacy-hint]');await box.check();await box.dispatchEvent('change');await p.waitForTimeout(80);const truth=await hint.evaluate(el=>{const probe=document.createElement('span');probe.style.color='var(--ws-teal)';probe.style.backgroundColor='var(--ws-teal-soft)';document.body.appendChild(probe);const a=getComputedStyle(el),q=getComputedStyle(probe);const out={text:el.textContent||'',private:el.classList.contains('private'),color:a.color,bg:a.backgroundColor,expectedColor:q.color,expectedBg:q.backgroundColor};probe.remove();return out});if(!truth.private||!truth.text.includes('有效可见：私人')||truth.color!==truth.expectedColor||truth.bg!==truth.expectedBg)throw Error('private semantic '+JSON.stringify(truth));const cat=form.locator('select[name="category_id"]');await cat.selectOption({label:'公开导航'});await box.uncheck();await box.dispatchEvent('change');await p.waitForTimeout(80);const pubTruth=await hint.evaluate(el=>({text:el.textContent||'',private:el.classList.contains('private')}));if(pubTruth.private||!pubTruth.text.includes('有效可见：公开'))throw Error('public semantic '+JSON.stringify(pubTruth));await p.locator('[data-close-panel]:visible').first().click();
// Real authenticated create/save endpoints prove server-side cross-domain normalization after remote upgrade.
await p.goto(base+'/start.php',{waitUntil:'networkidle'});const categoryId=await p.locator('#vf-workspace-data').evaluate(n=>String(JSON.parse(n.textContent||'{}').categories?.find(c=>c.name==='公开导航')?.id||''));if(!categoryId)throw Error('category');
const post=async(endpoint,fields)=>await p.evaluate(async({endpoint,fields})=>{const state=JSON.parse(document.getElementById('vf-workspace-data')?.textContent||'{}');const fd=new FormData();fd.set('csrf',state.csrf||'');for(const[k,v]of Object.entries(fields))fd.set(k,String(v));const r=await fetch(endpoint,{method:'POST',body:fd,credentials:'same-origin',headers:{'X-Requested-With':'XMLHttpRequest'}});const j=await r.json();if(!r.ok||!j.ok)throw Error(endpoint+': '+(j.error||r.status));return j;},{endpoint,fields});
const bf=(title,url,surface)=>({category_id:categoryId,title,url,surface,resource_kind:'Gate',description:'gate',tags:'v2310',is_private:'1',is_favorite:'0',source_kind:'remote_url'});
const channel=await post('workspace-create.php',{...bf('V2310 Normalize Channel','https://normalize-channel.example.com','channels'),background_friendly:'1',media_year:'1999',media_status:'watched',source_kind:'hosted_html'});
const moving=await post('workspace-create.php',{...bf('V2310 Normalize Move','https://normalize-move.example.com','channels'),background_friendly:'1'});await post('workspace-save.php',{...bf('V2310 Normalize Move','https://normalize-move.example.com','watch'),id:moving.id,background_friendly:'1',media_year:'2024',media_status:'watched'});fs.writeFileSync(e+'/browser-contract.json',JSON.stringify({privateSemantic:truth,channel,moving},null,2));await d.close();

const m=await browser.newContext({viewport:{width:390,height:844},isMobile:true});await login(m);const q=await m.newPage();for(const path of ['start.php','watch.php','topics.php'])await openAndCheck(q,path,modes[path],'mobile');await q.goto(base+'/start.php',{waitUntil:'networkidle'});await q.locator('.vf-mobile-command-row').waitFor({state:'visible'});const tr=q.locator('.vf-mobile-category-trigger');await tr.waitFor({state:'visible'});await tr.click();const ov=q.locator('.vf-mobile-category-overlay');await ov.waitFor({state:'visible'});await ov.locator('input[type=search]').fill('私人导航');if(await ov.locator('[data-category-picker-item]',{hasText:'私人导航'}).count()!=1)throw Error('picker');if(await overflow(q))throw Error('mobile overflow');await q.screenshot({path:e+'/mobile-start-picker.png',fullPage:true});await m.close();
await browser.close();fs.writeFileSync(e+'/browser.txt','P01_V2310_FINAL_DESKTOP_MOBILE_AND_CONTEXTUAL_UX=PASS\n');
JS
node gate.mjs
grep -Fx P01_V2310_FINAL_DESKTOP_MOBILE_AND_CONTEXTUAL_UX=PASS "$EVID/browser.txt"
cd /

# 7. DB truth for normalization operations after browser gate.
cat >/tmp/p01-v2310-normalization-verify.php <<'PHP'
<?php
declare(strict_types=1);
$root=getenv('ROOT');require $root.'/app/bootstrap.php';$db=vf_db();
$get=static function(string $title)use($db):array{$s=$db->prepare('SELECT p.domain_key,p.background_friendly,p.media_year,p.media_status,p.source_kind FROM resource_domain_profiles p JOIN links l ON l.id=p.link_id WHERE l.title=?');$s->execute([$title]);$r=$s->fetch(PDO::FETCH_ASSOC);if(!is_array($r))throw new RuntimeException('missing '.$title);return $r;};
$c=$get('V2310 Normalize Channel');$m=$get('V2310 Normalize Move');
if((string)$c['domain_key']!=='channels'||(int)$c['background_friendly']!==1||$c['media_year']!==null||(string)$c['media_status']!==''||(string)$c['source_kind']!=='remote_url')throw new RuntimeException('channel '.json_encode($c));
if((string)$m['domain_key']!=='watch'||(int)$m['background_friendly']!==0||(int)$m['media_year']!==2024||(string)$m['media_status']!=='watched'||(string)$m['source_kind']!=='remote_url')throw new RuntimeException('move '.json_encode($m));
$schema=(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status='success'")->fetchColumn();$integrity=strtolower((string)$db->query('PRAGMA integrity_check')->fetchColumn());$fk=count($db->query('PRAGMA foreign_key_check')->fetchAll(PDO::FETCH_ASSOC));if($schema!=='2026082901'||$integrity!=='ok'||$fk!==0)throw new RuntimeException('db');file_put_contents(getenv('EVID').'/normalization.json',json_encode(['channel'=>$c,'move'=>$m,'schema'=>$schema,'integrity'=>$integrity,'fk'=>$fk],JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE));echo "NORMALIZATION_PASS\n";
PHP
ROOT="$ROOT" EVID="$EVID" php /tmp/p01-v2310-normalization-verify.php | tee "$EVID/normalization.txt" | grep -Fx NORMALIZATION_PASS
php "$ROOT/cli/verify.php" | tee "$EVID/final-verify.txt" | grep -Fx VERIFY_PASS=YES

echo P01_V230_TO_V2310_REMOTE_ONLINE_UPDATE_FINAL_GATE=PASS
