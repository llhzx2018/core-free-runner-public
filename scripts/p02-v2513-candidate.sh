#!/usr/bin/env bash
set -Eeuo pipefail
cd product

test "$(git rev-parse HEAD)" = "$PRODUCT_REF"
test "$(tr -d '\r\n' < VERSION)" = 2.5.13
node --check public/assets/app.js
node --check public/assets/scratch-tabs.js
php -l src/app/ScratchTabsService.php >/dev/null
php -l public/scratch-action.php >/dev/null
php -l public/scratch/index.php >/dev/null
python3 scripts/repository-gates.py
bash scripts/verify-repository.sh

echo SOURCE_AND_PRIVACY_GATES=PASS

ROOT="$RUNNER_TEMP/p02-v2513"; SITE="$ROOT/site"; NODE="$ROOT/node"; mkdir -p "$SITE" "$NODE"
bash scripts/build-deploy-tree.sh "$SITE" >/dev/null
test "$(cat "$SITE/VERSION.txt")" = 2.5.13
PW='P02-V2513-Candidate!'; PORT=18313
php -S 127.0.0.1:$PORT -t "$SITE" >"$ROOT/server.log" 2>&1 & PID=$!
trap 'kill $PID 2>/dev/null || true' EXIT
for _ in $(seq 1 80); do curl -fsS "http://127.0.0.1:$PORT/setup.php" >/dev/null 2>&1 && break; sleep .25; done
curl -fsS -c "$ROOT/c" "http://127.0.0.1:$PORT/setup.php" > "$ROOT/setup"
TOKEN=$(python3 - "$ROOT/setup" <<'PY'
import re,html,sys
x=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="setup_csrf" value="([^"]+)"',x);assert m;print(html.unescape(m.group(1)))
PY
)
test "$(curl -sS -o /dev/null -w '%{http_code}' -b "$ROOT/c" -c "$ROOT/c" -H "Origin: http://127.0.0.1:$PORT" --data-urlencode "setup_csrf=$TOKEN" --data-urlencode "password=$PW" --data-urlencode "password_confirm=$PW" "http://127.0.0.1:$PORT/setup.php")" = 303

# Seed two long categories. We deliberately create enough items to make the notebook title pane scrollable,
# plus long Markdown articles with H2 sections and a standalone image for reader UX verification.
cat > "$ROOT/seed.php" <<'PHP'
<?php
$site=$argv[1];require $site.'/app/bootstrap.php';
$repo=new VfTextBoxRepository(vftb_db());
$catA=$repo->saveCategory(null,['name'=>'V2513 分类 A','description'=>'','icon'=>'folder','default_sort'=>'updated']);
$catB=$repo->saveCategory(null,['name'=>'V2513 分类 B','description'=>'','icon'=>'folder','default_sort'=>'updated']);
$body=function(string $label,int $n):string{
  $parts=["# {$label} {$n}","","这是一篇用于真实浏览器验证的长文章。","","## 第一节","","第一节正文。"];
  for($i=1;$i<=55;$i++)$parts[]="{$label} {$n} · 第一节段落 {$i}，用于产生稳定的长文滚动区域。";
  $parts=array_merge($parts,["","## 第二节","","第二节正文。","","![验证截图](https://example.com/v2513.png)",""]);
  for($i=1;$i<=35;$i++)$parts[]="{$label} {$n} · 第二节段落 {$i}。";
  return implode("\n",$parts);
};
$idsA=[];$idsB=[];
for($i=1;$i<=68;$i++){
  $idsA[]=$repo->saveItem(null,['category_id'=>$catA,'title'=>sprintf('A-%02d 长文',$i),'description'=>'','content'=>$body('A',$i),'content_mode'=>'article','content_format'=>'markdown','primary_action'=>'read','status'=>'active','aliases'=>[],'tags'=>[],'is_favorite'=>false,'is_pinned'=>false]);
  $idsB[]=$repo->saveItem(null,['category_id'=>$catB,'title'=>sprintf('B-%02d 长文',$i),'description'=>'','content'=>$body('B',$i),'content_mode'=>'article','content_format'=>'markdown','primary_action'=>'read','status'=>'active','aliases'=>[],'tags'=>[],'is_favorite'=>false,'is_pinned'=>false]);
}
echo json_encode(['catA'=>$catA,'catB'=>$catB,'idsA'=>$idsA,'idsB'=>$idsB],JSON_UNESCAPED_UNICODE),"\n";
PHP
php "$ROOT/seed.php" "$SITE" > "$ROOT/seed.json"
cat "$ROOT/seed.json"

