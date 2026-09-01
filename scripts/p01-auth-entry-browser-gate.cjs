const {chromium}=require('playwright-core');
const fs=require('fs');
const base=`http://127.0.0.1:${process.env.PORT}/`;
const E=process.env.EVID;
const A=(v,m)=>{if(!v)throw new Error(m)};
const routes={
  'start.php':['门禁公开导航','门禁私人导航'],
  'channels.php':['门禁公开频道','门禁私人频道'],
  'watch.php':['门禁公开电影','门禁私人电影']
};
const visibleCount=async(p,sel)=>await p.locator(sel).evaluateAll(es=>es.filter(e=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&r.width>0&&r.height>0}).length);
const text=async p=>(await p.locator('body').innerText()).replace(/\s+/g,' ');
const noOverflow=async(p,label)=>{const d=await p.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth);A(d===0,`${label} overflow=${d}`)};
const loginThroughUi=async p=>{
  const trigger=p.locator('[data-vf-auth-login]:visible').first();A(await trigger.count()===1,'visible login entry missing');
  await trigger.click();
  const dialog=p.locator('[data-vf-auth-dialog]');await dialog.waitFor({state:'visible'});
  await dialog.locator('input[name="password"]').fill(process.env.ADMIN_PASS);
  await dialog.locator('[data-vf-auth-submit]').click();
  await p.waitForFunction(()=>document.querySelectorAll('[data-vf-auth-logout]').length>0,{timeout:10000});
};
const logoutThroughUi=async p=>{
  const trigger=p.locator('[data-vf-auth-logout]:visible').first();A(await trigger.count()===1,'visible logout entry missing');
  await trigger.click();
  await p.waitForFunction(()=>document.querySelectorAll('[data-vf-auth-login]').length>0,{timeout:10000});
};
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME,args:['--no-sandbox']});
  const out={source:process.env.SOURCE,widths:{}};
  for(const width of [390,1440]){
    const height=width===390?844:900;
    const ctx=await browser.newContext({viewport:{width,height}});
    const p=await ctx.newPage();out.widths[width]={anonymous:{},admin:{},logout:{}};
    for(const [route,[pub,priv]] of Object.entries(routes)){
      await p.goto(base+route,{waitUntil:'domcontentloaded'});await p.waitForTimeout(180);
      let t=await text(p);A(t.includes(pub),`anonymous public missing ${route}`);A(!t.includes(priv),`anonymous private leak ${route}`);
      A(await visibleCount(p,'[data-vf-auth-login]')>0,`anonymous login entry not visible ${route}`);
      A(await visibleCount(p,'[data-vf-auth-logout]')===0,`anonymous logout visible ${route}`);
      A(await visibleCount(p,'a[href="links-admin.php"]')===0,`anonymous resource management visible ${route}`);
      A(await visibleCount(p,'a[href="settings.php"]')===0,`anonymous settings visible ${route}`);
      if(width===390)A(await visibleCount(p,'.vf-global-auth-action[data-vf-auth-login]')===1,`mobile login not in global nav ${route}`);
      await noOverflow(p,`anonymous ${route} ${width}`);out.widths[width].anonymous[route]='PASS';
    }
    await p.goto(base+'start.php',{waitUntil:'domcontentloaded'});await loginThroughUi(p);await p.waitForTimeout(200);
    for(const [route,[pub,priv]] of Object.entries(routes)){
      await p.goto(base+route,{waitUntil:'domcontentloaded'});await p.waitForTimeout(180);const t=await text(p);
      A(t.includes(pub)&&t.includes(priv),`admin public/private missing ${route}`);
      A(await p.locator('a[href="links-admin.php"]').count()>0,`admin resource management DOM missing ${route}`);
      A(await p.locator('a[href="settings.php"]').count()>0,`admin settings DOM missing ${route}`);
      A(await visibleCount(p,'[data-vf-auth-logout]')>0,`admin logout entry not visible ${route}`);
      A(await visibleCount(p,'[data-vf-auth-login]')===0,`admin login still visible ${route}`);
      if(width===1440){A(await visibleCount(p,'a[href="links-admin.php"]')>0,`desktop resource management not visible ${route}`);A(await visibleCount(p,'a[href="settings.php"]')>0,`desktop settings not visible ${route}`)}
      if(width===390)A(await visibleCount(p,'.vf-global-auth-action[data-vf-auth-logout]')===1,`mobile logout not in global nav ${route}`);
      await noOverflow(p,`admin ${route} ${width}`);out.widths[width].admin[route]='PASS';
    }
    await p.goto(base+'start.php',{waitUntil:'domcontentloaded'});await logoutThroughUi(p);await p.waitForTimeout(180);
    const after=await text(p);A(after.includes('门禁公开导航')&&!after.includes('门禁私人导航'),'logout did not restore public-only state');
    A(await visibleCount(p,'[data-vf-auth-login]')>0,'login missing after logout');A(await visibleCount(p,'[data-vf-auth-logout]')===0,'logout remains visible after logout');
    out.widths[width].logout['start.php']='PASS';
    await ctx.close();
  }
  fs.writeFileSync(`${E}/browser-gate.json`,JSON.stringify({...out,verdict:'PASS'},null,2));
  await browser.close();console.log('P01_AUTH_ENTRY_BROWSER_GATE=PASS');
})().catch(e=>{console.error(e);process.exit(1)});
