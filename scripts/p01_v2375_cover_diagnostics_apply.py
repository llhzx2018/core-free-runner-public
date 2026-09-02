from pathlib import Path

root = Path('product')
shell_path = root / 'src/app/FunctionalWorkspaceShell.php'
js_path = root / 'src/assets/workspace.js'
css_path = root / 'src/assets/surface-workspace.css'

shell = shell_path.read_text(encoding='utf-8')
start = shell.index('function vf_fw_render_watch_card')
head, tail = shell[:start], shell[start:]
needle = '  <span class="vf-asset-actions"><?php if($admin): ?>'
assert tail.count(needle) == 1, tail.count(needle)
replacement = '''  <?php if($admin): ?><span class="vf-cover-diagnostic" data-cover-diagnostic hidden></span><?php endif; ?>
  <span class="vf-asset-actions"><?php if($admin): ?><?php if($visual===''): ?><button type="button" class="vf-icon-button" data-cover-refresh-id="<?=(int)$asset['id']?>" aria-label="重新抓封面" title="重新抓封面">↻</button><?php endif; ?>'''
tail = tail.replace(needle, replacement, 1)
shell_path.write_text(head + tail, encoding='utf-8')

js = js_path.read_text(encoding='utf-8')
assert 'vf-cover-retry:v5:${id}' in js
js = js.replace('vf-cover-retry:v5:${id}', 'vf-cover-retry:v6:${id}', 1)

apply_start = js.index('  const applyAutoCover=(id,url)=>{')
refresh_start = js.index('  const refreshAutoCovers=async()=>{', apply_start)
open_panel = js.index('  const openPanel=', refresh_start)
new_cover_block = r'''  const coverDiagnostic=(id,message='')=>{
    const row=document.querySelector(`[data-asset-row="${id}"]`),el=row?.querySelector('[data-cover-diagnostic]'),button=row?.querySelector('[data-cover-refresh-id]');
    const text=String(message||'').trim().slice(0,260);
    if(el){el.textContent=text;el.hidden=!text}
    if(button)button.title=text?`重新抓封面：${text}`:'重新抓封面';
  };
  const applyAutoCover=(id,url)=>{
    const a=state.assets[String(id)];if(a)a.cover_url=url||'';
    if(!url)return;
    document.querySelectorAll(`[data-asset-row="${id}"] .vf-watch-poster,[data-asset-row="${id}"] .vf-asset-icon`).forEach(el=>{el.innerHTML=`<img src="${String(url).replace(/"/g,'&quot;')}" alt="" loading="lazy">`});
    const button=document.querySelector(`[data-asset-row="${id}"] [data-cover-refresh-id]`);if(button)button.hidden=true;coverDiagnostic(id,'');
  };
  const refreshCoverBatch=async(batch,manual=false)=>{
    const body=new FormData();body.set('csrf',state.csrf||'');body.set('ids',JSON.stringify(batch));
    let json={ok:false};
    try{
      const r=await fetch('resource-cover-refresh.php',{method:'POST',body,credentials:'same-origin',headers:{'X-Requested-With':'XMLHttpRequest'}});json=await r.json().catch(()=>({ok:false,error:'服务器返回了无效封面响应。'}));
      if(!r.ok||!json.ok)throw new Error(json.error||'自动封面抓取失败。');
      const seen=new Set();
      (json.results||[]).forEach(item=>{const id=Number(item.id||0),url=item?.cover?.url||'',error=String(item.error||'页面没有提供可用的封面图片。');if(!id)return;seen.add(id);if(manual)markCoverRetry(id,false);else markCoverRetry(id,!item.success);coverDiagnostic(id,item.success?'':error);if(item.success&&url)applyAutoCover(id,url)});
      batch.filter(id=>!seen.has(Number(id))).forEach(id=>{const message='服务器没有返回该资源的封面结果。';if(!manual)markCoverRetry(id,true);coverDiagnostic(id,message)});
      return json;
    }catch(err){const message=String(err?.message||'自动封面抓取失败。');batch.forEach(id=>{if(!manual)markCoverRetry(id,true);coverDiagnostic(id,message)});throw err}
  };
  const refreshAutoCovers=async()=>{
    const ids=Object.values(state.assets||{}).filter(a=>['channels','watch'].includes(String(a.surface||''))&&!a.cover_url&&!coverRetryBlocked(a.id)).map(a=>Number(a.id)).filter(Boolean);
    for(let i=0;i<ids.length;i+=2){const batch=ids.slice(i,i+2);try{await refreshCoverBatch(batch,false)}catch(_){}await new Promise(resolve=>setTimeout(resolve,250))}
  };
'''
js = js[:apply_start] + new_cover_block + js[open_panel:]

search_marker = "  const search=$('.vf-global-search input');"
assert search_marker in js
manual_handler = r'''  document.addEventListener('click',async e=>{
    const button=e.target.closest?.('[data-cover-refresh-id]');if(!button)return;
    e.preventDefault();e.stopPropagation();const id=Number(button.dataset.coverRefreshId||0);if(!id||button.disabled)return;
    button.disabled=true;markCoverRetry(id,false);coverDiagnostic(id,'正在重新抓取封面…');
    try{const json=await refreshCoverBatch([id],true),item=(json.results||[]).find(x=>Number(x.id||0)===id);if(item?.success){toast('封面已刷新。')}else{toast(String(item?.error||'封面刷新失败。'),'error')}}
    catch(err){toast(String(err?.message||'封面刷新失败。'),'error')}
    finally{button.disabled=false}
  });
'''
js = js.replace(search_marker, manual_handler + search_marker, 1)
js_path.write_text(js, encoding='utf-8')

css = css_path.read_text(encoding='utf-8')
watch_marker = '.vf-watch-card .vf-asset-actions{position:absolute;top:11px;right:11px;padding:2px;border-radius:7px;background:color-mix(in srgb,var(--ws-panel) 92%,transparent)}'
assert css.count(watch_marker) == 1
css_add = watch_marker + '.vf-cover-diagnostic{display:block;margin:2px 2px 5px;padding:5px 6px;border-radius:6px;background:color-mix(in srgb,#f59e0b 12%,var(--ws-panel));color:var(--ws-warning);font-size:10.5px;line-height:1.35;word-break:break-word}.vf-cover-diagnostic[hidden]{display:none}'
css = css.replace(watch_marker, css_add, 1)
css_path.write_text(css, encoding='utf-8')
