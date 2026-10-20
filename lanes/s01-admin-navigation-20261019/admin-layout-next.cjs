const {chromium}=require('playwright');const fs=require('fs');
(async()=>{
 const browser=await chromium.launch();const checks=[],pages=[],errors=[];let complete=false,focusProof=0,saveRequests=0;
 const check=(id,ok,detail)=>{checks.push({id,ok:!!ok,detail});if(!ok)console.error('FAILED_CHECK',id,JSON.stringify(detail));};
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}});page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
  page.on('request',r=>{if(r.method()==='POST'&&(r.postData()||'').includes('vf_theme_layout_save'))saveRequests++;});
  const base='http://127.0.0.1:18880/wp-admin/themes.php?page=vf-theme-modules&tab=layout';
  await page.goto('http://127.0.0.1:18880/wp-login.php');await page.locator('#user_login').fill('admin');await page.locator('#user_pass').fill('Synthetic-Only-Update-54!');await page.locator('input[name=redirect_to]').evaluate((e,u)=>e.value=u,base);await page.locator('#wp-submit').click();await page.waitForURL('**/wp-admin/**');
  await page.goto(base,{waitUntil:'networkidle'});const contexts=await page.locator('[data-vf-page-context]').evaluateAll(es=>es.map(e=>e.dataset.vfPageContext));check('20-context-inventory',new Set(contexts).size===20,contexts);
  const canonical=()=>page.locator('[data-vf-layout-form]').evaluate(f=>[...f.querySelectorAll('[name]')].map(e=>[e.name,e.value,e.checked]));
  const tabTrap=async(dialog,id)=>{
   await dialog.evaluate(d=>{const cs=[...d.querySelectorAll('button:not([disabled]),a[href],input:not([type=hidden]):not([disabled]),select:not([disabled]),textarea:not([disabled]),summary,[tabindex]')].filter(e=>e.tabIndex>=0&&e.getClientRects().length);cs[cs.length-1]?.focus();});await page.keyboard.press('Tab');
   check(id,await dialog.evaluate(d=>{const cs=[...d.querySelectorAll('button:not([disabled]),a[href],input:not([type=hidden]):not([disabled]),select:not([disabled]),textarea:not([disabled]),summary,[tabindex]')].filter(e=>e.tabIndex>=0&&e.getClientRects().length);return document.activeElement===cs[0];}),'Last focusable wraps to first');
  };
  for(const width of [1440,1024])for(const context of contexts){
   await page.setViewportSize({width,height:1000});const id=context+'-'+width;const response=await page.goto(base+'&view=edit&context='+context,{waitUntil:'networkidle'});
   check(id+'-http',response.status()===200,response.status());
   const root=page.locator('[data-vf-layout-page]');check(id+'-correct-editor',await root.getAttribute('data-vf-layout-context')===context,await root.getAttribute('data-vf-layout-context'));
   const guide=page.locator('[data-vf-page-finder]');await guide.locator('summary').click();await page.waitForFunction(()=>document.querySelector('[data-vf-page-finder-select]').options.length>0);
   const option=await guide.locator('option').evaluateAll(es=>es.find(e=>e.textContent==='模块结构')?.value);check(id+'-module-entry',option!==undefined,option);
   if(option===undefined)continue;
   await guide.locator('select').selectOption(option);await guide.locator('button').click();
   const opener=root.locator('[data-vf-layout-module-library-open]');check(id+'-reachable-library',await opener.isVisible(),'Open module structure through page finder');if(!await opener.isVisible())continue;
   const original=await canonical();await page.screenshot({path:`proof/layout-editor-${context}-${width}.png`});await opener.click();
   const library=root.locator('[data-vf-layout-module-library]');await library.waitFor({state:'visible'});
   const filter=library.locator('[data-vf-layout-library-filter]'),search=library.locator('[data-vf-layout-library-search]'),items=library.locator('[data-vf-layout-library-item]');
   const total=await items.count(),allowed=await items.locator('xpath=self::*[@data-allowed="1"]').count();
   check(id+'-default-scope',await filter.inputValue()==='allowed'&&await library.locator('[data-vf-layout-library-item]:visible').count()===allowed,{total,allowed});
   check(id+'-lookup-label-layout',await library.locator('.vf-layout-library-filters label').evaluateAll(es=>es.every(e=>getComputedStyle(e).gridTemplateColumns.split(' ').length===1)),'Lookup labels use one column above their controls');
   await filter.selectOption('all');check(id+'-all-modules',await library.locator('[data-vf-layout-library-item]:visible').count()===total,total);
   await search.fill('NO_MATCH_SYNTHETIC_MODULE_39');check(id+'-empty-feedback',await library.locator('[data-vf-layout-library-item]:visible').count()===0&&await library.locator('[data-vf-layout-library-empty]').isVisible(),'No matches have a visible explanation');
   if(context==='home')await page.screenshot({path:`proof/layout-library-empty-${width}.png`});
   await search.press('Enter');check(id+'-enter-no-save',saveRequests===0,saveRequests);
   await search.fill('');await filter.selectOption('available');
   check(id+'-available-only',await library.locator('[data-vf-layout-library-item]:visible').evaluateAll(es=>es.every(e=>e.dataset.allowed==='1'&&!e.querySelector('[data-vf-layout-library-add]')?.disabled)),await library.locator('[data-vf-layout-library-item]:visible').count());
   if(await root.getAttribute('data-vf-layout-system-locked')==='1')check(id+'-locked-structure',await library.locator('[data-vf-layout-library-item]:visible').count()===0,'Locked contexts have no enabled structural add actions');
   await filter.selectOption('all');const firstName=await items.first().locator('strong').first().innerText();await search.fill(firstName);
   check(id+'-search-matches',await library.locator('[data-vf-layout-library-item]:visible').count()>0&&await library.locator('[data-vf-layout-library-item]:visible').evaluateAll((es,q)=>es.every(e=>e.textContent.includes(q)),firstName),firstName);
   await search.fill('');await filter.selectOption('allowed');
   const afterLookup=await canonical();const lookupDirty=await root.evaluate(r=>r.classList.contains('is-dirty'));check(id+'-lookup-keeps-values',JSON.stringify(original)===JSON.stringify(afterLookup)&&!lookupDirty,{dirty:lookupDirty,changedFields:original.filter((e,i)=>JSON.stringify(e)!==JSON.stringify(afterLookup[i])).map(e=>e[0])});
   check(id+'-lookup-indicator-clean',await page.locator('[data-vf-unsaved-indicator]').evaluate(e=>!e.classList.contains('is-dirty')),'Looking up modules must not show a false unsaved-change badge');
   check(id+'-dialog-fits',await library.evaluate(e=>{const r=e.getBoundingClientRect();return r.x>=0&&r.right<=innerWidth+1&&r.y>=0&&r.bottom<=innerHeight+1&&e.scrollWidth<=e.clientWidth+1;}),'Dialog and controls fit the viewport');
   if(['home','article_detail','blog_index','problem_detail','not_found'].includes(context))await page.screenshot({path:`proof/layout-library-${context}-${width}.png`});
   await tabTrap(library,id+'-library-tab-trap');await page.keyboard.press('Escape');
   check(id+'-library-escape-focus',!await library.isVisible()&&await opener.evaluate(e=>document.activeElement===e),'Escape returns to the library opener');
   // One representative add/editor/return proof per width; changes stay in browser memory.
   if(!pages.some(p=>p.width===width&&p.focusProof)){
    const key=await root.evaluate(r=>{
     const owned=(r.querySelector('[data-vf-owned-modules]')?.dataset.vfOwnedModules||'').split(',');
     return [...r.querySelectorAll('[data-vf-layout-library-add]:not([disabled])')].map(b=>b.dataset.vfLayoutLibraryAdd).find(k=>!owned.includes(k)&&!(k==='post_list'&&r.querySelector('[data-vf-blog-function-cockpit],[data-vf-directory-index-cockpit]'))&&[...r.querySelectorAll('[data-vf-module-settings-card]')].some(c=>c.dataset.module===k));
    });
    if(key){
     await opener.click();await filter.selectOption('available');await library.locator('[data-vf-layout-library-add="'+key+'"]').click();
     const editor=root.locator('[data-vf-layout-module-editor]');await editor.waitFor({state:'visible'});await page.waitForFunction(()=>document.querySelector('[data-vf-layout-module-editor]')?.contains(document.activeElement));
     check(id+'-add-editor-only',!await library.isVisible()&&await editor.evaluate(e=>e.classList.contains('is-saas-modal')),{module:key});
     await tabTrap(editor,id+'-editor-tab-trap');await page.keyboard.press('Escape');
     check(id+'-editor-returns-visible-focus',await opener.evaluate(e=>document.activeElement===e&&!!e.getClientRects().length),'Returning from the editor never focuses a hidden library button');
     check(id+'-candidate-not-saved',await root.evaluate(r=>r.classList.contains('is-dirty'))&&saveRequests===0,saveRequests);
     const breadcrumb=root.locator('.vf-layout-location [data-vf-layout-directory-link]');await breadcrumb.click();
     const guard=root.locator('[data-vf-layout-navigation-dialog]');await guard.waitFor({state:'visible'});check(id+'-breadcrumb-guard',await guard.locator('[data-vf-layout-navigation-target]').innerText()==='前台页面总览','Existing custom guard is shared by both return paths');
     await guard.locator('button[data-vf-layout-navigation-cancel]').last().click();check(id+'-cancel-preserves-candidate',await root.evaluate(r=>r.classList.contains('is-dirty'))&&new URL(page.url()).searchParams.get('context')===context,'Cancel stays in current editor');
     focusProof++;pages.push({context,width,focusProof:true});
    }
   }
   check(id+'-page-no-overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'No whole-page horizontal scroll');pages.push({context,width,total,allowed});
  }
  check('two-width-editor-focus-proofs',focusProof===2,focusProof);check('no-save-posts',saveRequests===0,saveRequests);check('no-browser-errors',errors.length===0,errors);complete=true;
  if(checks.some(c=>!c.ok))throw Error(JSON.stringify(checks.filter(c=>!c.ok)));
 }finally{fs.writeFileSync('proof/admin-layout-next.json',JSON.stringify({status:complete&&checks.every(c=>c.ok)?'PASS':'FAIL',complete,targetSha:process.env.TARGET_SHA,checks,pages,scope:'20 layout editor contexts, two desktop widths, browser-only candidates; no database save or Production'},null,2));await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
