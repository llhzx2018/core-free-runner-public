#!/usr/bin/env python3
from pathlib import Path
import re

p = Path('public/assets/scratch-tabs.js')
s = p.read_text(encoding='utf-8')

anchor = "  let autoOpened=false;\n  let noticeTimer=null;"
replacement = "  let autoOpened=false;\n  let openingPromise=null;\n  let noticeTimer=null;"
if anchor not in s:
    raise SystemExit('openingPromise anchor missing')
s = s.replace(anchor, replacement, 1)

stale = "autoOpened=true;setTimeout(()=>openWorkspace(true).catch(()=>{}),180);"
guarded = "autoOpened=true;setTimeout(()=>{if(storage.get(LAST_OPEN_KEY)==='1'&&!workspace)openWorkspace(true).catch(()=>{});},180);"
if stale not in s:
    raise SystemExit('stale auto-open timer anchor missing')
s = s.replace(stale, guarded, 1)

pattern = r"  async function openWorkspace\(auto,createNew\)\{.*?\n  \}\n\n  function rememberCursor"
match = re.search(pattern, s, flags=re.S)
if not match:
    raise SystemExit('openWorkspace function block missing')

new_block = """  async function openWorkspace(auto,createNew){
    if(workspace&&!workspace.isConnected)workspace=null;
    if(workspace){if(createNew)await createTab();return;}
    if(openingPromise){
      await openingPromise;
      if(createNew&&workspace)await createTab();
      return;
    }
    openingPromise=(async()=>{
      try{await session();await loadSnapshot();}
      catch(error){if(!auto)alert(error.message||'无法打开临时页签');return;}
      if(workspace&&workspace.isConnected)return;
      const existing=document.querySelector('#scratchWorkspaceV259');
      if(existing){workspace=existing;return;}
      const main=document.querySelector('#main');if(!main){if(!auto)alert('资料工作区尚未就绪。');return;}main.insertAdjacentHTML('beforeend',workspaceMarkup());workspace=document.querySelector('#scratchWorkspaceV259');
      document.body.classList.add('scratch-mode-v2510');document.querySelector('#scratchLaunchV259')?.setAttribute('aria-pressed','true');
      storage.set(LAST_OPEN_KEY,'1');
      workspace.querySelector('[data-scratch-add]').addEventListener('click',createTab);workspace.querySelector('[data-scratch-empty-add]').addEventListener('click',createTab);
      workspace.querySelector('[data-scratch-exit]').addEventListener('click',exitWorkspace);workspace.querySelector('[data-scratch-recent]').addEventListener('click',toggleRecent);workspace.querySelector('[data-scratch-organize]').addEventListener('click',openOrganize);
      const tabsScroll=workspace.querySelector('.scratch-tabs-scroll-v259');if(tabsScroll)tabsScroll.addEventListener('wheel',event=>{if(Math.abs(event.deltaY)<=Math.abs(event.deltaX)||tabsScroll.scrollWidth<=tabsScroll.clientWidth)return;event.preventDefault();tabsScroll.scrollLeft+=event.deltaY;},{passive:false});
      editor=workspace.querySelector('[data-scratch-editor]');
      editor.addEventListener('input',onInput);editor.addEventListener('scroll',()=>{const tab=current();if(tab)tab.scroll_top=editor.scrollTop;},{passive:true});editor.addEventListener('keyup',rememberCursor);editor.addEventListener('click',rememberCursor);editor.addEventListener('select',rememberCursor);
      let desired=Number(storage.get(ACTIVE_KEY)||0);if(!snapshot.open.some(t=>Number(t.id)===desired))desired=Number(snapshot.open[0]?.id||0);activeId=desired;
      if(createNew||(!activeId&&snapshot.open.length===0))await createTab();else{renderTabs();renderEditor();}
    })();
    try{await openingPromise;}finally{openingPromise=null;}
  }

  function rememberCursor"""

s = s[:match.start()] + new_block + s[match.end():]
p.write_text(s, encoding='utf-8')
print('SCRATCH_SINGLE_OPEN_PATCH=APPLIED')
