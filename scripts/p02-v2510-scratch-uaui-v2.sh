#!/usr/bin/env bash
set -Eeuo pipefail
cd product

python3 - <<'PY'
from pathlib import Path
root=Path('.')
(root/'VERSION').write_text('2.5.10\n',encoding='utf-8')

p=root/'CHANGELOG.md'; s=p.read_text(encoding='utf-8')
entry='''## V2.5.10 · Scratch Tabs UX/UI 精修\n\n- 临时工作台进入沉浸模式，隐藏临时记录时无关的搜索、文档工具和正式内容“新增”入口。\n- 顶部入口由“临时 + 数量”收敛为“临时 数量”，避免把工作台入口误解为直接新建。\n- 页签改为更接近桌面 Notepad 的紧凑标签形态，隐藏横向滚动条；关闭按钮仅在当前/悬停页签明显显示。\n- 操作区收紧为“最近关闭 / 整理 / 返回”，自动保存状态收敛为“已保存”。\n- 输入时只更新当前页签标题，不再每个按键重建整条 Tab DOM，减少多 TAB 连续输入时的 UI 抖动。\n- 页签区域支持鼠标滚轮横向浏览。\n- Schema 2401 不变，无 Migration。\n\n'''
if not s.startswith('## V2.5.10'): p.write_text(entry+s,encoding='utf-8')

css=root/'public/assets/scratch-tabs.css'; c=css.read_text(encoding='utf-8')
marker='/* V2.5.10 · Scratch Tabs UX/UI refinement */'
override='''\n\n/* V2.5.10 · Scratch Tabs UX/UI refinement */
body.scratch-mode-v2510 .search-wrap,
body.scratch-mode-v2510 .workspace-top-controls,
body.scratch-mode-v2510 #updateBadgeBtn,
body.scratch-mode-v2510 #addContentSplit{display:none!important}
body.scratch-mode-v2510 .topbar-inner{gap:8px}
body.scratch-mode-v2510 .scratch-launch-v259{background:color-mix(in srgb,var(--primary) 8%,var(--surface));border-color:color-mix(in srgb,var(--primary) 42%,var(--border));color:var(--primary)}
.scratch-launch-v259{gap:6px;padding:0 10px;font-weight:720}
.scratch-launch-v259 b{min-width:18px;height:18px;padding:0 5px;font-size:10px}
.scratch-bar-v259{min-height:48px;gap:6px;padding:6px 10px;background:var(--surface-soft)}
.scratch-tabs-scroll-v259{scrollbar-width:none}
.scratch-tabs-scroll-v259::-webkit-scrollbar{display:none;width:0;height:0}
.scratch-tabs-v259{gap:2px;padding:0;min-width:max-content}
.scratch-tab-v259{height:35px;min-width:112px;max-width:214px;border-radius:7px;background:transparent;border-color:transparent;color:var(--muted);padding:0 7px 0 10px;font-size:13px;font-weight:650}
.scratch-tab-v259:hover{background:var(--surface);border-color:var(--border);color:var(--strong)}
.scratch-tab-v259.active{background:var(--surface);border-color:var(--border);color:var(--strong);box-shadow:inset 0 -2px var(--primary)}
.scratch-tab-v259 .scratch-tab-close-v259{opacity:0;transition:opacity .14s,background .14s,color .14s}
.scratch-tab-v259:hover .scratch-tab-close-v259,.scratch-tab-v259.active .scratch-tab-close-v259,.scratch-tab-v259:focus-visible .scratch-tab-close-v259{opacity:1}
.scratch-add-tab-v259{width:34px;height:34px;border-color:transparent;background:transparent;border-radius:7px;font-size:20px}
.scratch-add-tab-v259:hover{border-color:var(--border);background:var(--surface);color:var(--primary)}
.scratch-actions-v259{gap:5px}
.scratch-status-v259{min-width:48px;font-size:11px;color:var(--muted2)}
.scratch-action-v259{height:34px;padding:0 9px;border-radius:7px;font-size:12px;font-weight:680}
.scratch-action-v259.organize{background:color-mix(in srgb,var(--primary) 6%,var(--surface));border-color:color-mix(in srgb,var(--primary) 30%,var(--border))}
.scratch-editor-v259{padding-top:22px;padding-bottom:64px;line-height:1.72}
.scratch-editor-v259::selection{background:color-mix(in srgb,var(--primary) 20%,transparent)}
@media(max-width:900px){body.scratch-mode-v2510 .search-wrap{display:none!important}.scratch-bar-v259{min-height:46px;padding:5px 7px}.scratch-tab-v259{height:34px}.scratch-actions-v259{gap:4px}.scratch-action-v259{height:32px}.scratch-editor-v259{padding-top:18px}}
'''
if marker not in c: css.write_text((c.rstrip()+override).rstrip()+'\n',encoding='utf-8')

