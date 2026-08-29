#!/usr/bin/env bash
set -Eeuo pipefail
PRODUCT=${PRODUCT:?}
ROOT=${ROOT:?}
PORT=${PORT:?}
ADMIN_PASS=${ADMIN_PASS:?}
EVID=${EVID:?}
mkdir -p "$EVID"
COOKIE=/tmp/p01-v231-context.cookies
PIDFILE=/tmp/p01-v231-context.pid
cleanup(){ if test -f "$PIDFILE"; then kill "$(cat "$PIDFILE")" >/dev/null 2>&1 || true; fi; }
trap cleanup EXIT
start_server(){
  cleanup
  php -S "127.0.0.1:${PORT}" -t "$ROOT" >"$EVID/server.log" 2>&1 & echo $! >"$PIDFILE"
  for i in $(seq 1 40); do curl -fsS "http://127.0.0.1:${PORT}/setup.php" -o /dev/null && return 0 || sleep .25; done
  echo SERVER_START_FAILED; return 1
}

# 1. Exact candidate and syntax fence.
test "$(git -C "$PRODUCT" rev-parse HEAD)" = "2bf77af426ca39667600c8e0939d3580c80133ba"
test "$(tr -d '\r\n' < "$ROOT/VERSION.txt")" = "2.30.0"
grep -F '[data-surface-field][hidden]' "$ROOT/assets/workspace-domain-nav.css" >/dev/null
php -l "$ROOT/workspace-create.php" >/dev/null
php -l "$ROOT/workspace-save.php" >/dev/null
php "$ROOT/cli/verify.php" | tee "$EVID/pre-verify.txt" | grep -Fx VERIFY_PASS=YES || true
printf '%s\n' 'P01_V231_SOURCE_SYNTAX_FENCE=PASS' | tee "$EVID/source.txt"

