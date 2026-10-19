const {chromium}=require('playwright');
const fs=require('fs');
(async()=>{
 const browser=await chromium.launch();const pages=[];
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const base='http://127.0.0.1:18880/wp-admin/themes.php?page=vf-theme-modules&tab=';
  await page.goto('http://127.0.0.1:18880/wp-login.php');await page.locator('#user_login').fill('admin');await page.locator('#user_pass').fill('Synthetic-Only-Update-54!');await page.locator('input[name=redirect_to]').evaluate((e,url)=>e.value=url,base+'overview');await page.locator('#wp-submit').click();await page.waitForURL('**/wp-admin/**');
  for(const tab of ['overview','brand','layout','navigation','render','seo','preview','recovery']){
   for(const width of [1440,1024]){
    await page.setViewportSize({width,height:1000});const r=await page.goto(base+tab,{waitUntil:'networkidle'});
    if(r.status()!==200)throw Error(tab+' HTTP '+r.status());
    const record=await page.evaluate(()=>{
     const root=document.querySelector('.vf-admin-workspace');
     const visible=x=>!!(x.getClientRects().length&&getComputedStyle(x).visibility!=='hidden');
     const box=x=>{const r=x.getBoundingClientRect(),s=getComputedStyle(x);return {width:Math.round(r.width),height:Math.round(r.height),font:s.fontSize,lineHeight:s.lineHeight,overflow:x.scrollWidth>x.clientWidth+2,x:Math.round(r.x),y:Math.round(r.y)}};
     return {title:document.querySelector('.vf-theme-admin h1')?.innerText,height:document.documentElement.scrollHeight,overflow:document.documentElement.scrollWidth>innerWidth+1,
      headings:[...root.querySelectorAll('h2,h3')].filter(visible).map(x=>({text:x.innerText,...box(x)})),
      controls:[...root.querySelectorAll('button,input:not([type=hidden]):not([type=checkbox]):not([type=radio]),select,textarea,a.button')].filter(visible).map(x=>({tag:x.tagName,type:x.type,name:x.name,text:(x.innerText||x.getAttribute('aria-label')||'').trim().slice(0,100),disabled:x.disabled,...box(x)})),
      disclosures:[...root.querySelectorAll('details')].map(x=>({summary:x.querySelector('summary')?.innerText,open:x.open,visible:visible(x)})),
      visibleDialogs:[...root.querySelectorAll('[role=dialog]')].filter(visible).map(x=>x.id||x.className)};
    });
    pages.push({tab,width,http:r.status(),...record});
    await page.screenshot({path:`proof/admin-ux-${tab}-${width}.png`,fullPage:true});
    console.log('ADMIN_UX_BASELINE',tab,width,record.height,record.controls.length);
   }
  }
 }finally{fs.writeFileSync('proof/admin-ux-baseline.json',JSON.stringify({pages,scope:'8 Theme pages, desktop only, read-only baseline'},null,2));await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
