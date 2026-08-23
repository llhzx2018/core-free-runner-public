#!/usr/bin/env python3
from pathlib import Path
import re

p=Path('public/assets/scratch-tabs.js')
s=p.read_text(encoding='utf-8')

anchor="  let saving=false;\n  let autoOpened=false;"
replacement="  let saving=false;\n  let savePromise=null;\n  let editRevision=0;\n  let autoOpened=false;"
if anchor not in s:
    raise SystemExit('save barrier state anchor missing')
s=s.replace(anchor,replacement,1)

old="  function onInput(){\n    const tab=current();if(!tab)return;tab.content=editor.value;"
new="  function onInput(){\n    const tab=current();if(!tab)return;editRevision++;tab.content=editor.value;"
if old not in s:
    raise SystemExit('onInput anchor missing')
s=s.replace(old,new,1)

pattern=r"  async function flushSave\(quiet\)\{.*?\n  \}\n\n  async function createTab"
match=re.search(pattern,s,flags=re.S)
if not match:
    raise SystemExit('flushSave block missing')
new_block="""  async function flushSave(quiet){
    clearTimeout(saveTimer);saveTimer=null;
    if(saving&&savePromise){
      const ok=await savePromise;
      if(!ok)return false;
      return dirty?flushSave(quiet):true;
    }
    if(!dirty)return true;
    const tab=current();if(!tab)return true;
    rememberCursor();
    const tabId=Number(tab.id),revision=editRevision;
    const payload={id:tab.id,content:tab.content,cursor_pos:tab.cursor_pos||0,scroll_top:tab.scroll_top||0};
    saving=true;
    savePromise=(async()=>{
      try{
        const data=await request('save',{method:'POST',body:payload});const saved=data.tab||tab;
        const index=snapshot.open.findIndex(t=>Number(t.id)===tabId);
        const unchanged=editRevision===revision&&Number(activeId)===tabId;
        if(index>=0&&unchanged)snapshot.open[index]={...snapshot.open[index],...saved};
        dirty=!unchanged;
        status(dirty?'保存中…':'已保存',dirty?'saving':'');renderTabs();return true;
      }
      catch(error){status('保存失败','failed');if(!quiet)showNotice(error.message||'自动保存失败');return false;}
      finally{saving=false;savePromise=null;}
    })();
    const ok=await savePromise;
    if(!ok)return false;
    return dirty?flushSave(quiet):true;
  }

  async function createTab"""
s=s[:match.start()]+new_block+s[match.end():]
p.write_text(s,encoding='utf-8')
print('SCRATCH_SAVE_BARRIER_PATCH=APPLIED')