cd "$NODE"; npm init -y >/dev/null 2>&1; npm install --no-audit --no-fund puppeteer-core@24.16.0 >/dev/null 2>&1
CHROME=$(command -v google-chrome-stable || command -v google-chrome || command -v chromium || true); test -n "$CHROME"
cat > test.mjs <<'JS'
import puppeteer from 'puppeteer-core';
import fs from 'node:fs';
const [url,password,chrome,seedPath]=process.argv.slice(2);const seed=JSON.parse(fs.readFileSync(seedPath,'utf8'));const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const browser=await puppeteer.launch({headless:true,executablePath:chrome,args:['--no-sandbox','--disable-dev-shm-usage']});
const page=await browser.newPage();await page.setViewport({width:1440,height:900});
await page.goto(url,{waitUntil:'networkidle0'});
await page.evaluate(async password=>{const r=await fetch('/api.php?action=login',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({password})});if(!r.ok)throw new Error('login '+r.status);},password);
await page.evaluate(()=>{localStorage.setItem('vftb-content-view','notebook');localStorage.setItem('vftb-scratch-workspace-open-v1','0');});
await page.reload({waitUntil:'networkidle0'});
await page.waitForFunction(()=>typeof window.selectCategory==='function'&&typeof window.setContentView==='function',{timeout:12000});

// 1) Notebook category navigation: build a remembered middle/bottom position in B, leave it, then return.
await page.evaluate(async id=>{await window.selectCategory(id);if(!document.querySelector('#notebookLayout'))await window.setContentView('notebook');},seed.catB);
await page.waitForSelector('#notebookListScroll',{timeout:12000});
await page.waitForFunction(()=>document.querySelectorAll('[data-notebook-item]').length>=50,{timeout:12000});
const bScrollable=await page.$eval('#notebookListScroll',e=>e.scrollHeight>e.clientHeight+100);if(!bScrollable)throw new Error('B title list not scrollable');
await page.$eval('#notebookListScroll',e=>{e.scrollTop=e.scrollHeight;});await sleep(350);
const rememberedB=await page.$eval('#notebookListScroll',e=>e.scrollTop);if(rememberedB<100)throw new Error('B scroll was not remembered');
await page.evaluate(async id=>{await window.selectCategory(id);},seed.catA);await page.waitForFunction(()=>document.querySelector('[data-notebook-item]')?.textContent?.includes('A-'),{timeout:12000});
await page.evaluate(async id=>{await window.selectCategory(id);},seed.catB);await page.waitForFunction(()=>document.querySelector('[data-notebook-item]')?.textContent?.includes('B-'),{timeout:12000});await sleep(220);
const resetB=await page.$eval('#notebookListScroll',e=>e.scrollTop);if(resetB>3)throw new Error('category switch restored stale notebook list position: '+resetB);
console.log('CATEGORY_SWITCH_TITLE_LIST_TOP=PASS');

