#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$GITHUB_WORKSPACE/product"
cd "$ROOT"

git fetch origin feature/v2.5.10-scratch-uaui
git checkout -B feature/v2.5.10-scratch-uaui origin/feature/v2.5.10-scratch-uaui

python3 - <<'PY'
from pathlib import Path

# Changelog: keep V2.5.10 as one unreleased candidate and fold the new UX findings into it.
p=Path('CHANGELOG.md'); s=p.read_text(encoding='utf-8')
needle='- 页签区域支持鼠标滚轮横向浏览。\n'
extra='- 临时工作台在桌面进入真正单行模式：隐藏资料库基础顶栏，TAB、行数/保存状态、最近关闭、整理、返回集中在同一行。\n- 显式点击某个 TAB 时从文档头部打开，不再继承上次位于文末的滚动位置；工作台恢复仍保留当前页现场。\n- 顶部实时显示当前临时页的行数，并与自动保存状态合并为低噪音信息（如“42 行 · 已保存”）。\n'
if extra not in s:
    assert needle in s
    s=s.replace(needle,needle+extra,1)
p.write_text(s,encoding='utf-8')

# CSS: desktop scratch workspace owns the full viewport; no redundant application header row.
p=Path('public/assets/scratch-tabs.css'); c=p.read_text(encoding='utf-8')
marker='/* V2.5.10b · single-row scratch chrome */'
override='''\n\n/* V2.5.10b · single-row scratch chrome */
body.scratch-mode-v2510 .topbar{display:none!important}
body.scratch-mode-v2510 .scratch-workspace-v259{top:0!important}
body.scratch-mode-v2510 .scratch-bar-v259{min-height:46px;height:46px;flex-wrap:nowrap!important;padding:5px 9px}
body.scratch-mode-v2510 .scratch-status-v259{min-width:auto;margin:0 2px 0 4px;text-align:right;font-variant-numeric:tabular-nums}
@media(max-width:900px){body.scratch-mode-v2510 .scratch-bar-v259{height:auto;min-height:46px;flex-wrap:wrap!important}.scratch-status-v259{margin-right:auto;text-align:left}}
'''
if marker not in c:
    p.write_text(c.rstrip()+override+'\n',encoding='utf-8')

# JS: line count + explicit tab click opens at top.
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
assert old in s
s=s.replace(old,new,1)
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
assert old in s
s=s.replace(old,new,1)
old="""  async function switchTab(id){
    if(Number(id)===Number(activeId))return;const ok=await flushSave(false);if(!ok)return;const exists=snapshot.open.some(t=>Number(t.id)===Number(id));if(!exists)return;activeId=Number(id);storage.set(ACTIVE_KEY,activeId);dirty=false;renderTabs();renderEditor();
  }
"""
new="""  async function switchTab(id){
    if(Number(id)===Number(activeId))return;const ok=await flushSave(false);if(!ok)return;const exists=snapshot.open.some(t=>Number(t.id)===Number(id));if(!exists)return;activeId=Number(id);storage.set(ACTIVE_KEY,activeId);dirty=false;renderTabs();renderEditor(true);
  }
"""
assert old in s
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
PY

node --check public/assets/scratch-tabs.js
python3 scripts/generate-source-manifest.py >/dev/null
python3 scripts/repository-gates.py
git diff --check
test "$(cat VERSION)" = 2.5.10
test "$(jq -r .version SOURCE_MANIFEST.json)" = 2.5.10

echo SOURCE_AND_PRIVACY_GATES=PASS

TEST="$RUNNER_TEMP/p02-v2510b"; SITE="$TEST/site"; NODE="$TEST/node"; mkdir -p "$SITE" "$NODE"
bash scripts/build-deploy-tree.sh "$SITE" >/dev/null
PW='P02-V2510-OneLine!'; PORT=18311
php -S 127.0.0.1:$PORT -t "$SITE" >"$TEST/server.log" 2>&1 & PID=$!
trap 'kill $PID 2>/dev/null || true' EXIT
for _ in $(seq 1 80); do curl -fsS "http://127.0.0.1:$PORT/setup.php" >/dev/null 2>&1 && break; sleep .25; done
curl -fsS -c "$TEST/c" "http://127.0.0.1:$PORT/setup.php" > "$TEST/setup"
TOKEN=$(python3 - "$TEST/setup" <<'PY'
import re,html,sys
x=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="setup_csrf" value="([^"]+)"',x);assert m;print(html.unescape(m.group(1)))
PY
)
test "$(curl -sS -o /dev/null -w '%{http_code}' -b "$TEST/c" -c "$TEST/c" -H "Origin: http://127.0.0.1:$PORT" --data-urlencode "setup_csrf=$TOKEN" --data-urlencode "password=$PW" --data-urlencode "password_confirm=$PW" "http://127.0.0.1:$PORT/setup.php")" = 303

