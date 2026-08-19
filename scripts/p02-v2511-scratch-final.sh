#!/usr/bin/env bash
set -Eeuo pipefail
cd product

test "$(git rev-parse HEAD)" = "$(git rev-parse v2.5.10)"
test "$(tr -d '\r\n' < VERSION)" = 2.5.10

python3 - <<'PY'
from pathlib import Path

Path('VERSION').write_text('2.5.11\n',encoding='utf-8')

p=Path('CHANGELOG.md'); s=p.read_text(encoding='utf-8')
entry='''## V2.5.11 · Scratch Tabs 最终 UX/UI 收敛\n\n- 显式点击任意临时 TAB 时从文档头部打开，不再跳到上次位于文末的滚动位置。\n- 桌面临时工作台改为真正单行顶栏：隐藏资料库基础顶栏，TAB、行数/保存状态、最近关闭、整理、返回集中在同一行。\n- 顶部实时显示当前临时页行数，并与自动保存状态合并为低噪音信息，例如“42 行 · 已保存”。\n- 保留 V2.5.10 已完成的紧凑 TAB、滚轮横向浏览、低噪音关闭按钮与输入时不重建整个 Tab DOM。\n- Schema 2401 不变，无 Migration。\n\n'''
if not s.startswith('## V2.5.11'):
    p.write_text(entry+s,encoding='utf-8')

p=Path('public/assets/scratch-tabs.css'); c=p.read_text(encoding='utf-8')
marker='/* V2.5.11 · final scratch UX */'
override='''\n\n/* V2.5.11 · final scratch UX */
body.scratch-mode-v2510 .topbar{display:none!important}
body.scratch-mode-v2510 .scratch-workspace-v259{top:0!important}
body.scratch-mode-v2510 .scratch-bar-v259{height:46px;min-height:46px;flex-wrap:nowrap!important;padding:5px 9px}
body.scratch-mode-v2510 .scratch-status-v259{min-width:auto;margin:0 2px 0 4px;text-align:right;font-variant-numeric:tabular-nums}
@media(max-width:900px){body.scratch-mode-v2510 .scratch-bar-v259{height:auto;min-height:46px;flex-wrap:wrap!important}.scratch-status-v259{margin-right:auto;text-align:left}}
'''
if marker not in c:
    p.write_text((c.rstrip()+override).rstrip()+'\n',encoding='utf-8')

p=Path('public/assets/scratch-tabs.js'); s=p.read_text(encoding='utf-8')
old="""  function status(text,kind=''){
    if(!workspace)return;const node=workspace.querySelector('[data-scratch-status]');if(!node)return;node.textContent=text;node.classList.remove('saving','failed');if(kind)node.classList.add(kind);
  }
"""
new="""  function lineCount(value){
    const text=String(value??'');return text===''?1:text.split(/\\r?\\n/).length;
  }

  function status(text,kind=''){
    if(!workspace)return;const node=workspace.querySelector('[data-scratch-status]');if(!node)return;const tab=current();const lines=tab?(lineCount(tab.content)+' 行'):'';node.textContent=text?(lines?lines+' · '+text:text):lines;node.classList.remove('saving','failed');if(kind)node.classList.add(kind);
  }
"""
assert old in s;s=s.replace(old,new,1)
old="""  function renderEditor(){
    if(!workspace)return;const tab=current();editor=workspace.querySelector('[data-scratch-editor]');const empty=workspace.querySelector('[data-scratch-empty]');
    if(!tab){editor.value='';editor.disabled=true;empty.classList.remove('hidden');status('');return;}
    empty.classList.add('hidden');editor.disabled=false;editor.value=String(tab.content||'');
    requestAnimationFrame(()=>{
      try{editor.setSelectionRange(Number(tab.cursor_pos||0),Number(tab.cursor_pos||0));editor.scrollTop=Number(tab.scroll_top||0);}catch(e){}
      editor.focus();
    });
    status('已保存');
  }
"""
new="""  function renderEditor(openAtTop=false){
    if(!workspace)return;const tab=current();editor=workspace.querySelector('[data-scratch-editor]');const empty=workspace.querySelector('[data-scratch-empty]');
    if(!tab){editor.value='';editor.disabled=true;empty.classList.remove('hidden');status('');return;}
    empty.classList.add('hidden');editor.disabled=false;editor.value=String(tab.content||'');
    requestAnimationFrame(()=>{
      try{const pos=openAtTop?0:Number(tab.cursor_pos||0);editor.setSelectionRange(pos,pos);editor.scrollTop=openAtTop?0:Number(tab.scroll_top||0);}catch(e){}
      editor.focus();
    });
    status('已保存');
  }
"""
assert old in s;s=s.replace(old,new,1)
old="""  async function switchTab(id){
    if(Number(id)===Number(activeId))return;const ok=await flushSave(false);if(!ok)return;const exists=snapshot.open.some(t=>Number(t.id)===Number(id));if(!exists)return;activeId=Number(id);storage.set(ACTIVE_KEY,activeId);dirty=false;renderTabs();renderEditor();
  }
"""
new="""  async function switchTab(id){
    if(Number(id)===Number(activeId))return;const ok=await flushSave(false);if(!ok)return;const exists=snapshot.open.some(t=>Number(t.id)===Number(id));if(!exists)return;activeId=Number(id);storage.set(ACTIVE_KEY,activeId);dirty=false;renderTabs();renderEditor(true);
  }
"""
assert old in s;s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')

