const {chromium}=require('playwright'),fs=require('fs');
const mode=process.argv[2]||'focused',checks=[];
function check(name,pass,detail){checks.push({name,pass:!!pass,detail});if(!pass)throw Error(name+': '+JSON.stringify(detail));}
const contexts=['home','tool','tool_hub','blog_index','article_detail','guide_index','guide_detail','problem_index','problem_detail','archive_list','faq_page','glossary_index','glossary_detail','legal','contact_page','about_page','basic_page','search','not_found','html_sitemap'];
const origin='http://127.0.0.1:18880',directory=origin+'/wp-admin/themes.php?page=vf-theme-modules&tab=layout&view=pages';
const edit=c=>origin+'/wp-admin/themes.php?page=vf-theme-modules&tab=layout&view=edit&context='+c;
const fields=p=>p.locator('[data-vf-layout-form] input[name]:not([type=hidden]),[data-vf-layout-form] select[name],[data-vf-layout-form] textarea[name]').evaluateAll(xs=>xs.map(e=>({name:e.name,type:e.type,value:e.type==='checkbox'?e.checked:e.value,min:e.min||'',max:e.max||'',options:e.options?[...e.options].map(o=>o.value):null})));
(async()=>{const b=await chromium.launch();let p;try{
 const cx=await b.newContext({viewport:{width:1440,height:1000}});p=await cx.newPage();const errors=[];cx.on('page',q=>q.on('pageerror',e=>errors.push(e.message)));p.on('pageerror',e=>errors.push(e.message));
 p.on('dialog',d=>d.accept());await p.goto(origin+'/wp-login.php');await p.locator('#user_login').fill('admin');await p.locator('#user_pass').fill('Synthetic-Only-Update-54!');await p.locator('input[name=redirect_to]').evaluate((e,v)=>e.value=v,directory);await p.locator('#wp-submit').click();await p.waitForURL('**/wp-admin/**');await p.goto(directory,{waitUntil:'networkidle'});
 if(mode==='baseline'){
  const data={};for(const c of contexts){await p.goto(edit(c),{waitUntil:'networkidle'});data[c]=await fields(p);}
  fs.writeFileSync('proof/baseline-fields.json',JSON.stringify(data));check('stable163 captures20 existing editor forms',Object.keys(data).length===20);return;
 }
 if(mode!=='flows'){
 const baseline=JSON.parse(fs.readFileSync('proof/baseline-fields.json'));
 for(const c of contexts){
  await p.goto(edit(c),{waitUntil:'networkidle'});const root=p.locator('[data-vf-layout-page]');
  check(c+' full original input values types bounds options preserved',JSON.stringify(await fields(p))===JSON.stringify(baseline[c]));
  check(c+' no engineering panels or visible identifiers',await root.locator('.vf-layout-professional-info,.vf-layout-function-cockpit__consumer,.vf-layout-function-integration__status,.vf-layout-function-cockpit__summary').count()===0&&!/消费者|真实消费链|#vf-module-|项核心功能|个控制项/.test(await root.innerText()));
  check(c+' clean page has no sticky save or zero-change count',!await root.locator('[data-vf-layout-save-dock]').isVisible()&&!await root.locator('[data-vf-layout-dirty-count]').isVisible());
 }
 for(const width of[1920,1440,1319,1024])for(const c of['home','article_detail','archive_list']){
  await p.setViewportSize({width,height:1000});await p.goto(edit(c),{waitUntil:'networkidle'});await p.evaluate(()=>document.fonts.ready);
  check(c+'/'+width+' no horizontal overflow',await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  check(c+'/'+width+' actual settings usable',await p.locator('#vf-layout-step-functions input:not([type=hidden]):visible,#vf-layout-step-functions select:visible').count()>0);
  if(width===1440)await p.screenshot({path:'proof/editor-'+c+'-1440.png',fullPage:true});
 }
 console.log('LAYOUT_EDITOR_RENDER_PASS',checks.length);return;
 }
 await p.setViewportSize({width:1440,height:1000});await p.goto(edit('home'),{waitUntil:'networkidle'});
 const root=p.locator('[data-vf-layout-page]'),title=p.locator('[name="layout[activeModuleSettings][tool_grid][title]"]'),save=p.locator('[data-vf-layout-save]'),original=await title.inputValue();
 await title.fill('Synthetic operator title 164');
 check('dirty dock offers one save plus discard',await root.locator('[data-vf-layout-save-dock]').isVisible()&&await root.locator('[data-vf-layout-discard]').isVisible()&&await save.innerText()==='保存更改');
 const sameRow=await root.locator('.vf-layout-save-dock__actions').evaluate(e=>{const a=e.querySelector('[data-vf-layout-save]').getBoundingClientRect(),b=e.querySelector('[data-vf-layout-discard]').getBoundingClientRect();return Math.abs(a.y-b.y)<2&&b.right<=a.x+1;});check('discard and save share aligned action row',sameRow);
 const ajax=async route=>{if((route.request().postData()||'').includes('vf_theme_layout_save'))return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({success:true,data:{message:'synthetic incomplete response'}})});return route.continue();};
 await p.route('**/admin-ajax.php',ajax);await save.click();await root.locator('[data-vf-layout-error-summary]').waitFor({state:'visible'});
 check('incomplete receipt cannot claim save or discard draft',await title.inputValue()==='Synthetic operator title 164'&&await root.evaluate(e=>e.classList.contains('is-dirty'))&&!await root.locator('[data-vf-layout-toast]').isVisible());await p.unroute('**/admin-ajax.php',ajax);
 const abort=async route=>{if((route.request().postData()||'').includes('vf_theme_layout_save'))return route.abort('failed');return route.continue();};await p.route('**/admin-ajax.php',abort);await save.click();await root.locator('[data-vf-layout-error-summary]').waitFor({state:'visible'});await p.waitForFunction(()=>!document.querySelector('[data-vf-layout-save]').disabled);
 check('network failure retains draft and enables retry',await title.inputValue()==='Synthetic operator title 164'&&await save.isEnabled());await p.unroute('**/admin-ajax.php',abort);
 const stale=await cx.newPage();stale.on('dialog',d=>d.accept());await stale.goto(edit('home'),{waitUntil:'networkidle'});
 const submit=async page=>{const response=page.waitForResponse(r=>r.url().includes('/admin-ajax.php')&&(r.request().postData()||'').includes('vf_theme_layout_save'));await page.locator('[data-vf-layout-save]').click();const body=await(await response).json();await page.waitForFunction(()=>!document.querySelector('[data-vf-layout-save]').disabled);return body;};
 const receipt=await submit(p);check('real canonical save returns complete verified receipt',receipt.success===true&&receipt.data?.revision?.length===64&&receipt.data?.runtimeVerification?.ok===true, {success:receipt.success,keys:Object.keys(receipt.data||{})});
 check('success feedback is concise and dock clears',!await root.locator('[data-vf-layout-save-dock]').isVisible()&&await save.textContent()==='保存更改'&&await root.locator('[data-vf-layout-toast]').innerText().then(t=>t.includes('已保存')&&!/回读|消费者|字段/.test(t)));
 await p.reload({waitUntil:'networkidle'});check('real saved title persists after reload',await title.inputValue()==='Synthetic operator title 164');
 await stale.locator('[name="layout[activeModuleSettings][tool_grid][title]"]').fill('Synthetic stale draft');let conflict=await submit(stale);check('stale editor cannot overwrite current value',conflict.success===false&&await stale.locator('[data-vf-layout-error-summary]').isVisible()&&await stale.locator('[name="layout[activeModuleSettings][tool_grid][title]"]').inputValue()==='Synthetic stale draft');conflict=await submit(stale);check('repeated stale retry stays fail closed',conflict.success===false);await stale.close();
 await title.fill(original);await submit(p);await p.reload({waitUntil:'networkidle'});check('restored original title survives canonical save',await title.inputValue()===original);
 await title.fill('Synthetic discard only');await root.locator('[data-vf-layout-discard]').click();await p.waitForLoadState('networkidle');check('discard reload restores saved value and clean dock',await title.inputValue()===original&&!await root.locator('[data-vf-layout-save-dock]').isVisible());
 await title.fill('Synthetic navigation draft');await root.locator('[data-vf-layout-directory-link]').last().click();await root.locator('[data-vf-layout-navigation-dialog]').waitFor({state:'visible'});await root.locator('[data-vf-layout-navigation-cancel]').first().click();check('cancel navigation preserves draft',await title.inputValue()==='Synthetic navigation draft');await root.locator('[data-vf-layout-directory-link]').last().click();await root.locator('[data-vf-layout-navigation-confirm]').click();await p.waitForURL('**view=pages**');check('confirmed return reaches clean20-type directory',await p.locator('[data-vf-page-context]').count()===20&&await p.locator('.vf-frontend-pages__progress-record').count()===0);
 await p.goto(edit('home'),{waitUntil:'networkidle'});await root.locator('[data-vf-layout-context-catalog-open]').click();const dialog=root.locator('[data-vf-layout-context-catalog-dialog]');check('existing page switch dialog opens',await dialog.isVisible());await p.keyboard.press('Escape');check('escape restores page switch trigger focus',!await dialog.isVisible()&&await root.locator('[data-vf-layout-context-catalog-open]').evaluate(e=>e===document.activeElement));
 const native=await p.request.get(origin+'/wp-admin/install.php');check('clean native installation revisit stays locked',/Already Installed|already installed/.test(await native.text()));
 check('no browser runtime errors',errors.length===0,errors);console.log('LAYOUT_EDITOR_FOCUSED_PASS',checks.length);
}finally{if(p&&checks.some(x=>!x.pass))await p.screenshot({path:'proof/editor-failed.png',fullPage:true});fs.writeFileSync('proof/'+(mode==='baseline'?'baseline-results':mode==='flows'?'flow-results':'browser-results')+'.json',JSON.stringify({status:checks.every(c=>c.pass)?'PASS':'FAIL',count:checks.length,passed:checks.filter(c=>c.pass).length,checks},null,2));await b.close();}})().catch(e=>{console.error(e);process.exit(1)});