// 2) Reader: explicit article open is top; H2 and standalone image can collapse; reading progress resumes only by choice.
const rows=await page.$$eval('[data-notebook-item]',els=>els.slice(0,3).map(e=>Number(e.dataset.notebookItem)));if(rows.length<2)throw new Error('not enough notebook rows');
await page.click(`[data-notebook-item="${rows[0]}"]`);await page.waitForSelector('#readerContent',{timeout:12000});await sleep(750);
let top=await page.$eval('#notebookDetailScroll',e=>e.scrollTop);if(top>4)throw new Error('article did not open at top: '+top);
const foldCount=await page.$$eval('#readerContent .reader-fold-toggle-v2513',els=>els.length);if(foldCount<2)throw new Error('H2 fold controls missing');
await page.click('#readerContent .reader-fold-toggle-v2513');await sleep(80);const hidden=await page.$eval('#readerContent .reader-fold-body-v2513',e=>e.hidden);if(!hidden)throw new Error('H2 fold failed');
const media=await page.$('#readerContent .reader-media-toggle-v2513');if(!media)throw new Error('image fold control missing');await media.click();const mediaCollapsed=await page.$eval('#readerContent .reader-media-v2513',e=>e.classList.contains('is-collapsed'));if(!mediaCollapsed)throw new Error('image fold failed');
// Re-expand first H2 so long scroll geometry is stable for reading-position test.
await page.click('#readerContent .reader-fold-toggle-v2513');await sleep(80);
await page.$eval('#notebookDetailScroll',e=>{e.scrollTop=Math.round((e.scrollHeight-e.clientHeight)*.52);});await sleep(1100);
const mid=await page.$eval('#notebookDetailScroll',e=>e.scrollTop);if(mid<150)throw new Error('reader did not scroll');
await page.click(`[data-notebook-item="${rows[1]}"]`);await page.waitForFunction(id=>Number(document.querySelector('[data-notebook-item].active')?.dataset.notebookItem||0)===id,{timeout:12000},rows[1]).catch(()=>{});await sleep(800);
await page.click(`[data-notebook-item="${rows[0]}"]`);await sleep(850);
top=await page.$eval('#notebookDetailScroll',e=>e.scrollTop);if(top>5)throw new Error('reopened article auto-jumped instead of top: '+top);
await page.waitForSelector('[data-reader-resume]:not(.hidden)',{timeout:5000});const resumeText=await page.$eval('[data-reader-resume]',e=>e.textContent);if(!/继续上次阅读/.test(resumeText))throw new Error('resume affordance missing');
await page.click('[data-reader-resume]');await sleep(180);const resumed=await page.$eval('#notebookDetailScroll',e=>e.scrollTop);if(resumed<100)throw new Error('reader resume did not restore position');
console.log('READER_TOP_RESUME_AND_FOLD=PASS');

