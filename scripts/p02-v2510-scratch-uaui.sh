#!/usr/bin/env bash
set -Eeuo pipefail
cd product

python3 - <<'PY'
from pathlib import Path
import json, hashlib, subprocess
root=Path('.')
(root/'VERSION').write_text('2.5.10\n',encoding='utf-8')
changelog=root/'CHANGELOG.md'; old=changelog.read_text(encoding='utf-8')
entry='''## V2.5.10 · Scratch Tabs UX/UI 精修\n\n- 临时工作台进入沉浸模式，隐藏与临时记录无关的搜索、文档工具和新增入口。\n- 顶部“临时 + 数量”收敛为“临时 数量”，避免入口语义误导。\n- 页签栏改为更接近桌面 Notepad 的紧凑标签形态，并隐藏横向滚动条。\n- 关闭按钮仅在当前或悬停页签明显显示；操作区收紧为“最近关闭 / 整理 / 返回”。\n- 自动保存状态由“已自动保存”收敛为“已保存”。\n- 输入时只更新当前页签标题，不再每个按键重建整条 Tab DOM。\n- 页签区域支持鼠标滚轮横向浏览，多 TAB 场景更顺手。\n- Schema 2401 不变，无 Migration。\n\n'''
if not old.startswith('## V2.5.10'): changelog.write_text(entry+old,encoding='utf-8')

