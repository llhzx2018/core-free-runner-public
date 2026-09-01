from pathlib import Path

page=Path('src/links-admin.php')
js_path=Path('src/assets/links-admin.js')
css_path=Path('src/assets/admin-pages.css')

php=page.read_text(encoding='utf-8')
anchor='''    <div class="vf-batchbar" id="batchBar"><strong id="batchCount">已选择 0 项</strong><?php if($pendingView):?><button class="btn" data-bulk="organized" data-active-only>仅标记已整理</button><button class="btn primary" data-bulk="move" data-active-only>归类并完成</button><?php else:?><button class="btn" data-bulk="pending" data-active-only>移入待整理</button><button class="btn" data-bulk="organized" data-active-only>标记已整理</button><button class="btn" data-bulk="move" data-active-only>移动分类</button><?php endif;?><button class="btn" data-bulk="archive" data-active-only>归档</button><button class="btn danger" data-bulk="delete" data-active-only>移入回收站</button><button class="btn primary" data-bulk="restore" data-retired-only hidden>恢复所选</button></div>'''
insert=anchor+'''\n    <div class="vf-inline-undo" id="linkUndo" hidden role="status" aria-live="polite"><span id="linkUndoCopy">网址已移入回收站。</span><div><button class="btn primary" id="undoDelete" type="button">撤销</button><button class="btn" id="dismissUndo" type="button">关闭</button></div></div>'''
if anchor not in php: raise SystemExit('batchbar anchor missing')
php=php.replace(anchor,insert,1)
page.write_text(php,encoding='utf-8')

js=js_path.read_text(encoding='utf-8')
old="""const $=s=>document.querySelector(s),$$=s=>Array.from(document.querySelectorAll(s));const csrf=($('meta[name=\"csrf-token\"]')||{}).content||'';let data={categories:[],links:[],lifecycleLinks:[]},page=1,size=50,selected=new Set();"""
new="""const $=s=>document.querySelector(s),$$=s=>Array.from(document.querySelectorAll(s));const csrf=($('meta[name=\"csrf-token\"]')||{}).content||'';let data={categories:[],links:[],lifecycleLinks:[]},page=1,size=50,selected=new Set(),undoIds=[],undoTimer=null;"""
if old not in js: raise SystemExit('state anchor missing')
js=js.replace(old,new,1)
anchor="""async function restoreIds(ids){if(!ids.length)return;try{await api('links_bulk_restore',{method:'POST',body:{ids}});selected.clear();await load();await loadLifecycle(currentState());renderLinks();toast('网址已恢复')}catch(e){toast(e.message,true)}}"""
helpers=r'''function hideDeleteUndo(){if(undoTimer){clearTimeout(undoTimer);undoTimer=null}undoIds=[];let bar=$('#linkUndo');if(bar)bar.hidden=true}
function showDeleteUndo(ids){undoIds=ids.map(Number).filter(Boolean);if(!undoIds.length)return;let bar=$('#linkUndo'),copy=$('#linkUndoCopy');if(!bar||!copy)return;if(undoTimer)clearTimeout(undoTimer);copy.textContent='已将 '+undoIds.length+' 个网址移入回收站。现在可以直接撤销；之后仍可在回收站恢复。';bar.hidden=false;undoTimer=setTimeout(hideDeleteUndo,30000)}
async function undoDelete(){let ids=undoIds.slice();if(!ids.length)return;let button=$('#undoDelete');if(button){button.disabled=true;button.textContent='恢复中…'}try{await api('links_bulk_restore',{method:'POST',body:{ids}});hideDeleteUndo();selected.clear();await load();toast('已撤销移入回收站')}catch(e){toast(e.message,true)}finally{if(button){button.disabled=false;button.textContent='撤销'}}}
'''+anchor
if anchor not in js: raise SystemExit('restore anchor missing')
js=js.replace(anchor,helpers,1)
old="""async function bulk(action){let ids=Array.from(selected);if(!ids.length)return;if(action==='restore'){await restoreIds(ids);return}if(action==='move'){openMoveDialog();return}if(['delete','archive'].includes(action)&&!confirm(action==='delete'?'所选网址会进入回收站，确认继续？':'所选网址会进入归档，确认继续？'))return;await api('links_bulk',{method:'POST',body:{ids,action}});selected.clear();await load();toast('批量操作完成')}"""
new="""async function bulk(action){let ids=Array.from(selected);if(!ids.length)return;if(action==='restore'){await restoreIds(ids);return}if(action==='move'){openMoveDialog();return}if(['delete','archive'].includes(action)&&!confirm(action==='delete'?'所选网址会进入回收站，确认继续？':'所选网址会进入归档，确认继续？'))return;await api('links_bulk',{method:'POST',body:{ids,action}});selected.clear();await load();if(action==='delete'){showDeleteUndo(ids);return}toast('批量操作完成')}"""
if old not in js: raise SystemExit('bulk anchor missing')
js=js.replace(old,new,1)
old="""$$('[data-bulk]').forEach(b=>b.onclick=()=>bulk(b.dataset.bulk).catch(e=>toast(e.message,true)));$('#moveConfirm').onclick=()=>confirmMove();"""
new="""$$('[data-bulk]').forEach(b=>b.onclick=()=>bulk(b.dataset.bulk).catch(e=>toast(e.message,true)));$('#moveConfirm').onclick=()=>confirmMove();$('#undoDelete').onclick=()=>undoDelete();$('#dismissUndo').onclick=hideDeleteUndo;"""
if old not in js: raise SystemExit('binding anchor missing')
js=js.replace(old,new,1)
js_path.write_text(js.rstrip()+'\n',encoding='utf-8')

styles=css_path.read_text(encoding='utf-8').rstrip()+r'''

/* links-admin.php — deletion uses the existing recycle-bin restore contract and exposes undo inline, not as an overlay toast. */
body[data-vf-page="links-admin"] .vf-inline-undo{margin:0 0 10px;padding:9px 10px;display:flex;align-items:center;justify-content:space-between;gap:12px;border:1px solid color-mix(in srgb,var(--vf-admin-warn) 30%,var(--vf-admin-border));border-radius:9px;background:color-mix(in srgb,var(--vf-admin-warn) 7%,var(--vf-admin-surface));color:var(--vf-admin-text)}
body[data-vf-page="links-admin"] .vf-inline-undo[hidden]{display:none}
body[data-vf-page="links-admin"] .vf-inline-undo>span{min-width:0;font-size:11.5px;line-height:1.45}
body[data-vf-page="links-admin"] .vf-inline-undo>div{display:flex;align-items:center;gap:6px;flex:0 0 auto}
body[data-vf-page="links-admin"] .vf-inline-undo .btn{min-height:32px!important;padding:5px 9px!important}
@media(max-width:600px){body[data-vf-page="links-admin"] .vf-inline-undo{align-items:flex-start;flex-direction:column}body[data-vf-page="links-admin"] .vf-inline-undo>div{width:100%}body[data-vf-page="links-admin"] .vf-inline-undo .btn{flex:1}}
'''
css_path.write_text(styles.rstrip()+'\n',encoding='utf-8')