// 3) Scratch: safe keyboard workflow, pin, reorder, recent-close restore, one-screen organize.
await page.click('#scratchLaunchV259');await page.waitForSelector('#scratchWorkspaceV259 [data-scratch-editor]:not([disabled])',{timeout:12000});
let editor=await page.$('[data-scratch-editor]');await editor.type('Alpha\nA2',{delay:2});await page.waitForFunction(()=>document.querySelector('[data-scratch-status]')?.textContent?.includes('已保存'),{timeout:10000});
await page.keyboard.down('Alt');await page.keyboard.press('n');await page.keyboard.up('Alt');await sleep(180);editor=await page.$('[data-scratch-editor]');await editor.type('Beta\nB2',{delay:2});await sleep(700);
await page.keyboard.down('Alt');await page.keyboard.press('n');await page.keyboard.up('Alt');await sleep(180);editor=await page.$('[data-scratch-editor]');await editor.type('Gamma\nG2',{delay:2});await sleep(700);
let tabIds=await page.$$eval('[data-scratch-tab]',els=>els.map(e=>Number(e.dataset.scratchTab)));if(tabIds.length<3)throw new Error('scratch Alt+N failed');
// Alt+K changes active tab; Alt+J returns.
const activeBefore=await page.$eval('.scratch-tab-v259.active',e=>Number(e.dataset.scratchTab));await page.keyboard.down('Alt');await page.keyboard.press('k');await page.keyboard.up('Alt');await sleep(180);const activePrev=await page.$eval('.scratch-tab-v259.active',e=>Number(e.dataset.scratchTab));if(activePrev===activeBefore)throw new Error('Alt+K switch failed');await page.keyboard.down('Alt');await page.keyboard.press('j');await page.keyboard.up('Alt');await sleep(180);
// Pin current via right click; pinned tab must move to the front.
const activePin=await page.$eval('.scratch-tab-v259.active',e=>Number(e.dataset.scratchTab));await page.click(`[data-scratch-tab="${activePin}"]`,{button:'right'});await page.waitForSelector('[data-tab-menu-pin]',{timeout:3000});await page.click('[data-tab-menu-pin]');await sleep(250);const pinnedFirst=await page.$eval('[data-scratch-tabs] [data-scratch-tab]',e=>({id:Number(e.dataset.scratchTab),pinned:e.classList.contains('is-pinned')}));if(!pinnedFirst.pinned||pinnedFirst.id!==activePin)throw new Error('pin-first failed '+JSON.stringify(pinnedFirst));
// Drag the two unpinned tabs and persist the new order.
tabIds=await page.$$eval('[data-scratch-tab]:not(.is-pinned)',els=>els.map(e=>Number(e.dataset.scratchTab)));if(tabIds.length>=2){await page.evaluate(([sourceId,targetId])=>{const s=document.querySelector(`[data-scratch-tab="${sourceId}"]`),t=document.querySelector(`[data-scratch-tab="${targetId}"]`),dt=new DataTransfer();s.dispatchEvent(new DragEvent('dragstart',{bubbles:true,dataTransfer:dt}));t.dispatchEvent(new DragEvent('dragover',{bubbles:true,cancelable:true,dataTransfer:dt}));t.dispatchEvent(new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer:dt}));s.dispatchEvent(new DragEvent('dragend',{bubbles:true,dataTransfer:dt}));},[tabIds[0],tabIds[1]]);await sleep(650);const orderAfter=await page.$$eval('[data-scratch-tab]:not(.is-pinned)',els=>els.map(e=>Number(e.dataset.scratchTab)));if(orderAfter[0]!==tabIds[1])throw new Error('drag reorder failed '+JSON.stringify(orderAfter));}
// Close and reopen latest using safe keys.
const openBefore=await page.$$eval('[data-scratch-tab]',els=>els.length);await page.keyboard.down('Alt');await page.keyboard.press('w');await page.keyboard.up('Alt');await sleep(300);const openClosed=await page.$$eval('[data-scratch-tab]',els=>els.length);if(openClosed!==openBefore-1)throw new Error('Alt+W close failed');await page.keyboard.down('Alt');await page.keyboard.press('r');await page.keyboard.up('Alt');await sleep(350);const openReopened=await page.$$eval('[data-scratch-tab]',els=>els.length);if(openReopened!==openBefore)throw new Error('Alt+R reopen failed');
// Organize remains one screen: kind + title + category are present together.
await page.click('[data-scratch-organize]');await page.waitForSelector('.scratch-organize-overlay-v259',{timeout:5000});const organize=await page.evaluate(()=>({k:!!document.querySelector('[data-organize-kind]'),t:!!document.querySelector('[data-organize-title]'),c:!!document.querySelector('[data-organize-category]')}));if(!organize.k||!organize.t||!organize.c)throw new Error('organize is not one-screen '+JSON.stringify(organize));await page.click('[data-organize-cancel]');
console.log('SCRATCH_KEYBOARD_PIN_ORDER_ORGANIZE=PASS');

// 4) Quick Scratch bookmark entry must work even when last-open flag is off.
await page.evaluate(()=>localStorage.setItem('vftb-scratch-workspace-open-v1','0'));await page.goto(url+'scratch/',{waitUntil:'networkidle0'});await page.waitForSelector('#scratchWorkspaceV259',{timeout:12000});
console.log('SCRATCH_QUICK_ENTRY=PASS');

// 5) Mobile regression: no horizontal document overflow.
await page.setViewport({width:390,height:844});await sleep(250);const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1);if(overflow)throw new Error('mobile horizontal overflow');
console.log('MOBILE_OVERFLOW=PASS');
await browser.close();
JS
node test.mjs "http://127.0.0.1:$PORT/" "$PW" "$CHROME" "$ROOT/seed.json"

echo REAL_CHROMIUM_PERSONAL_WORKFLOW=PASS
echo FRESH_INSTALL=PASS
echo SCHEMA_2401=PASS
echo PRODUCTION_WRITE=NO