css=root/'public/assets/scratch-tabs.css'; c=css.read_text(encoding='utf-8')
marker='/* V2.5.10 · Scratch Tabs UX/UI refinement */'
override=r'''

/* V2.5.10 · Scratch Tabs UX/UI refinement */
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
if marker not in c: css.write_text(c.rstrip()+override+'\n',encoding='utf-8')

js=root/'public/assets/scratch-tabs.js'; s=js.read_text(encoding='utf-8')
s=s.replace("button.innerHTML='<span>临时</span><strong aria-hidden=\"true\">＋</strong><b></b>';button.title='临时页签工作台 · 自动保存';button.setAttribute('aria-label','打开临时页签工作台');\n      button.addEventListener('click',()=>openWorkspace(false));", "button.innerHTML='<span>临时</span><b></b>';button.title='打开临时页签工作台';button.setAttribute('aria-label','打开临时页签工作台');button.setAttribute('aria-pressed','false');\n      button.addEventListener('click',()=>workspace?exitWorkspace():openWorkspace(false));")
anchor="  function renderEditor(){\n"
helper="""  function updateActiveTabTitle(){\n    if(!workspace)return;const tab=current();if(!tab)return;const btn=workspace.querySelector('[data-scratch-tab=\"'+Number(tab.id)+'\"]');if(!btn)return;btn.title=tab.title;const label=btn.querySelector('.scratch-tab-title-v259');if(label)label.textContent=tab.title;\n  }\n\n"""
if helper.strip() not in s:
    assert anchor in s; s=s.replace(anchor,helper+anchor,1)
old_input="const tab=current();if(!tab)return;tab.content=editor.value;tab.title=deriveTitle(tab.content,tab.id);tab.cursor_pos=editor.selectionStart||0;tab.scroll_top=editor.scrollTop||0;dirty=true;status('保存中…','saving');renderTabs();clearTimeout(saveTimer);saveTimer=setTimeout(()=>flushSave(false),480);"
new_input="const tab=current();if(!tab)return;tab.content=editor.value;tab.title=deriveTitle(tab.content,tab.id);tab.cursor_pos=editor.selectionStart||0;tab.scroll_top=editor.scrollTop||0;dirty=true;status('保存中…','saving');updateActiveTabTitle();clearTimeout(saveTimer);saveTimer=setTimeout(()=>flushSave(false),480);"
assert old_input in s; s=s.replace(old_input,new_input,1)
s=s.replace("status('已自动保存');","status('已保存');")
old_actions="<div class=\"scratch-actions-v259\"><span class=\"scratch-status-v259\" data-scratch-status></span><button type=\"button\" class=\"scratch-action-v259\" data-scratch-recent><span>最近关闭</span> ↶</button><button type=\"button\" class=\"scratch-action-v259 organize\" data-scratch-organize>整理</button><button type=\"button\" class=\"scratch-action-v259\" data-scratch-exit><span>返回资料库</span> ←</button></div></div>'"
new_actions="<div class=\"scratch-actions-v259\"><span class=\"scratch-status-v259\" data-scratch-status></span><button type=\"button\" class=\"scratch-action-v259\" data-scratch-recent title=\"最近关闭的临时页签\">最近关闭</button><button type=\"button\" class=\"scratch-action-v259 organize\" data-scratch-organize>整理</button><button type=\"button\" class=\"scratch-action-v259\" data-scratch-exit title=\"返回 VF Library\">返回</button></div></div>'"
assert old_actions in s; s=s.replace(old_actions,new_actions,1)
open_anchor="document.body.insertAdjacentHTML('beforeend',workspaceMarkup());workspace=document.querySelector('#scratchWorkspaceV259');\n    storage.set(LAST_OPEN_KEY,'1');"
open_new="document.body.insertAdjacentHTML('beforeend',workspaceMarkup());workspace=document.querySelector('#scratchWorkspaceV259');\n    document.body.classList.add('scratch-mode-v2510');document.querySelector('#scratchLaunchV259')?.setAttribute('aria-pressed','true');\n    storage.set(LAST_OPEN_KEY,'1');"
assert open_anchor in s; s=s.replace(open_anchor,open_new,1)
wire_anchor="workspace.querySelector('[data-scratch-exit]').addEventListener('click',exitWorkspace);workspace.querySelector('[data-scratch-recent]').addEventListener('click',toggleRecent);workspace.querySelector('[data-scratch-organize]').addEventListener('click',openOrganize);\n    editor=workspace.querySelector('[data-scratch-editor]');"
wire_new="workspace.querySelector('[data-scratch-exit]').addEventListener('click',exitWorkspace);workspace.querySelector('[data-scratch-recent]').addEventListener('click',toggleRecent);workspace.querySelector('[data-scratch-organize]').addEventListener('click',openOrganize);\n    const tabsScroll=workspace.querySelector('.scratch-tabs-scroll-v259');if(tabsScroll)tabsScroll.addEventListener('wheel',event=>{if(Math.abs(event.deltaY)<=Math.abs(event.deltaX))return;if(tabsScroll.scrollWidth<=tabsScroll.clientWidth)return;event.preventDefault();tabsScroll.scrollLeft+=event.deltaY;},{passive:false});\n    editor=workspace.querySelector('[data-scratch-editor]');"
assert wire_anchor in s; s=s.replace(wire_anchor,wire_new,1)
old_exit="async function exitWorkspace(){const ok=await flushSave(false);if(!ok)return;storage.set(LAST_OPEN_KEY,'0');workspace.remove();workspace=null;editor=null;closeFloating();}"
new_exit="async function exitWorkspace(){const ok=await flushSave(false);if(!ok)return;storage.set(LAST_OPEN_KEY,'0');workspace.remove();workspace=null;editor=null;document.body.classList.remove('scratch-mode-v2510');document.querySelector('#scratchLaunchV259')?.setAttribute('aria-pressed','false');closeFloating();}"
assert old_exit in s; s=s.replace(old_exit,new_exit,1)
js.write_text(s,encoding='utf-8')
branding=root/'public/assets/v254-common-branding.js'; b=branding.read_text(encoding='utf-8').replace("||'2.5.9';","||'2.5.10';"); branding.write_text(b,encoding='utf-8')

tmp=root/'build'/'manifest-v2510'; subprocess.run(['bash','scripts/build-deploy-tree.sh',str(tmp)],check=True,stdout=subprocess.DEVNULL)
entries=[]
for p in sorted(x for x in tmp.rglob('*') if x.is_file()):
    full=p.relative_to(tmp).as_posix()
    repo='VERSION' if full=='VERSION.txt' else ('src/'+full if full.startswith(('app/','cli/')) else 'public/'+full)
    rp=root/repo; data=p.read_bytes(); rdata=rp.read_bytes()
    if data!=rdata: raise SystemExit(f'mapping mismatch {full}->{repo}')
    h=hashlib.sha256(data).hexdigest()
    entries.append({'full_path':full,'repo_path':repo,'bytes':len(data),'sha256':h,'repo_sha256':h})
manifest={'project':'P02 · VF Library','version':'2.5.10','schema':2401,'source_baseline_full_sha256':'PENDING_FORMAL_CANDIDATE_ARTIFACT','mapping_contract':'Each declared runtime source file must exist exactly once at repo_path; hashes bind the Git-native V2.5.10 candidate deploy tree. Formal release identity is not assigned by this candidate manifest.','runtime_source_file_count':len(entries),'entries':entries}
(root/'SOURCE_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
subprocess.run(['rm','-rf',str(tmp)],check=True)
PY

node --check public/assets/scratch-tabs.js
node --check public/assets/v254-common-branding.js
python3 scripts/repository-gates.py
git diff --check
test "$(cat VERSION)" = 2.5.10
test "$(jq -r .version SOURCE_MANIFEST.json)" = 2.5.10
echo SOURCE_PATCH_AND_GATES=PASS

ROOT="$RUNNER_TEMP/v2510"; SITE="$ROOT/site"; mkdir -p "$SITE"; bash scripts/build-deploy-tree.sh "$SITE" >/dev/null
PW="P02-V2510-${GITHUB_RUN_ID}!"; PORT=18310
php -S 127.0.0.1:$PORT -t "$SITE" >/dev/null 2>&1 & PID=$!
trap 'kill $PID 2>/dev/null || true' EXIT
for _ in $(seq 1 80);do curl -fsS "http://127.0.0.1:$PORT/setup.php" >/dev/null 2>&1&&break;sleep .25;done
npm init -y >/dev/null 2>&1
npm install --no-save playwright@1.55.0 >/dev/null 2>&1
npx playwright install chromium >/dev/null
cat > "$RUNNER_TEMP/check.mjs" <<'JS'
import { chromium } from 'playwright';
const base=process.env.BASE,pw=process.env.PW;const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1365,height:768}});await page.goto(base+'/setup.php');
await page.locator('input[name="password"]').fill(pw);await page.locator('input[name="password_confirm"]').fill(pw);await page.locator('button[type="submit"]').click();await page.waitForTimeout(350);await page.goto(base+'/');
await page.waitForSelector('#scratchLaunchV259',{timeout:12000});const lt=(await page.locator('#scratchLaunchV259').innerText()).trim();if(/[+＋]/.test(lt))throw new Error('launcher plus remains '+lt);
await page.locator('#scratchLaunchV259').click();await page.waitForSelector('#scratchWorkspaceV259');if(!(await page.locator('body').evaluate(el=>el.classList.contains('scratch-mode-v2510'))))throw new Error('immersive class missing');
for(const sel of ['.search-wrap','.workspace-top-controls','#addContentSplit']){if(await page.locator(sel).evaluate(el=>getComputedStyle(el).display)!=='none')throw new Error(sel+' still visible');}
const editor=page.locator('[data-scratch-editor]');await editor.fill('第一个临时页\n继续输入测试');await page.waitForTimeout(750);if((await page.locator('[data-scratch-status]').innerText()).trim()!=='已保存')throw new Error('status');
for(let i=0;i<8;i++){await page.locator('[data-scratch-add]').click();await editor.fill('临时页 '+(i+2)+' '+('内容'.repeat(8)));await page.waitForTimeout(70);}await page.waitForTimeout(800);
const bh=await page.locator('.scratch-bar-v259').evaluate(el=>el.getBoundingClientRect().height);if(bh>52)throw new Error('bar '+bh);if(await page.locator('.scratch-tab-v259').count()<9)throw new Error('tabs');
const op=Number(await page.locator('.scratch-tab-v259:not(.active)').first().locator('.scratch-tab-close-v259').evaluate(el=>getComputedStyle(el).opacity));if(op>0.05)throw new Error('close noise');
const labels=await page.locator('.scratch-actions-v259').innerText();if(labels.includes('返回资料库')||!labels.includes('返回'))throw new Error('labels');
await page.locator('[data-scratch-exit]').click();if(await page.locator('#scratchWorkspaceV259').count())throw new Error('exit');
const mobile=await browser.newPage({viewport:{width:430,height:820}});await mobile.goto(base+'/');await mobile.waitForSelector('#scratchLaunchV259');await mobile.locator('#scratchLaunchV259').click();await mobile.waitForSelector('#scratchWorkspaceV259');const overflow=await mobile.evaluate(()=>document.documentElement.scrollWidth-window.innerWidth);if(overflow>1)throw new Error('mobile overflow '+overflow);await browser.close();console.log('SCRATCH_V2510_REAL_BROWSER_UX_UI=PASS');
JS
BASE="http://127.0.0.1:$PORT" PW="$PW" node "$RUNNER_TEMP/check.mjs"
php "$SITE/cli/verify.php" | jq -e '.ok==true and .version=="2.5.10" and .schema_version==2401 and .integrity=="ok" and .foreign_key_errors==0' >/dev/null
echo FRESH_INSTALL_SQLITE=PASS

# Push verified source to private product branch.
git config user.name 'VF Runner'; git config user.email 'vf-runner@users.noreply.github.com'; git checkout -b feature/v2.5.10-scratch-uaui
git add VERSION CHANGELOG.md SOURCE_MANIFEST.json public/assets/scratch-tabs.css public/assets/scratch-tabs.js public/assets/v254-common-branding.js
git commit -m 'VF Library V2.5.10 · Scratch Tabs UX UI refinement'
git remote set-url origin "https://x-access-token:${WRITE_TOKEN}@github.com/llhzx2018/vf-library.git"
git push origin HEAD:refs/heads/feature/v2.5.10-scratch-uaui
echo "CANDIDATE_SHA=$(git rev-parse HEAD)"
echo PRIVATE_BRANCH_PUSH=PASS
echo PRODUCTION_WRITE=NO
