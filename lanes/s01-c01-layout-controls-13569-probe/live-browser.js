const {chromium}=require('playwright'),fs=require('fs');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']}),page=await browser.newPage(),origin='http://127.0.0.1:18880',checks=[],failures=[];
 page.on('pageerror',e=>failures.push({error:e.message}));
 await page.goto(origin+'/wp-login.php');await page.locator('#user_login').fill('admin');await page.locator('#user_pass').fill('Synthetic-Only-Update-54!');await page.locator('#wp-submit').click();
 const contexts=['blog_index'];
 const scan=async(c,width,area)=>{
  const controls=page.locator('[data-vf-layout-page] input[type="checkbox"]:visible,[data-vf-layout-page] select:visible');
  for(let i=0;i<await controls.count();i++){
   const control=controls.nth(i),info=await control.evaluate(n=>({name:n.name,type:n.type,disabled:n.disabled,options:n.options?[...n.options].map(o=>({value:o.value,disabled:o.disabled})):null}));
   if(info.disabled){checks.push({c,width,area,...info,result:'DISABLED'});continue;}
   try{
    if(info.type==='checkbox'){
     const before=await control.isChecked();await control.click({timeout:2000});const after=await control.isChecked();
     if(before===after)throw Error('mouse click did not toggle');
     const label=control.locator('xpath=ancestor::label[1]');await label.locator('span').first().click({timeout:2000});if(await control.isChecked()!==before)throw Error('label did not toggle');
     await control.focus();await page.keyboard.press('Space');if(await control.isChecked()===before)throw Error('Space did not toggle');await page.keyboard.press('Space');
    }else{
     const before=await control.inputValue(),choices=info.options.filter(o=>!o.disabled&&o.value!==before);
     await control.click({timeout:2000});await page.keyboard.press('Escape');
     if(choices.length){await control.focus();await page.keyboard.press('Home');await page.keyboard.press('ArrowDown');await page.keyboard.press('Enter');await control.selectOption(choices[0].value);if(await control.inputValue()!==choices[0].value)throw Error('select did not change');await control.selectOption(before);}
    }
    checks.push({c,width,area,...info,result:'OPERABLE'});
   }catch(e){const details=await control.evaluate(n=>{const r=n.getBoundingClientRect(),hit=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2),s=getComputedStyle(n);return {checked:n.checked,hit:hit?.outerHTML.slice(0,500),box:r.toJSON(),pointer:s.pointerEvents,before:getComputedStyle(n,'::before').content};});failures.push({c,width,area,...info,error:e.message,details});}
  }
 };
 for(const width of [1319]){
  await page.setViewportSize({width,height:660});
  for(const c of contexts){
   await page.goto(origin+'/wp-admin/themes.php?page=vf-theme-modules&tab=layout&context='+c);
   await scan(c,width,'page');
   const tabs=page.locator('.vf-layout-function-master__item');for(let i=0;i<await tabs.count();i++){await tabs.nth(i).click();await scan(c,width,'function-'+i);}
   const rows=page.locator('[data-vf-layout-list] [data-vf-layout-edit-module]');for(let i=0;i<await rows.count();i++){
    await rows.nth(i).click();const modal=page.locator('[data-vf-layout-module-editor].is-saas-modal:visible');if(!await modal.count())continue;
    await scan(c,width,'module-'+i);
    const body=modal.locator('.vf-layout-module-settings-grid');await body.evaluate(n=>n.scrollTop=0);await body.hover();await page.mouse.wheel(0,2000);await page.waitForTimeout(100);
    const scroll=await body.evaluate(n=>{const r=n.getBoundingClientRect();return {height:n.clientHeight,total:n.scrollHeight,offset:n.scrollTop,overflow:getComputedStyle(n).overflowY,last:n.querySelector('[data-vf-module-settings-card]:not([hidden])')?.getBoundingClientRect().bottom,bottom:r.bottom};});
    if(scroll.total>scroll.height+2&&scroll.offset===0)failures.push({c,width,area:'modal-wheel',scroll});
    if(c==='blog_index'&&i===await rows.count()-1)await page.screenshot({path:'proof/probe-modal-'+width+'.png'});
    checks.push({c,width,area:'modal-scroll',scroll});await page.keyboard.press('Escape');
   }
  }
 }
 fs.writeFileSync('proof/controls-probe.json',JSON.stringify({checks,failures},null,2));console.log(JSON.stringify({checks:checks.length,failures}));await browser.close();
})();