js=root/'public/assets/scratch-tabs.js'; s=js.read_text(encoding='utf-8')
old="button.innerHTML='<span>临时</span><strong aria-hidden=\"true\">＋</strong><b></b>';button.title='临时页签工作台 · 自动保存';button.setAttribute('aria-label','打开临时页签工作台');\n      button.addEventListener('click',()=>openWorkspace(false));"
new="button.innerHTML='<span>临时</span><b></b>';button.title='打开临时页签工作台';button.setAttribute('aria-label','打开临时页签工作台');button.setAttribute('aria-pressed','false');\n      button.addEventListener('click',()=>workspace?exitWorkspace():openWorkspace(false));"
assert old in s; s=s.replace(old,new,1)
anchor='  function renderEditor(){\n'
helper="""  function updateActiveTabTitle(){
    if(!workspace)return;const tab=current();if(!tab)return;const btn=workspace.querySelector('[data-scratch-tab="'+Number(tab.id)+'"]');if(!btn)return;btn.title=tab.title;const label=btn.querySelector('.scratch-tab-title-v259');if(label)label.textContent=tab.title;
  }

"""
assert anchor in s; s=s.replace(anchor,helper+anchor,1)
old="const tab=current();if(!tab)return;tab.content=editor.value;tab.title=deriveTitle(tab.content,tab.id);tab.cursor_pos=editor.selectionStart||0;tab.scroll_top=editor.scrollTop||0;dirty=true;status('保存中…','saving');renderTabs();clearTimeout(saveTimer);saveTimer=setTimeout(()=>flushSave(false),480);"
new="const tab=current();if(!tab)return;tab.content=editor.value;tab.title=deriveTitle(tab.content,tab.id);tab.cursor_pos=editor.selectionStart||0;tab.scroll_top=editor.scrollTop||0;dirty=true;status('保存中…','saving');updateActiveTabTitle();clearTimeout(saveTimer);saveTimer=setTimeout(()=>flushSave(false),480);"
assert old in s; s=s.replace(old,new,1)
s=s.replace("status('已自动保存');","status('已保存');")
old='<div class="scratch-actions-v259"><span class="scratch-status-v259" data-scratch-status></span><button type="button" class="scratch-action-v259" data-scratch-recent><span>最近关闭</span> ↶</button><button type="button" class="scratch-action-v259 organize" data-scratch-organize>整理</button><button type="button" class="scratch-action-v259" data-scratch-exit><span>返回资料库</span> ←</button></div></div>\''
new='<div class="scratch-actions-v259"><span class="scratch-status-v259" data-scratch-status></span><button type="button" class="scratch-action-v259" data-scratch-recent title="最近关闭的临时页签">最近关闭</button><button type="button" class="scratch-action-v259 organize" data-scratch-organize>整理</button><button type="button" class="scratch-action-v259" data-scratch-exit title="返回 VF Library">返回</button></div></div>\''
assert old in s; s=s.replace(old,new,1)
old="document.body.insertAdjacentHTML('beforeend',workspaceMarkup());workspace=document.querySelector('#scratchWorkspaceV259');\n    storage.set(LAST_OPEN_KEY,'1');"
new="document.body.insertAdjacentHTML('beforeend',workspaceMarkup());workspace=document.querySelector('#scratchWorkspaceV259');\n    document.body.classList.add('scratch-mode-v2510');document.querySelector('#scratchLaunchV259')?.setAttribute('aria-pressed','true');\n    storage.set(LAST_OPEN_KEY,'1');"
assert old in s; s=s.replace(old,new,1)
old="workspace.querySelector('[data-scratch-exit]').addEventListener('click',exitWorkspace);workspace.querySelector('[data-scratch-recent]').addEventListener('click',toggleRecent);workspace.querySelector('[data-scratch-organize]').addEventListener('click',openOrganize);\n    editor=workspace.querySelector('[data-scratch-editor]');"
new="workspace.querySelector('[data-scratch-exit]').addEventListener('click',exitWorkspace);workspace.querySelector('[data-scratch-recent]').addEventListener('click',toggleRecent);workspace.querySelector('[data-scratch-organize]').addEventListener('click',openOrganize);\n    const tabsScroll=workspace.querySelector('.scratch-tabs-scroll-v259');if(tabsScroll)tabsScroll.addEventListener('wheel',event=>{if(Math.abs(event.deltaY)<=Math.abs(event.deltaX)||tabsScroll.scrollWidth<=tabsScroll.clientWidth)return;event.preventDefault();tabsScroll.scrollLeft+=event.deltaY;},{passive:false});\n    editor=workspace.querySelector('[data-scratch-editor]');"
assert old in s; s=s.replace(old,new,1)
old="async function exitWorkspace(){const ok=await flushSave(false);if(!ok)return;storage.set(LAST_OPEN_KEY,'0');workspace.remove();workspace=null;editor=null;closeFloating();}"
new="async function exitWorkspace(){const ok=await flushSave(false);if(!ok)return;storage.set(LAST_OPEN_KEY,'0');workspace.remove();workspace=null;editor=null;document.body.classList.remove('scratch-mode-v2510');document.querySelector('#scratchLaunchV259')?.setAttribute('aria-pressed','false');closeFloating();}"
assert old in s; s=s.replace(old,new,1)
js.write_text(s,encoding='utf-8')

