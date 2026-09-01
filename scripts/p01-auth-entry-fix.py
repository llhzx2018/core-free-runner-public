from pathlib import Path
import os

root = Path(os.environ['P01_ROOT'])
shell_path = root / 'src/app/FunctionalWorkspaceShell.php'
css_path = root / 'src/assets/workspace-rebaseline.css'
js_path = root / 'src/assets/auth-controls.js'

shell = shell_path.read_text(encoding='utf-8')
old = '''  <div class="vf-sidebar-bottom">\n    <?php if($admin): ?><a href="links-admin.php">☷ <span>资源管理</span></a><a href="settings.php">⚙ <span>系统设置</span></a><?php endif; ?>\n    <small>VF Start · V<?=vf_fw_h(VF_VERSION)?></small>\n  </div>\n</aside>\n'''
new = '''  <div class="vf-sidebar-bottom">\n    <?php if($admin): ?>\n      <a href="links-admin.php">☷ <span>资源管理</span></a>\n      <a href="settings.php">⚙ <span>系统设置</span></a>\n      <a href="#" data-vf-auth-logout>↪ <span>退出</span></a>\n    <?php else: ?>\n      <a href="#" data-vf-auth-login>↪ <span>登录</span></a>\n    <?php endif; ?>\n    <small>VF Start · V<?=vf_fw_h(VF_VERSION)?></small>\n  </div>\n</aside>\n<script src="<?=vf_fw_h(vf_asset_url('assets/auth-controls.js'))?>" defer></script>\n'''
if shell.count(old) != 1:
    raise SystemExit(f'FunctionalWorkspaceShell auth anchor mismatch: {shell.count(old)}')
shell = shell.replace(old, new)
shell_path.write_text(shell, encoding='utf-8')

js = r'''(()=>{
  const loginTrigger=document.querySelector('[data-vf-auth-login]');
  const logoutTrigger=document.querySelector('[data-vf-auth-logout]');
  if(!loginTrigger&&!logoutTrigger)return;

  const apiJson=async(action,options={})=>{
    const request={method:options.method||'GET',credentials:'same-origin',headers:{Accept:'application/json'}};
    if(options.body!==undefined){request.headers['Content-Type']='application/json';request.body=JSON.stringify(options.body)}
    if(options.csrf)request.headers['X-CSRF-Token']=options.csrf;
    const response=await fetch(`api.php?action=${encodeURIComponent(action)}`,request);
    const data=await response.json().catch(()=>({ok:false,error:'服务器返回了无效响应。'}));
    if(!response.ok||data.ok===false)throw new Error(data.error||`请求失败 (${response.status})`);
    return data;
  };

  const ensureDialog=()=>{
    let dialog=document.querySelector('[data-vf-auth-dialog]');
    if(dialog)return dialog;
    dialog=document.createElement('dialog');
    dialog.className='vf-auth-dialog';
    dialog.dataset.vfAuthDialog='1';
    dialog.innerHTML=`<form method="dialog" class="vf-auth-card" data-vf-auth-form>
      <header><div><strong>登录 VF Start</strong><small>登录后可查看私人内容并使用管理功能。</small></div><button type="button" data-vf-auth-close aria-label="关闭">×</button></header>
      <label><span>管理员密码</span><input type="password" name="password" autocomplete="current-password" required></label>
      <p data-vf-auth-error hidden></p>
      <footer><button type="button" data-vf-auth-close>取消</button><button type="submit" data-vf-auth-submit>登录</button></footer>
    </form>`;
    document.body.appendChild(dialog);
    dialog.querySelectorAll('[data-vf-auth-close]').forEach(button=>button.addEventListener('click',()=>dialog.close()));
    dialog.addEventListener('click',event=>{if(event.target===dialog)dialog.close()});
    const form=dialog.querySelector('[data-vf-auth-form]');
    form.addEventListener('submit',async event=>{
      event.preventDefault();
      const password=String(form.elements.password.value||'');
      const submit=form.querySelector('[data-vf-auth-submit]');
      const error=dialog.querySelector('[data-vf-auth-error]');
      error.hidden=true;error.textContent='';submit.disabled=true;submit.textContent='登录中…';
      try{
        await apiJson('login',{method:'POST',body:{password}});
        location.reload();
      }catch(err){
        error.textContent=err?.message||'登录失败。';error.hidden=false;submit.disabled=false;submit.textContent='登录';form.elements.password.focus();form.elements.password.select();
      }
    });
    return dialog;
  };

  loginTrigger?.addEventListener('click',event=>{
    event.preventDefault();
    const dialog=ensureDialog();
    if(typeof dialog.showModal==='function')dialog.showModal();else dialog.setAttribute('open','');
    setTimeout(()=>dialog.querySelector('input[name="password"]')?.focus(),20);
  });

  logoutTrigger?.addEventListener('click',async event=>{
    event.preventDefault();
    logoutTrigger.setAttribute('aria-busy','true');
    logoutTrigger.style.pointerEvents='none';
    try{
      let csrf='';
      const dataNode=document.getElementById('vf-workspace-data');
      if(dataNode){try{csrf=String(JSON.parse(dataNode.textContent||'{}').csrf||'')}catch(_){}}
      if(!csrf){const boot=await apiJson('bootstrap');csrf=String(boot.csrf||'')}
      if(!csrf)throw new Error('无法取得退出凭据，请刷新页面后重试。');
      await apiJson('logout',{method:'POST',body:{},csrf});
      location.reload();
    }catch(err){
      alert(err?.message||'退出失败，请刷新页面后重试。');
      logoutTrigger.removeAttribute('aria-busy');
      logoutTrigger.style.pointerEvents='';
    }
  });
})();
'''
js_path.write_text(js, encoding='utf-8')