cd "$NODE"
npm init -y >/dev/null 2>&1
npm install --no-audit --no-fund puppeteer-core@24.16.0 >/dev/null 2>&1
CHROME=$(command -v google-chrome-stable || command -v google-chrome || command -v chromium || true); test -n "$CHROME"
cat > test.mjs <<'JS'
import puppeteer from 'puppeteer-core';
const [url,password,chrome]=process.argv.slice(2);
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const browser=await puppeteer.launch({headless:true,executablePath:chrome,args:['--no-sandbox','--disable-dev-shm-usage']});
const page=await browser.newPage();await page.setViewport({width:1365,height:768});
await page.goto(url,{waitUntil:'networkidle0'});
await page.evaluate(async password=>{const r=await fetch('/api.php?action=login',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({password})});if(!r.ok)throw new Error('login '+r.status);},password);
await page.reload({waitUntil:'networkidle0'});await page.waitForSelector('#scratchLaunchV259',{visible:true,timeout:12000});await page.click('#scratchLaunchV259');await page.waitForSelector('#scratchWorkspaceV259 [data-scratch-editor]:not([disabled])',{timeout:10000});
const topbar=await page.evaluate(()=>{const el=document.querySelector('.topbar');return el?getComputedStyle(el).display:null});if(topbar!==null&&topbar!=='none')throw new Error('base topbar remains');
const rect=await page.$eval('#scratchWorkspaceV259',el=>({top:el.getBoundingClientRect().top,bar:el.querySelector('.scratch-bar-v259').getBoundingClientRect().height}));if(rect.top!==0||rect.bar>48)throw new Error('not single row '+JSON.stringify(rect));
let editor=await page.$('[data-scratch-editor]');await editor.type('第一行\n第二行\n第三行',{delay:3});await page.waitForFunction(()=>document.querySelector('[data-scratch-status]')?.textContent.includes('3 行'),{timeout:5000});await page.waitForFunction(()=>document.querySelector('[data-scratch-status]')?.textContent.includes('已保存'),{timeout:10000});
// create a long second tab, push it to the bottom, switch away and explicitly click back: it must open at document top.
await page.click('[data-scratch-add]');await sleep(150);await page.evaluate(()=>{const e=document.querySelector('[data-scratch-editor]');e.value=Array.from({length:180},(_,i)=>'第 '+(i+1)+' 行内容').join('\n');e.dispatchEvent(new Event('input',{bubbles:true}));});await page.waitForFunction(()=>document.querySelector('[data-scratch-status]')?.textContent.includes('180 行'),{timeout:5000});await sleep(800);
await page.$eval('[data-scratch-editor]',e=>{e.scrollTop=e.scrollHeight;e.setSelectionRange(e.value.length,e.value.length);e.dispatchEvent(new Event('scroll'));});
const ids=await page.$$eval('[data-scratch-tab]',els=>els.map(e=>e.dataset.scratchTab));if(ids.length<2)throw new Error('need two tabs');
await page.click('[data-scratch-tab="'+ids[0]+'"]');await sleep(120);await page.click('[data-scratch-tab="'+ids[1]+'"]');await sleep(160);
const pos=await page.$eval('[data-scratch-editor]',e=>({scrollTop:e.scrollTop,start:e.selectionStart}));if(pos.scrollTop>2||pos.start!==0)throw new Error('tab did not open at top '+JSON.stringify(pos));
const status=await page.$eval('[data-scratch-status]',e=>e.textContent.trim());if(!/^180 行 · 已保存$/.test(status))throw new Error('line/save status '+status);
const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1);if(overflow)throw new Error('desktop horizontal overflow');
await page.setViewport({width:390,height:844});await sleep(250);const mob=await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1);if(mob)throw new Error('mobile horizontal overflow');
await browser.close();
console.log('SCRATCH_V2510_SINGLE_ROW_BROWSER=PASS');
console.log('TAB_CLICK_OPENS_AT_TOP=PASS');
console.log('LIVE_LINE_COUNT=PASS');
console.log('AUTOSAVE_STATUS=PASS');
console.log('RESPONSIVE_OVERFLOW=PASS');
JS
node test.mjs "http://127.0.0.1:$PORT/" "$PW" "$CHROME"

echo FRESH_INSTALL=PASS
cd "$ROOT"
git config user.name 'VF Agent'
git config user.email 'vf-agent@users.noreply.github.com'
git add VERSION CHANGELOG.md SOURCE_MANIFEST.json public/assets/scratch-tabs.css public/assets/scratch-tabs.js
if ! git diff --cached --quiet; then git commit -m 'refine(P02): single-row scratch UX and line count'; fi
git push "https://x-access-token:${WRITE_TOKEN}@github.com/llhzx2018/vf-library.git" HEAD:feature/v2.5.10-scratch-uaui

echo CANDIDATE_SHA=$(git rev-parse HEAD)
echo PRIVATE_BRANCH_PUSH=PASS
echo PRODUCTION_WRITE=NO
