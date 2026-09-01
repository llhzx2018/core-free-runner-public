const {chromium}=require('playwright-core');
const fs=require('fs');
const base=`http://127.0.0.1:${process.env.PORT}/`;
const E=process.env.EVID;
const A=(v,m)=>{if(!v)throw new Error(m)};
const functionalRoutes={
  'channels.php':['门禁公开频道','门禁私人频道'],
  'watch.php':['门禁公开电影','门禁私人电影']
};
const allRoutes={
  'start.php':['门禁公开导航','门禁私人导航'],
  ...functionalRoutes
};
const visibleCount=async(p,sel)=>await p.locator(sel).evaluateAll(es=>es.filter(e=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&r.width>0&&r.height>0}).length);
const text=async p=>(await p.locator('body').innerText()).replace(/\s+/g,' ');
const noOverflow=async(p,label)=>{const d=await p.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth);A(d===0,`${label} overflow=${d}`)};
const assertLegacyStartLogin=async(p,width)=>{
  if(width===390){
    const mobile=p.locator('#mobileAccount');
    A(await visibleCount(p,'#mobileAccount')===1,'legacy mobile account entry not visible');
    A((await mobile.innerText()).trim()==='登录','legacy mobile account label is not 登录');
    await mobile.click();
  }else{
    const desktop=p.locator('#loginButton');
    A(await visibleCount(p,'#loginButton')===1,'legacy desktop login entry not visible');
    A((await desktop.innerText()).trim()==='登录','legacy desktop login label is not 登录');
    await desktop.click();
  }
  const password=p.locator('input[type="password"]:visible').first();
  await password.waitFor({state:'visible',timeout:5000});
  A(await password.count()===1,'legacy login action did not open password UI');
};
const loginThroughWorkspace=async p=>{
  const trigger=p.locator('[data-vf-auth-login]:visible').first();
  A(await trigger.count()===1,'visible workspace login entry missing');
  await trigger.click();
  const dialog=p.locator('[data-vf-auth-dialog]');
  await dialog.waitFor({state:'visible'});
  await dialog.locator('input[name="password"]').fill(process.env.ADMIN_PASS);
  await dialog.locator('[data-vf-auth-submit]').click();
  await p.waitForFunction(()=>document.querySelectorAll('[data-vf-auth-logout]').length>0,{timeout:10000});
};
const logoutThroughWorkspace=async p=>{
  const trigger=p.locator('[data-vf-auth-logout]:visible').first();
  A(await trigger.count()===1,'visible workspace logout entry missing');
  await trigger.click();
  await p.waitForFunction(()=>document.querySelectorAll('[data-vf-auth-login]').length>0,{timeout:10000});
};
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME,args:['--no-sandbox']});
  const out={source:process.env.SOURCE,widths:{}};
  for(const width of [390,1440]){
    const height=width===390?844:900;
    const ctx=await browser.newContext({viewport:{width,height}});
    const p=await ctx.newPage();
    out.widths[width]={anonymous:{},legacyLoginAction:{},admin:{},logout:{}};

    // 1) Anonymous public Start uses the established legacy navigator.
    await p.goto(base+'start.php',{waitUntil:'domcontentloaded'});await p.waitForTimeout(220);
    let t=await text(p);
    A(t.includes('门禁公开导航'),'anonymous public navigation missing start.php');
    A(!t.includes('门禁私人导航'),'anonymous private navigation leaked start.php');
    A(await visibleCount(p,'a[href="links-admin.php"],a[href="settings.php"]')===0,'anonymous management entry visible start.php');
    await noOverflow(p,`anonymous start.php ${width}`);
    await assertLegacyStartLogin(p,width);
    out.widths[width].anonymous['start.php']='PASS';
    out.widths[width].legacyLoginAction['start.php']='PASS';

    // Navigate away from the legacy login UI without using it to establish auth.
    // The real login transition is verified through the shared Workspace auth control below.
    for(const [route,[pub,priv]] of Object.entries(functionalRoutes)){
      await p.goto(base+route,{waitUntil:'domcontentloaded'});await p.waitForTimeout(220);
      t=await text(p);
      A(t.includes(pub),`anonymous public missing ${route}`);
      A(!t.includes(priv),`anonymous private leak ${route}`);
      A(await visibleCount(p,'[data-vf-auth-login]')>0,`anonymous workspace login not visible ${route}`);
      A(await visibleCount(p,'[data-vf-auth-logout]')===0,`anonymous workspace logout visible ${route}`);
      A(await visibleCount(p,'a[href="links-admin.php"]')===0,`anonymous resource management visible ${route}`);
      A(await visibleCount(p,'a[href="settings.php"]')===0,`anonymous settings visible ${route}`);
      if(width===390)A(await visibleCount(p,'.vf-global-auth-action[data-vf-auth-login]')===1,`mobile workspace login not fixed in global nav ${route}`);
      await noOverflow(p,`anonymous ${route} ${width}`);
      out.widths[width].anonymous[route]='PASS';
    }

    // 2) Perform a real login through the visible Workspace UI.
    await p.goto(base+'channels.php',{waitUntil:'domcontentloaded'});await p.waitForTimeout(150);
    await loginThroughWorkspace(p);await p.waitForTimeout(250);

    // 3) The same frontend now shows public + private content and management capability.
    for(const [route,[pub,priv]] of Object.entries(allRoutes)){
      await p.goto(base+route,{waitUntil:'domcontentloaded'});await p.waitForTimeout(220);
      t=await text(p);
      A(t.includes(pub)&&t.includes(priv),`admin public/private missing ${route}`);
      A(await p.locator('a[href="links-admin.php"]').count()>0,`admin resource management DOM missing ${route}`);
      A(await p.locator('a[href="settings.php"]').count()>0,`admin settings DOM missing ${route}`);
      A(await visibleCount(p,'[data-vf-auth-logout]')>0,`admin logout entry not visible ${route}`);
      A(await visibleCount(p,'[data-vf-auth-login]')===0,`admin workspace login still visible ${route}`);
      if(width===1440){
        A(await visibleCount(p,'a[href="links-admin.php"]')>0,`desktop resource management not visible ${route}`);
        A(await visibleCount(p,'a[href="settings.php"]')>0,`desktop settings not visible ${route}`);
      }
      if(width===390)A(await visibleCount(p,'.vf-global-auth-action[data-vf-auth-logout]')===1,`mobile workspace logout not fixed in global nav ${route}`);
      await noOverflow(p,`admin ${route} ${width}`);
      out.widths[width].admin[route]='PASS';
    }

    // 4) Perform a real logout and prove the same route returns to public-only state.
    await p.goto(base+'channels.php',{waitUntil:'domcontentloaded'});await p.waitForTimeout(150);
    await logoutThroughWorkspace(p);await p.waitForTimeout(220);
    t=await text(p);
    A(t.includes('门禁公开频道')&&!t.includes('门禁私人频道'),'logout did not restore public-only channel state');
    A(await visibleCount(p,'[data-vf-auth-login]')>0,'workspace login missing after logout');
    A(await visibleCount(p,'[data-vf-auth-logout]')===0,'workspace logout remains visible after logout');
    out.widths[width].logout['channels.php']='PASS';

    // 5) Public Start must also return to its explicit legacy Login entry after logout.
    await p.goto(base+'start.php',{waitUntil:'domcontentloaded'});await p.waitForTimeout(180);
    t=await text(p);
    A(t.includes('门禁公开导航')&&!t.includes('门禁私人导航'),'legacy start not public-only after logout');
    if(width===390){A(await visibleCount(p,'#mobileAccount')===1,'mobile Login missing after logout');A((await p.locator('#mobileAccount').innerText()).trim()==='登录','mobile Login label wrong after logout');}
    else{A(await visibleCount(p,'#loginButton')===1,'desktop Login missing after logout');A((await p.locator('#loginButton').innerText()).trim()==='登录','desktop Login label wrong after logout');}
    out.widths[width].logout['start.php']='PASS';
    await ctx.close();
  }
  fs.writeFileSync(`${E}/browser-gate.json`,JSON.stringify({...out,verdict:'PASS'},null,2));
  await browser.close();
  console.log('P01_AUTH_ENTRY_BROWSER_GATE=PASS');
})().catch(e=>{console.error(e);process.exit(1)});
