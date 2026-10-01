const fs=require('fs'); const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const context=await browser.newContext(); const page=await context.newPage();
 const errors=[]; page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:18880/wp-login.php');
 await page.locator('#user_login').fill('admin');await page.locator('#user_pass').fill('Synthetic-Only-Update-54!');
 await Promise.all([page.waitForURL(/wp-admin/),page.locator('#wp-submit').click()]);
 const checks=[];
 for(const width of [1440,1024,768,390]){
  await page.setViewportSize({width,height:1000});
  await page.goto('http://127.0.0.1:18880/wp-admin/tools.php?page=vf-private-updates&vf_notice=check_partial');
  await page.locator('[data-vf-update-body-v8]').waitFor();
  const state=await page.evaluate(()=>{
   const root=document.querySelector('[data-vf-update-body-v8]'),bar=root.querySelector('header');
   return {overflow:document.documentElement.scrollWidth>innerWidth+1,title:getComputedStyle(root.querySelector('h1')).fontSize,pagebar:bar.getBoundingClientRect().height,noticesInPagebar:bar.querySelectorAll('.notice').length,rows:root.querySelectorAll('.vf-update-component').length,name:getComputedStyle(root.querySelector('h3')).fontSize,version:getComputedStyle(root.querySelector('.vf-update-component__versions strong')).fontSize,passwordExposed:[...root.querySelectorAll('input[type=password]')].some(n=>n.value)};
  });
  if(state.overflow||parseFloat(state.title)<26||state.pagebar>130||state.noticesInPagebar||state.rows!==3||parseFloat(state.name)<15||parseFloat(state.version)<14||state.passwordExposed)throw Error(JSON.stringify({width,state}));
  if(!await page.locator('.vf-update-center__ownership').isVisible())throw Error('theme ownership hidden');
  if(await page.locator('.vf-update-component--current').count()!==3)throw Error('same-version normal state not corrected');
  if(await page.locator('.vf-update-component__versions strong').count()!==3)throw Error('duplicate equal version fields');
  const details=page.getByRole('link',{name:/^查看详情/});
  if(await details.count()){
   await details.first().click();if(!await page.locator('#vf-update-settings').evaluate(n=>n.open))throw Error('details failed');
   await page.locator('#vf-update-settings>summary').click();
  }
  const rec=page.locator('.vf-update-center__panel--recovery');await rec.locator('summary').focus();await page.keyboard.press('Enter');
  if(!await rec.evaluate(n=>n.open))throw Error('keyboard disclosure failed');await page.keyboard.press('Enter');
  await page.evaluate(()=>{location.hash='';window.scrollTo(0,0)});
  await page.screenshot({path:'proof/live-'+width+'.png',fullPage:true});checks.push({width,...state});
 }
 if(errors.length)throw Error(errors.join('\n'));
 fs.writeFileSync('proof/live-browser.json',JSON.stringify({pass:true,environment:'isolated real WordPress',checks,errors,owner_product_pass:false},null,2));
 await browser.close();console.log('REAL_WORDPRESS_BROWSER=PASS');
})().catch(e=>{console.error(e);process.exit(1)});