p=Path('public/assets/v254-common-branding.js'); s=p.read_text(encoding='utf-8')
assert "||'2.5.10';" in s
p.write_text(s.replace("||'2.5.10';","||'2.5.11';",1),encoding='utf-8')
PY

node --check public/assets/scratch-tabs.js
node --check public/assets/v254-common-branding.js
python3 scripts/generate-source-manifest.py >/dev/null
python3 scripts/repository-gates.py
git diff --check
test "$(cat VERSION)" = 2.5.11
test "$(jq -r .version SOURCE_MANIFEST.json)" = 2.5.11

echo SOURCE_PRIVACY_GATES=PASS

ROOT="$RUNNER_TEMP/p02-v2511"; SITE="$ROOT/site"; NODE="$ROOT/node"; mkdir -p "$SITE" "$NODE"
bash scripts/build-deploy-tree.sh "$SITE" >/dev/null
test "$(cat "$SITE/VERSION.txt")" = 2.5.11
PW='P02-V2511-Scratch!'; PORT=18331
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

cd "$NODE"; npm init -y >/dev/null 2>&1; npm install --no-audit --no-fund puppeteer-core@24.16.0 >/dev/null 2>&1
CHROME=$(command -v google-chrome-stable || command -v google-chrome || command -v chromium || true); test -n "$CHROME"
cat > test.mjs <<'JS'
import puppeteer from 'puppeteer-core';
const [url,password,chrome]=process.argv.slice(2);const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const browser=await puppeteer.launch({headless:true,executablePath:chrome,args:['--no-sandbox','--disable-dev-shm-usage']});const page=await browser.newPage();await page.setViewport({width:1365,height:768});
await page.goto(url,{waitUntil:'networkidle0'});await page.evaluate(async password=>{const r=await fetch('/api.php?action=login',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({password})});if(!r.ok)throw new Error('login '+r.status);},password);await page.reload({waitUntil:'networkidle0'});
await page.waitForSelector('#scratchLaunchV259',{visible:true,timeout:12000});await page.click('#scratchLaunchV259');await page.waitForSelector('#scratchWorkspaceV259 [data-scratch-editor]:not([disabled])',{timeout:10000});
const chromeState=await page.evaluate(()=>({topbar:getComputedStyle(document.querySelector('.topbar')).display,top:document.querySelector('#scratchWorkspaceV259').getBoundingClientRect().top,bar:document.querySelector('.scratch-bar-v259').getBoundingClientRect().height}));if(chromeState.topbar!=='none'||chromeState.top!==0||chromeState.bar>48)throw new Error('single row failed '+JSON.stringify(chromeState));
let editor=await page.$('[data-scratch-editor]');await editor.type('一\n二\n三',{delay:3});await page.waitForFunction(()=>document.querySelector('[data-scratch-status]')?.textContent==='3 行 · 已保存',{timeout:10000});
await page.click('[data-scratch-add]');await sleep(120);await page.evaluate(()=>{const e=document.querySelector('[data-scratch-editor]');e.value=Array.from({length:160},(_,i)=>'第'+(i+1)+'行').join('\n');e.dispatchEvent(new Event('input',{bubbles:true}));});await page.waitForFunction(()=>document.querySelector('[data-scratch-status]')?.textContent.startsWith('160 行'),{timeout:5000});await sleep(700);await page.$eval('[data-scratch-editor]',e=>{e.scrollTop=e.scrollHeight;e.setSelectionRange(e.value.length,e.value.length);e.dispatchEvent(new Event('scroll'));});
const ids=await page.$$eval('[data-scratch-tab]',els=>els.map(e=>e.dataset.scratchTab));await page.click('[data-scratch-tab="'+ids[0]+'"]');await sleep(100);await page.click('[data-scratch-tab="'+ids[1]+'"]');await sleep(150);const pos=await page.$eval('[data-scratch-editor]',e=>({scrollTop:e.scrollTop,start:e.selectionStart}));if(pos.scrollTop>2||pos.start!==0)throw new Error('tab top failed '+JSON.stringify(pos));
await page.setViewport({width:390,height:844});await sleep(200);if(await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1))throw new Error('mobile overflow');await browser.close();
console.log('V2511_SINGLE_ROW=PASS');console.log('V2511_TAB_TOP=PASS');console.log('V2511_LINE_COUNT=PASS');console.log('V2511_MOBILE=PASS');
JS
node test.mjs "http://127.0.0.1:$PORT/" "$PW" "$CHROME"

echo REAL_BROWSER_AND_FRESH_INSTALL=PASS
cd "$GITHUB_WORKSPACE/product"
git config user.name 'VF Agent';git config user.email 'vf-agent@users.noreply.github.com'
git checkout -b feature/v2.5.11-scratch-final
git add VERSION CHANGELOG.md SOURCE_MANIFEST.json public/assets/scratch-tabs.css public/assets/scratch-tabs.js public/assets/v254-common-branding.js
git commit -m 'VF Library V2.5.11 · final Scratch Tabs UX UI'
git push "https://x-access-token:${WRITE_TOKEN}@github.com/llhzx2018/vf-library.git" HEAD:feature/v2.5.11-scratch-final

echo CANDIDATE_SHA=$(git rev-parse HEAD)
echo PRIVATE_BRANCH_PUSH=PASS
echo PRODUCTION_WRITE=NO
