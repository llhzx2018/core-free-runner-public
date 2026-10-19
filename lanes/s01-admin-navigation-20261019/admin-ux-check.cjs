const {chromium}=require('playwright');
const fs=require('fs');
(async()=>{
 const browser=await chromium.launch();const checks=[],pages=[];let complete=false;
 const check=(id,ok,detail)=>{checks.push({id,ok:!!ok,detail});if(!ok)throw Error(id+': '+JSON.stringify(detail));};
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const base='http://127.0.0.1:18880/wp-admin/themes.php?page=vf-theme-modules&tab=';
  await page.goto('http://127.0.0.1:18880/wp-login.php');await page.locator('#user_login').fill('admin');await page.locator('#user_pass').fill('Synthetic-Only-Update-54!');await page.locator('input[name=redirect_to]').evaluate((e,url)=>e.value=url,base+'overview');await page.locator('#wp-submit').click();await page.waitForURL('**/wp-admin/**');
  const formState=()=>page.locator('.vf-admin-workspace').evaluate(root=>[...root.querySelectorAll('form input,form select,form textarea')].map(e=>[e.name,e.value,e.checked]));
  for(const tab of ['overview','brand','layout','navigation','render','seo','preview','recovery']){
   for(const width of [1440,1024]){
    await page.setViewportSize({width,height:1000});const r=await page.goto(base+tab,{waitUntil:'networkidle'});
    const id=tab+'-'+width;
    check(id+'-http',r.status()===200,r.status());
    const guide=page.locator('[data-vf-page-finder]');await guide.waitFor();
    check(id+'-finder-count',await guide.count()===1,await guide.count());
    await guide.locator('summary').click();await page.waitForFunction(()=>document.querySelector('[data-vf-page-finder-select]')?.options.length>0);
    const options=await guide.locator('option').evaluateAll(es=>es.map(e=>({value:e.value,text:e.textContent})));
    check(id+'-finder-entries',options.length>=3,options);
    if(tab==='brand')check(id+'-nested-settings',options.some(o=>o.text==='临时视觉')&&options.some(o=>o.text==='站点预设'),options);
    if(tab==='layout'){const types=await page.locator('.vf-frontend-pages__name h3').allTextContents();check(id+'-all-page-types',types.length===20&&types.every(t=>options.some(o=>o.text===t.trim())),{types,options});}
    const before=await formState();
    for(const option of options){
     await guide.locator('select').selectOption(option.value);
     await guide.locator('[data-vf-page-finder-go]').focus();await page.keyboard.press('Enter');
     const result=await page.evaluate(()=>{const active=document.activeElement;return {message:document.querySelector('[data-vf-page-finder-feedback]').textContent,focused:!!active&&!active.closest('[data-vf-page-finder]'),visible:!!active?.getClientRects().length}});
     check(id+'-jump-'+option.value,result.message.startsWith('已定位：')&&result.focused&&result.visible,{label:option.text,...result});
    }
    check(id+'-form-retained',JSON.stringify(before)===JSON.stringify(await formState()),'Page finding must not edit form values');
    await page.goto(base+tab,{waitUntil:'networkidle'});
    const metrics=await page.evaluate(()=>({height:document.documentElement.scrollHeight,overflow:document.documentElement.scrollWidth>innerWidth+1}));
    check(id+'-no-overflow',!metrics.overflow,metrics);
    if(tab==='layout')check(id+'-compact-directory',metrics.height<(width===1440?6000:7300),metrics);
    if(tab==='overview')check(id+'-preview-entry',new URL(await page.locator('.vf-overview-check-entry a').getAttribute('href')).searchParams.get('tab')==='preview',await page.locator('.vf-overview-check-entry a').getAttribute('href'));
    pages.push({tab,width,entries:options,...metrics});
    await page.screenshot({path:`proof/admin-ux-${tab}-${width}.png`,fullPage:true});
    await page.locator('[data-vf-page-finder] summary').click();await page.screenshot({path:`proof/admin-ux-finder-${tab}-${width}.png`,fullPage:true});
   }
  }
  // A user may locate advanced settings while preserving edits in the main form.
  for(const [tab,selector,newValue] of [
   ['brand','input[name="brand[siteName]"]','Unsaved synthetic brand'],
   ['render','select[name="renderer[defaultMode]"]','HYBRID'],
   ['seo','input[data-key="pathPattern"]','synthetic-unsaved-path']
  ]){
   await page.goto(base+tab,{waitUntil:'networkidle'});
   const field=page.locator(selector).filter({visible:true}).first();
   if(selector.startsWith('select'))await field.selectOption(newValue);else await field.fill(newValue);
   const before=await formState();const guide=page.locator('[data-vf-page-finder]');await guide.locator('summary').click();await guide.locator('select').selectOption({index:1});await guide.locator('button').click();
   check(tab+'-unsaved-retained',JSON.stringify(before)===JSON.stringify(await formState()),await field.inputValue());
   page.once('dialog',d=>d.accept());
  }
  check('no-browser-errors',errors.length===0,errors);complete=true;
 }finally{fs.writeFileSync('proof/admin-ux-check.json',JSON.stringify({status:complete&&checks.every(c=>c.ok)?'PASS':'FAIL',complete,checks,pages,scope:'8 Theme backoffice page bodies, two desktop widths; no Production or mobile acceptance'},null,2));await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
