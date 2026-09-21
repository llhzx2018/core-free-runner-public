import { chromium } from 'playwright';

const base=process.env.VF_R1_BASE_URL;
const password=process.env.VF_R1_PASSWORD;
if(!base||!password)throw new Error('missing R1 browser environment');
const assert=(ok,msg)=>{if(!ok)throw new Error(msg);};

const browser=await chromium.launch({headless:true});
const context=await browser.newContext({viewport:{width:1440,height:900}});
const page=await context.newPage();

async function login(){
  await page.goto(base+'/',{waitUntil:'networkidle'});
  const unlock=page.locator('[data-open-login]').first();
  if(await unlock.count()){
    await page.evaluate(()=>openLogin());
    await page.locator('#loginForm input[name="password"]').fill(password);
    await page.locator('#loginSubmit').click();
    await page.waitForFunction(async()=>{const j=await (await fetch('/api.php?action=session',{cache:'no-store'})).json();return !!j?.site?.auth;});
  }
}

try{
  await login();

  await page.evaluate(()=>{
    localStorage.removeItem('vftb-scratch-workspace-open-v1');
    localStorage.removeItem('vftb-scratch-active-v1');
  });
  await page.goto(base+'/?scratch=1',{waitUntil:'networkidle'});
  await page.waitForSelector('#scratchWorkspaceV259',{timeout:5000});
  assert(await page.locator('#scratchWorkspaceV259').count()===1,'Scratch quick route did not open workspace');
  console.log('P02_V2581_SCRATCH_QUICK_ROUTE=PASS');

  for(const section of ['system','updates','backup']){
    await page.goto(base+'/#settings='+section,{waitUntil:'networkidle'});
    await page.waitForSelector('#settingsPanel');
    const stateValue=await page.evaluate(()=>({mode:state.mode,section:state.settingsSection}));
    assert(stateValue.mode==='settings'&&stateValue.section===section,'settings deep link failed '+section+' '+JSON.stringify(stateValue));
  }
  console.log('P02_V2581_SETTINGS_DEEPLINKS=PASS');

  await page.setViewportSize({width:390,height:844});
  await page.goto(base+'/system-baseline.php',{waitUntil:'networkidle'});
  const baseline=await page.evaluate(()=>({
    scroll:document.documentElement.scrollWidth,
    client:document.documentElement.clientWidth,
    navHeights:[...document.querySelectorAll('nav a,nav strong')].map(n=>n.getBoundingClientRect().height)
  }));
  assert(baseline.scroll<=baseline.client+3,'system baseline mobile overflow '+JSON.stringify(baseline));
  assert(baseline.navHeights.every(h=>h>=43),'system baseline mobile nav touch target drift '+JSON.stringify(baseline));
  console.log('P02_V2581_BASELINE_MOBILE_CONTAINMENT=PASS');

  await page.goto(base+'/#settings=basic',{waitUntil:'networkidle'});
  await page.waitForSelector('#settingsPanel');
  const mobile=await page.evaluate(()=>{
    const q=s=>document.querySelector(s);
    const font=s=>parseFloat(getComputedStyle(q(s)).fontSize)||0;
    const h=s=>q(s)?.getBoundingClientRect().height||0;
    return {
      globalSearchFont:font('#globalSearch'),
      globalSearchHeight:h('#globalSearch'),
      settingInputFont:font('#settingsPanel input[name="site_title"]'),
      saveHeight:h('#saveSettings'),
      settingsBackHeight:h('#settingsBack')
    };
  });
  assert(mobile.globalSearchFont>=16&&mobile.settingInputFont>=16,'mobile form font baseline failed '+JSON.stringify(mobile));
  assert(mobile.globalSearchHeight>=43&&mobile.saveHeight>=43&&mobile.settingsBackHeight>=43,'mobile touch baseline failed '+JSON.stringify(mobile));
  console.log('P02_V2581_SHARED_MOBILE_BASELINE=PASS');

  await page.setViewportSize({width:1440,height:900});
  await page.goto(base+'/',{waitUntil:'networkidle'});
  const desktop=await page.evaluate(()=>{
    const wrap=document.querySelector('.v2537-nav-search-slot .search-wrap');
    return {searchHeight:wrap?.getBoundingClientRect().height||0,scroll:document.documentElement.scrollWidth,client:document.documentElement.clientWidth};
  });
  assert(Math.abs(desktop.searchHeight-36)<=1,'desktop compact search density regressed '+JSON.stringify(desktop));
  assert(desktop.scroll<=desktop.client+3,'desktop shell overflow '+JSON.stringify(desktop));
  console.log('P02_V2581_DESKTOP_DENSITY_PRESERVED=PASS');

  console.log('P02_V2581_R1_BROWSER=PASS');
} finally {
  await browser.close();
}