b=root/'public/assets/v254-common-branding.js'; t=b.read_text(encoding='utf-8'); assert "||'2.5.9';" in t; b.write_text(t.replace("||'2.5.9';","||'2.5.10';",1),encoding='utf-8')
PY

node --check public/assets/scratch-tabs.js
node --check public/assets/v254-common-branding.js
python3 scripts/generate-source-manifest.py >/dev/null
python3 scripts/repository-gates.py
git diff --check
test "$(cat VERSION)" = 2.5.10
test "$(jq -r .version SOURCE_MANIFEST.json)" = 2.5.10
echo SOURCE_PATCH_AND_GATES=PASS

ROOT="$RUNNER_TEMP/p02-v2510"; SITE="$ROOT/site"; NODE="$ROOT/node"; mkdir -p "$SITE" "$NODE"
bash scripts/build-deploy-tree.sh "$SITE" >/dev/null
test "$(cat "$SITE/VERSION.txt")" = 2.5.10
PW='P02-V2510-Scratch-UXUI!'; PORT=18310
php -S 127.0.0.1:$PORT -t "$SITE" >"$ROOT/server.log" 2>&1 & PID=$!
trap 'kill $PID 2>/dev/null || true' EXIT
for _ in $(seq 1 80); do curl -fsS "http://127.0.0.1:$PORT/setup.php" >/dev/null 2>&1 && break; sleep .25; done
curl -fsS -c "$ROOT/c" "http://127.0.0.1:$PORT/setup.php" > "$ROOT/setup"
TOKEN=$(python3 - "$ROOT/setup" <<'PY'
import re,html,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="setup_csrf" value="([^"]+)"',s);assert m;print(html.unescape(m.group(1)))
PY
)
test "$(curl -sS -o /dev/null -w '%{http_code}' -b "$ROOT/c" -c "$ROOT/c" -H "Origin: http://127.0.0.1:$PORT" --data-urlencode "setup_csrf=$TOKEN" --data-urlencode "password=$PW" --data-urlencode "password_confirm=$PW" "http://127.0.0.1:$PORT/setup.php")" = 303
cd "$NODE"; npm init -y >/dev/null 2>&1; npm install --no-audit --no-fund puppeteer-core@24.16.0 >/dev/null 2>&1
CHROME=$(command -v google-chrome-stable || command -v google-chrome || command -v chromium || true); test -n "$CHROME"
cat > "$NODE/test.mjs" <<'JS'
import puppeteer from 'puppeteer-core';
const [url,password,chrome]=process.argv.slice(2);
const browser=await puppeteer.launch({headless:true,executablePath:chrome,args:['--no-sandbox','--disable-dev-shm-usage']});
const page=await browser.newPage();await page.setViewport({width:1365,height:768});
await page.goto(url,{waitUntil:'networkidle0'});
await page.evaluate(async password=>{const r=await fetch('/api.php?action=login',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({password})});if(!r.ok)throw new Error('login '+r.status);},password);
await page.reload({waitUntil:'networkidle0'});await page.waitForSelector('#scratchLaunchV259',{visible:true,timeout:12000});
const launch=await page.$eval('#scratchLaunchV259',el=>el.innerText.trim());if(/[+＋]/.test(launch))throw new Error('launcher plus remains '+launch);
await page.click('#scratchLaunchV259');await page.waitForSelector('#scratchWorkspaceV259 [data-scratch-editor]:not([disabled])',{timeout:10000});
if(!(await page.$eval('body',el=>el.classList.contains('scratch-mode-v2510'))))throw new Error('immersive class missing');
for(const sel of ['.search-wrap','.workspace-top-controls','#addContentSplit']){const state=await page.evaluate(sel=>{const el=document.querySelector(sel);return el?getComputedStyle(el).display:null;},sel);if(state!==null&&state!=='none')throw new Error(sel+' still visible');}
let editor=await page.$('[data-scratch-editor]');await editor.type('第一个临时页\n连续输入体验',{delay:8});await page.waitForFunction(()=>document.querySelector('[data-scratch-status]')?.textContent.trim()==='已保存',{timeout:10000});
for(let i=0;i<8;i++){await page.click('[data-scratch-add]');editor=await page.$('[data-scratch-editor]');await editor.type('临时页 '+(i+2)+' '+('内容'.repeat(8)),{delay:1});await page.waitForTimeout(90);}await page.waitForTimeout(700);
const count=await page.$$eval('[data-scratch-tab]',els=>els.length);if(count<9)throw new Error('multi tabs '+count);
const barHeight=await page.$eval('.scratch-bar-v259',el=>el.getBoundingClientRect().height);if(barHeight>52)throw new Error('bar too tall '+barHeight);
const inactiveOpacity=await page.$eval('.scratch-tab-v259:not(.active) .scratch-tab-close-v259',el=>Number(getComputedStyle(el).opacity));if(inactiveOpacity>0.05)throw new Error('inactive close noisy');
const actions=await page.$eval('.scratch-actions-v259',el=>el.innerText);if(actions.includes('返回资料库')||!actions.includes('最近关闭')||!actions.includes('整理')||!actions.includes('返回'))throw new Error('action labels');
await page.click('[data-scratch-exit]');await page.waitForFunction(()=>!document.querySelector('#scratchWorkspaceV259'));if(await page.$eval('body',el=>el.classList.contains('scratch-mode-v2510')))throw new Error('mode leaked');
await page.setViewport({width:390,height:844});await page.click('#scratchLaunchV259');await page.waitForSelector('#scratchWorkspaceV259');await page.waitForTimeout(250);const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1);if(overflow)throw new Error('mobile overflow');
await browser.close();
console.log('SCRATCH_V2510_REAL_BROWSER_UX_UI=PASS');
console.log('IMMERSIVE_HEADER_NOISE_REDUCTION=PASS');
console.log('COMPACT_TABS_AND_ACTIONS=PASS');
console.log('AUTOSAVE_LABEL_AND_MULTI_TAB=PASS');
console.log('MOBILE_OVERFLOW=PASS');
JS
node "$NODE/test.mjs" "http://127.0.0.1:$PORT/" "$PW" "$CHROME"
cd - >/dev/null
php "$SITE/cli/verify.php" | jq -e '.ok==true and .version=="2.5.10" and .schema_version==2401 and .integrity=="ok" and .foreign_key_errors==0' >/dev/null
echo FRESH_INSTALL_SQLITE=PASS

# Push only the verified private candidate.
git config user.name 'VF Runner'
git config user.email 'vf-runner@users.noreply.github.com'
git checkout -b feature/v2.5.10-scratch-uaui
git add VERSION CHANGELOG.md SOURCE_MANIFEST.json SOURCE_MANIFEST.txt public/assets/scratch-tabs.css public/assets/scratch-tabs.js public/assets/v254-common-branding.js
git commit -m 'VF Library V2.5.10 · Scratch Tabs UX UI refinement'
git remote set-url origin "https://x-access-token:${WRITE_TOKEN}@github.com/llhzx2018/vf-library.git"
git push origin HEAD:refs/heads/feature/v2.5.10-scratch-uaui
echo "CANDIDATE_SHA=$(git rev-parse HEAD)"
echo PRIVATE_BRANCH_PUSH=PASS
echo PRODUCTION_WRITE=NO
