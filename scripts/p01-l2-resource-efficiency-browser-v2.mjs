import { chromium } from 'playwright';
import fs from 'fs';

const base='http://127.0.0.1:18342';
const evidence='/tmp/p01-l2-resource-efficiency-evidence';
const ids=JSON.parse(fs.readFileSync('/tmp/p01-l2-ids.json','utf8'));
fs.mkdirSync(evidence,{recursive:true});
const events=[];
const record=(type,value)=>{events.push({type,value:String(value)});};
const browser=await chromium.launch({headless:true});
try{
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  const login=await context.request.post(base+'/api.php?action=login',{data:{password:'P01L2!Resource'}});
  const loginText=await login.text();
  if(!login.ok())throw new Error('login http '+login.status());
  let loginBody={};try{loginBody=JSON.parse(loginText)}catch{}
  if(!loginBody.ok)throw new Error('login rejected '+loginText);
  const cookies=await context.cookies(base);
  fs.writeFileSync(evidence+'/browser-login.json',JSON.stringify({status:login.status(),body:loginBody,cookies:cookies.map(x=>({name:x.name,path:x.path,domain:x.domain,httpOnly:x.httpOnly,sameSite:x.sameSite}))},null,2));

  const page=await context.newPage();
  page.on('pageerror',e=>record('pageerror',e.stack||e.message||e));
  page.on('console',m=>{if(['error','warning'].includes(m.type()))record('console-'+m.type(),m.text());});
  page.on('requestfailed',r=>record('requestfailed',r.url()+' '+(r.failure()?.errorText||'')));

  const visible=async selector=>await page.locator(selector).evaluate(el=>el.getClientRects().length>0&&getComputedStyle(el).visibility!=='hidden'&&getComputedStyle(el).display!=='none');
  const expectNoOverflow=async label=>{const s=await page.evaluate(()=>({doc:document.documentElement.scrollWidth,win:window.innerWidth}));if(s.doc>s.win+2)throw new Error(label+' overflow '+JSON.stringify(s));};
  const snapshot=async label=>{
    const state=await page.evaluate(()=>{
      let payload={};const node=document.querySelector('#vf-workspace-data');try{payload=JSON.parse(node?.textContent||'{}')}catch{}
      return {
        url:location.href,
        title:document.title,
        payloadNode:!!node,
        csrfLength:String(payload.csrf||'').length,
        assetKeys:Object.keys(payload.assets||{}).length,
        bulkbar:!!document.querySelector('[data-bulkbar]'),
        bulkPublic:!!document.querySelector('[data-bulk-visibility="public"]'),
        globalPlaceholder:document.querySelector('.vf-global-search input[name="q"]')?.getAttribute('placeholder')||'',
        scripts:Array.from(document.scripts).map(s=>s.src||'[inline]').filter(Boolean),
      };
    });
    fs.writeFileSync(evidence+`/${label}.json`,JSON.stringify({state,events},null,2));
    return state;
  };

  await page.goto(base+'/surfaces.php?per=100',{waitUntil:'networkidle'});
  await page.waitForTimeout(750);
  let state=await snapshot('desktop-entry-diagnostic');
  if(!state.url.includes('/surfaces.php'))throw new Error('owner route lost '+state.url);
  if(!state.payloadNode||state.csrfLength<8)throw new Error('owner payload/csrf missing '+JSON.stringify(state));
  if(!state.bulkbar)throw new Error('bulkbar missing '+JSON.stringify(state));
  if(!state.bulkPublic){
    throw new Error('bulk enhancement missing '+JSON.stringify({state,events}));
  }

  const desktopSearch=page.locator('.vf-global-search input[name="q"]');
  if(await desktopSearch.getAttribute('placeholder')!=='搜索全部资源')throw new Error('desktop search not global');
  await page.keyboard.press('Control+K');
  if(!(await desktopSearch.evaluate(el=>document.activeElement===el)))throw new Error('desktop ctrl+k target');
  await page.locator('[data-select-all]').check();
  const allResults=page.locator('[data-select-all-results]');
  await allResults.waitFor({state:'visible'});
  if(!(await allResults.textContent()).includes('423'))throw new Error('all-results CTA count');
  await allResults.click();
  await page.waitForFunction(()=>document.querySelectorAll('[data-select-asset]:checked').length===423);
  const selected=await page.locator('[data-select-asset]:checked').count();
  const synthetic=await page.locator('[data-cross-page-selection]').count();
  if(selected!==423||synthetic!==323)throw new Error('cross-page selection '+JSON.stringify({selected,synthetic}));
  if(!(await visible('[data-bulk-category]')))throw new Error('navigation category bulk capability hidden');
  if(!(await visible('[data-bulk-visibility="public"]')))throw new Error('public bulk action hidden');
  await expectNoOverflow('desktop bulk');
  await page.screenshot({path:evidence+'/desktop-cross-page-bulk.png',fullPage:true});

  const [bulkResponse]=await Promise.all([
    page.waitForResponse(r=>r.url().includes('/workspace-action.php')&&r.request().method()==='POST'),
    page.locator('[data-bulk-visibility="public"]').click(),
  ]);
  const bulkBody=await bulkResponse.text();
  fs.writeFileSync(evidence+'/bulk-response.txt',`HTTP=${bulkResponse.status()}\n${bulkBody}\n`);
  if(!bulkResponse.ok())throw new Error('bulk visibility http '+bulkResponse.status());
  await page.waitForTimeout(400);

  await page.goto(base+'/start.php?category='+ids.dev+'&per=100',{waitUntil:'networkidle'});
  const q=page.locator('.vf-global-search input[name="q"]');
  await q.fill('Needle Resource 423');
  await Promise.all([page.waitForNavigation({waitUntil:'networkidle'}),q.press('Enter')]);
  const u=new URL(page.url());
  if(!u.pathname.endsWith('/surfaces.php')||u.searchParams.get('q')!=='Needle Resource 423'||u.searchParams.has('category'))throw new Error('global search routing '+u.toString());
  if(!(await page.locator('.vf-workspace-count').textContent()).includes('1 项'))throw new Error('global search result count');
  await page.screenshot({path:evidence+'/desktop-global-search.png',fullPage:true});

  for(const [window,count] of [['7',1],['30',2],['90',3],['all',4]]){
    const url=window==='all'?base+'/surfaces.php?view=recent':base+'/surfaces.php?view=recent&recent_window='+window;
    await page.goto(url,{waitUntil:'networkidle'});
    const text=await page.locator('.vf-workspace-count').textContent();
    if(!text.includes(count+' 项'))throw new Error('recent '+window+' count '+text);
    await page.locator('select[aria-label="最近使用时间范围"]').waitFor();
    if(await page.locator('[data-recent-age]').count()<1)throw new Error('recent age missing '+window);
  }
  await page.screenshot({path:evidence+'/desktop-recent-all.png',fullPage:true});

  await page.setViewportSize({width:900,height:900});
  await page.goto(base+'/start.php?per=100',{waitUntil:'networkidle'});
  const categorySearch=page.locator('.vf-category-search input[data-category-search]');
  await categorySearch.waitFor();
  if(!(await visible('.vf-category-search')))throw new Error('900 category search hidden');
  await categorySearch.fill('AI');
  await page.waitForTimeout(100);
  const hiddenNodes=await page.locator('[data-category-node][data-filter-hidden="1"]').count();
  if(hiddenNodes<2)throw new Error('category filtering not applied');
  if(!(await page.locator('[data-category-node]',{hasText:'AI 资料'}).first().isVisible()))throw new Error('AI category not visible');
  await expectNoOverflow('900 category search');
  await page.screenshot({path:evidence+'/narrow-category-search.png',fullPage:true});

  await page.setViewportSize({width:390,height:844});
  await page.goto(base+'/surfaces.php?per=30',{waitUntil:'networkidle'});
  const mobileSearch=page.locator('.vf-mobile-command-search input[name="q"]');
  await mobileSearch.waitFor();
  if(!(await visible('.vf-mobile-command-search input[name="q"]')))throw new Error('mobile search hidden');
  if(await mobileSearch.getAttribute('placeholder')!=='搜索全部资源')throw new Error('mobile search not global');
  await page.keyboard.press('Control+K');
  if(!(await mobileSearch.evaluate(el=>document.activeElement===el)))throw new Error('mobile ctrl+k target');
  await expectNoOverflow('390 workspace');
  await page.screenshot({path:evidence+'/mobile-visible-search.png',fullPage:true});

  await page.goto(base+'/home.php',{waitUntil:'networkidle'});
  const homeMobile=page.locator('.vf-home-mobile-command form input[name="q"]');
  if(await homeMobile.count()){
    if(!(await visible('.vf-home-mobile-command form input[name="q"]')))throw new Error('home mobile search hidden');
    await page.keyboard.press('Control+K');
    if(!(await homeMobile.evaluate(el=>document.activeElement===el)))throw new Error('home ctrl+k target');
  }
  await expectNoOverflow('390 home');
  await page.screenshot({path:evidence+'/mobile-home.png',fullPage:true});

  await snapshot('browser-final-diagnostic');
  fs.writeFileSync(evidence+'/browser-result.txt','P01_L2_BROWSER=PASS\n');
  console.log('P01_L2_BROWSER=PASS');
} catch(error){
  fs.writeFileSync(evidence+'/browser-error.txt',String(error?.stack||error)+'\n');
  fs.writeFileSync(evidence+'/browser-events.json',JSON.stringify(events,null,2));
  console.error(error);
  process.exitCode=1;
} finally {
  await browser.close();
}