css = css_path.read_text(encoding='utf-8')
marker = '/* P01 auth entry + login dialog · 2026-09-01 */'
if marker in css:
    raise SystemExit('auth css marker already exists')
css += r'''

/* P01 auth entry + login dialog · 2026-09-01 */
.vf-auth-dialog{width:min(390px,calc(100vw - 28px));padding:0;border:1px solid var(--ws-line-strong);border-radius:14px;background:var(--ws-panel);color:var(--ws-text);box-shadow:0 24px 70px rgba(15,23,42,.24)}
.vf-auth-dialog::backdrop{background:rgba(15,23,42,.38);backdrop-filter:blur(2px)}
.vf-auth-card{display:grid;gap:16px;padding:18px}
.vf-auth-card>header{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}
.vf-auth-card>header strong,.vf-auth-card>header small{display:block}.vf-auth-card>header strong{font-size:16px;color:var(--ws-strong)}.vf-auth-card>header small{margin-top:4px;color:var(--ws-muted);font-size:12px;line-height:1.5}
.vf-auth-card>header button{width:32px;height:32px;border:1px solid var(--ws-line);border-radius:8px;background:var(--ws-panel);color:var(--ws-muted);font-size:20px;cursor:pointer}
.vf-auth-card label{display:grid;gap:6px}.vf-auth-card label span{font-size:12px;font-weight:650}.vf-auth-card input{height:42px;padding:0 11px;border:1px solid var(--ws-line-strong);border-radius:8px;background:var(--ws-bg);color:var(--ws-text);font:inherit;outline:0}.vf-auth-card input:focus{border-color:#78bdb5;box-shadow:0 0 0 3px color-mix(in srgb,var(--ws-teal) 10%,transparent)}
.vf-auth-card [data-vf-auth-error]{margin:0;padding:8px 10px;border-radius:8px;background:color-mix(in srgb,var(--ws-danger) 8%,var(--ws-panel));color:var(--ws-danger);font-size:12px;line-height:1.45}
.vf-auth-card footer{display:flex;justify-content:flex-end;gap:8px}.vf-auth-card footer button{min-height:38px;padding:0 14px;border:1px solid var(--ws-line-strong);border-radius:8px;background:var(--ws-panel);color:var(--ws-text);font-weight:650;cursor:pointer}.vf-auth-card footer [data-vf-auth-submit]{border-color:var(--ws-teal);background:var(--ws-teal);color:#fff}.vf-auth-card footer button:disabled{opacity:.6;cursor:wait}
@media(max-width:520px){.vf-auth-dialog{width:calc(100vw - 20px);margin:auto 10px}.vf-auth-card{padding:16px}.vf-auth-card footer button{min-height:42px}}
'''
css_path.write_text(css, encoding='utf-8')