# 2. Fresh isolated runtime.
start_server
curl -fsS -c "$COOKIE" -b "$COOKIE" "http://127.0.0.1:${PORT}/setup.php" -o /tmp/p01-v231-setup.html
CSRF=$(python3 - <<'PY'
import re
s=open('/tmp/p01-v231-setup.html',encoding='utf-8').read();m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsS -c "$COOKIE" -b "$COOKIE" -X POST "http://127.0.0.1:${PORT}/setup.php" \
  --data-urlencode "setup_csrf=$CSRF" \
  --data-urlencode 'site_title=P01 V231 Context Gate' \
  --data-urlencode "admin_password=$ADMIN_PASS" \
  --data-urlencode "admin_password_confirm=$ADMIN_PASS" >/dev/null
php "$ROOT/cli/verify.php" | tee "$EVID/fresh-verify.txt" | grep -Fx VERIFY_PASS=YES

# 3. Seed one public category used by the create/save contract tests.
cat >/tmp/p01-v231-seed.php <<'PHP'
<?php
declare(strict_types=1);
$root=getenv('ROOT');require $root.'/app/bootstrap.php';
$r=new VfRepository(vf_db());
$id=$r->createCategory(['name'=>'V231 Gate 分类','description'=>'contextual form gate','is_private'=>false,'sort_order'=>100]);
file_put_contents('/tmp/p01-v231-category.txt',(string)$id);
echo "SEED_PASS\n";
PHP
php /tmp/p01-v231-seed.php | grep -Fx SEED_PASS

# 4. Browser truth: each domain shows only its own fields on desktop and mobile.
mkdir -p /tmp/p01-v231-browser && cd /tmp/p01-v231-browser
npm init -y >/dev/null 2>&1
npm install playwright@1.55.0 --no-save >/dev/null 2>&1
npx playwright install chromium --with-deps >/dev/null 2>&1
cat >gate.mjs <<'JS'
import{chromium}from'playwright';import fs from'fs';
const base='http://127.0.0.1:18631',pass='P01V231!Context',e='/tmp/p01-v231-context-evidence';
const browser=await chromium.launch({headless:true});
const login=async(context)=>{const r=await context.request.post(base+'/api.php?action=login',{data:{password:pass}});if(!r.ok())throw new Error('login '+r.status())};
const fieldState=async(page,name)=>page.locator('[data-add-form]').evaluate((form,name)=>{const control=form.elements.namedItem(name);if(!control)return{exists:false};const box=control.closest('[data-surface-field],[data-html-field],[data-url-field],label')||control;const css=getComputedStyle(box);return{exists:true,hidden:box.hidden,display:css.display,visible:css.display!=='none'&&css.visibility!=='hidden'}},name);
const assertField=async(page,name,want)=>{const s=await fieldState(page,name);if(!s.exists||s.visible!==want)throw new Error(`field ${name} expected ${want?'visible':'hidden'} got ${JSON.stringify(s)}`)};
const openAdd=async(page,path)=>{await page.goto(base+'/'+path,{waitUntil:'networkidle'});await page.locator('[data-open-add]:visible').first().click();await page.locator('[data-panel="add"]:visible').waitFor();await page.waitForTimeout(80)};
const common=['url','title','surface','tags','description','is_private','is_favorite'];
const hiddenByMode={
  start:['source_kind','html','resource_kind','cover','media_year','media_status','background_friendly'],
  channels:['category_id','source_kind','html','media_year','media_status'],
  watch:['category_id','source_kind','html','background_friendly'],
  topics:['category_id','html','media_year','media_status','background_friendly']
};
const visibleByMode={
  start:['category_id'],
  channels:['resource_kind','cover','background_friendly'],
  watch:['resource_kind','cover','media_year','media_status'],
  topics:['source_kind','resource_kind','cover']
};
const paths={start:'start.php',channels:'channels.php',watch:'watch.php',topics:'topics.php'};
const d=await browser.newContext({viewport:{width:1440,height:960}});await login(d);const p=await d.newPage();
for(const mode of Object.keys(paths)){
  await openAdd(p,paths[mode]);
  for(const f of common)await assertField(p,f,true);
  for(const f of visibleByMode[mode])await assertField(p,f,true);
  for(const f of hiddenByMode[mode])await assertField(p,f,false);
  if(mode==='topics'){
    await p.locator('[data-add-form] select[name="source_kind"]').selectOption('hosted_html');
    await assertField(p,'url',false);await assertField(p,'html',true);
    await p.locator('[data-add-form] select[name="source_kind"]').selectOption('remote_url');
    await assertField(p,'url',true);await assertField(p,'html',false);
  }
  await p.screenshot({path:`${e}/${mode}-desktop.png`,fullPage:true});
  await p.locator('[data-close-panel]:visible').first().click();
}

// Mobile verifies the same contextual contract at the narrow breakpoint.
const m=await browser.newContext({viewport:{width:390,height:844},isMobile:true});await login(m);const mp=await m.newPage();
for(const mode of ['start','watch','topics']){
  await openAdd(mp,paths[mode]);
  for(const f of common)await assertField(mp,f,true);
  for(const f of visibleByMode[mode])await assertField(mp,f,true);
  for(const f of hiddenByMode[mode])await assertField(mp,f,false);
  await mp.screenshot({path:`${e}/${mode}-mobile.png`,fullPage:true});
  await mp.locator('[data-close-panel]:visible').first().click();
}

// 5. Server normalization through the real authenticated create/save endpoints.
await p.goto(base+'/start.php',{waitUntil:'networkidle'});
const categoryId=await p.locator('#vf-workspace-data').evaluate(n=>String(JSON.parse(n.textContent||'{}').categories?.[0]?.id||''));if(!categoryId)throw new Error('no category');
const post=async(endpoint,fields)=>await p.evaluate(async({endpoint,fields})=>{const state=JSON.parse(document.getElementById('vf-workspace-data')?.textContent||'{}');const fd=new FormData();fd.set('csrf',state.csrf||'');for(const[k,v]of Object.entries(fields))fd.set(k,String(v));const r=await fetch(endpoint,{method:'POST',body:fd,credentials:'same-origin',headers:{'X-Requested-With':'XMLHttpRequest'}});const j=await r.json();if(!r.ok||!j.ok)throw new Error(endpoint+': '+(j.error||r.status));return j;},{endpoint,fields});
const baseFields=(title,url,surface)=>({category_id:categoryId,title,url,surface,resource_kind:'Gate',description:'gate',tags:'v231',is_private:'1',is_favorite:'0',source_kind:'remote_url'});
const createChannel=await post('workspace-create.php',{...baseFields('V231 Create Channel','https://v231-create-channel.example.com','channels'),background_friendly:'1',media_year:'1999',media_status:'watched',source_kind:'hosted_html'});
const createWatch=await post('workspace-create.php',{...baseFields('V231 Create Watch','https://v231-create-watch.example.com','watch'),background_friendly:'1',media_year:'2025',media_status:'watching'});
const createTopics=await post('workspace-create.php',{...baseFields('V231 Create Topics','https://v231-create-topics.example.com','topics'),background_friendly:'1',media_year:'1988',media_status:'favorite'});
const toWatch=await post('workspace-create.php',{...baseFields('V231 Save To Watch','https://v231-save-watch.example.com','channels'),background_friendly:'1'});
await post('workspace-save.php',{...baseFields('V231 Save To Watch','https://v231-save-watch.example.com','watch'),id:toWatch.id,background_friendly:'1',media_year:'2024',media_status:'watched'});
const toChannels=await post('workspace-create.php',{...baseFields('V231 Save To Channels','https://v231-save-channel.example.com','watch'),background_friendly:'1',media_year:'2023',media_status:'favorite'});
await post('workspace-save.php',{...baseFields('V231 Save To Channels','https://v231-save-channel.example.com','channels'),id:toChannels.id,background_friendly:'1',media_year:'1990',media_status:'favorite'});
fs.writeFileSync(`${e}/browser-contract.json`,JSON.stringify({categoryId,createChannel,createWatch,createTopics,toWatch,toChannels},null,2));
await browser.close();console.log('BROWSER_CONTEXTUAL_FORM_PASS');
JS
EVID="$EVID" node gate.mjs | tee "$EVID/browser.txt" | grep -Fx BROWSER_CONTEXTUAL_FORM_PASS
cd /

# 6. Read database truth after create/save endpoint operations.
cat >/tmp/p01-v231-data-verify.php <<'PHP'
<?php
declare(strict_types=1);
$root=getenv('ROOT');require $root.'/app/bootstrap.php';$db=vf_db();
$get=static function(string $title)use($db):array{$s=$db->prepare('SELECT p.domain_key,p.background_friendly,p.media_year,p.media_status,p.source_kind FROM resource_domain_profiles p JOIN links l ON l.id=p.link_id WHERE l.title=?');$s->execute([$title]);$r=$s->fetch(PDO::FETCH_ASSOC);if(!is_array($r))throw new RuntimeException('missing '.$title);return $r;};
$cases=[
 'V231 Create Channel'=>['channels',1,null,'','remote_url'],
 'V231 Create Watch'=>['watch',0,2025,'watching','remote_url'],
 'V231 Create Topics'=>['topics',0,null,'','remote_url'],
 'V231 Save To Watch'=>['watch',0,2024,'watched','remote_url'],
 'V231 Save To Channels'=>['channels',1,null,'','remote_url'],
];
$out=[];foreach($cases as $title=>$want){$r=$get($title);$got=[(string)$r['domain_key'],(int)$r['background_friendly'],$r['media_year']===null?null:(int)$r['media_year'],(string)$r['media_status'],(string)$r['source_kind']];if($got!==$want)throw new RuntimeException($title.' '.json_encode($got).' != '.json_encode($want));$out[$title]=$r;}
$schema=(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status='success'")->fetchColumn();if($schema!=='2026082901')throw new RuntimeException('schema '.$schema);if(strtolower((string)$db->query('PRAGMA integrity_check')->fetchColumn())!=='ok')throw new RuntimeException('integrity');if(count($db->query('PRAGMA foreign_key_check')->fetchAll(PDO::FETCH_ASSOC))!==0)throw new RuntimeException('fk');file_put_contents(getenv('EVID').'/data-contract.json',json_encode(['schema'=>$schema,'cases'=>$out],JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE));echo "DATA_DOMAIN_NORMALIZATION_PASS\n";
PHP
php /tmp/p01-v231-data-verify.php | tee "$EVID/data.txt" | grep -Fx DATA_DOMAIN_NORMALIZATION_PASS
php "$ROOT/cli/verify.php" | tee "$EVID/post-verify.txt" | grep -Fx VERIFY_PASS=YES
cat >"$EVID/verdict.txt" <<'EOF'
P01_V231_CONTEXTUAL_CREATE_FORM=PASS
P01_V231_DESKTOP_CONTEXT_FIELDS=PASS
P01_V231_MOBILE_CONTEXT_FIELDS=PASS
P01_V231_CREATE_DOMAIN_NORMALIZATION=PASS
P01_V231_SAVE_DOMAIN_NORMALIZATION=PASS
P01_V231_SCHEMA_UNCHANGED_2026082901=PASS
P01_V231_PRODUCT_VERSION_UNCHANGED_2.30.0=PASS
OWNER_PRODUCTION_WRITE=NO
EOF
cat "$EVID/verdict.txt"
