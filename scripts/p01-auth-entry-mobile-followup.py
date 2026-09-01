from pathlib import Path
import os

root=Path(os.environ['P01_ROOT'])
shell_path=root/'src/app/FunctionalWorkspaceShell.php'
js_path=root/'src/assets/auth-controls.js'
css_path=root/'src/assets/workspace-rebaseline.css'

shell=shell_path.read_text(encoding='utf-8')
old='''    ?><a class="<?=$mode===$key?'active':''?>" href="<?=$href?>" aria-current="<?=$mode===$key?'page':'false'?>"><?=vf_fw_h($label)?></a><?php endforeach; ?>\n  </div>\n</nav>\n'''
new='''    ?><a class="<?=$mode===$key?'active':''?>" href="<?=$href?>" aria-current="<?=$mode===$key?'page':'false'?>"><?=vf_fw_h($label)?></a><?php endforeach; ?>\n    <?php if($admin): ?><a href="#" class="vf-global-auth-action" data-vf-auth-logout>退出</a><?php else: ?><a href="#" class="vf-global-auth-action" data-vf-auth-login>登录</a><?php endif; ?>\n  </div>\n</nav>\n'''
if shell.count(old)!=1:
    raise SystemExit(f'global nav anchor mismatch: {shell.count(old)}')
shell=shell.replace(old,new)
shell_path.write_text(shell,encoding='utf-8')

js=js_path.read_text(encoding='utf-8')
repls={
"  const loginTrigger=document.querySelector('[data-vf-auth-login]');\n  const logoutTrigger=document.querySelector('[data-vf-auth-logout]');\n  if(!loginTrigger&&!logoutTrigger)return;":"  const loginTriggers=Array.from(document.querySelectorAll('[data-vf-auth-login]'));\n  const logoutTriggers=Array.from(document.querySelectorAll('[data-vf-auth-logout]'));\n  if(!loginTriggers.length&&!logoutTriggers.length)return;",
"  loginTrigger?.addEventListener('click',event=>{\n    event.preventDefault();\n    const dialog=ensureDialog();\n    if(typeof dialog.showModal==='function')dialog.showModal();else dialog.setAttribute('open','');\n    setTimeout(()=>dialog.querySelector('input[name=\"password\"]')?.focus(),20);\n  });":"  loginTriggers.forEach(trigger=>trigger.addEventListener('click',event=>{\n    event.preventDefault();\n    const dialog=ensureDialog();\n    if(typeof dialog.showModal==='function')dialog.showModal();else dialog.setAttribute('open','');\n    setTimeout(()=>dialog.querySelector('input[name=\"password\"]')?.focus(),20);\n  }));",
"  logoutTrigger?.addEventListener('click',async event=>{\n    event.preventDefault();\n    logoutTrigger.setAttribute('aria-busy','true');\n    logoutTrigger.style.pointerEvents='none';":"  logoutTriggers.forEach(trigger=>trigger.addEventListener('click',async event=>{\n    event.preventDefault();\n    trigger.setAttribute('aria-busy','true');\n    trigger.style.pointerEvents='none';",
"      logoutTrigger.removeAttribute('aria-busy');\n      logoutTrigger.style.pointerEvents='';\n    }\n  });":"      trigger.removeAttribute('aria-busy');\n      trigger.style.pointerEvents='';\n    }\n  }));"
}
for old_text,new_text in repls.items():
    if js.count(old_text)!=1:
        raise SystemExit(f'js anchor mismatch: {old_text[:40]!r} count={js.count(old_text)}')
    js=js.replace(old_text,new_text)
js_path.write_text(js,encoding='utf-8')

css=css_path.read_text(encoding='utf-8')
marker='/* P01 mobile auth entry · 2026-09-01 */'
if marker in css:
    raise SystemExit('mobile auth css already exists')
css += r'''

/* P01 mobile auth entry · 2026-09-01 */
.vf-global-auth-action{display:none}
@media(max-width:760px){
  .vf-global-domain-nav-inner{padding-right:6px}
  .vf-global-domain-nav .vf-global-auth-action{position:sticky;right:0;margin-left:auto;padding:0 10px;display:inline-flex;align-items:center;justify-content:center;background:color-mix(in srgb,var(--ws-panel) 98%,transparent);color:var(--ws-teal);font-weight:750;box-shadow:-10px 0 14px color-mix(in srgb,var(--ws-panel) 92%,transparent)}
  .vf-global-domain-nav .vf-global-auth-action::after{display:none!important}
}
'''
css_path.write_text(css,encoding='utf-8')
