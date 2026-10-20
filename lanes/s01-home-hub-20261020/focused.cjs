const {chromium}=require('playwright');
const fs=require('fs');
const cases=JSON.parse(fs.readFileSync('proof/cases.json','utf8')).cases;
const checks=[];
function check(name,pass,detail){checks.push({name,pass:!!pass,detail});if(!pass)throw Error(name+': '+JSON.stringify(detail));}
async function loaded(page,url){await page.goto(url,{waitUntil:'load'});await page.evaluate(()=>document.fonts.ready);}
async function geometry(page){return page.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth+1,main:document.querySelector('main').getBoundingClientRect().toJSON(),headings:[...document.querySelectorAll('main h1,main h2')].map(x=>({text:x.textContent,box:x.getBoundingClientRect().toJSON()})),clipped:[...document.querySelectorAll('main h1,main h2,main h3,main h4')].filter(x=>x.getClientRects().length&&x.scrollWidth>x.clientWidth+2).map(x=>x.textContent)}));}
(async()=>{const browser=await chromium.launch();try{
 for(const lang of ['en','zh'])for(const width of [1920,1440,1319,1024])for(const context of ['home','tool_hub']){
  const page=await browser.newPage({viewport:{width,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));await loaded(page,cases[lang][context]);
  const key=`${lang}/${width}/${context}`;const g=await geometry(page);check(key+' no horizontal overflow',!g.overflow,g);check(key+' no clipped headings',!g.clipped.length,g.clipped);check(key+' one H1',await page.locator('main h1').count()===1);check(key+' no script errors',!errors.length,errors);
  if(width===1440||width===1024)await page.screenshot({path:`proof/${context}-${lang}-${width}.png`,fullPage:true});
  if(context==='home'){
   const links=await page.locator('.vf-home-tools-grid a').evaluateAll(xs=>xs.map(x=>({href:x.href,label:x.textContent.trim()})));check(key+' available tools have direct links',links.length>0&&links.every(x=>x.href.startsWith(locationOrigin(cases[lang].home))&&x.label),links);
   const quick=page.locator('.vf-home-quick-start a');check(key+' first tool discoverable',await quick.count()>0);
   if(width===1440){const first=quick.first(),url=await first.getAttribute('href');await first.focus();await Promise.all([page.waitForURL(new URL(url,cases[lang].home).href),page.keyboard.press('Enter')]);check(key+' keyboard quick entry works',page.url()===url||page.url()===new URL(url,cases[lang].home).href,{url,actual:page.url()});}
  }else{
   const root=page.locator('[data-vf-directory-context="tool_hub"]');const query=root.locator('[data-vf-directory-query]');
   check(key+' directory initialized',await root.getAttribute('data-vf-directory-enhanced')==='true');
   const all=await root.locator('[data-vf-directory-item]').count();check(key+' tools available',all>0,{all});
   const routes=await root.locator('[data-vf-directory-item]').evaluateAll(xs=>xs.map(x=>x.getAttribute('data-vf-directory-route')));check(key+' distinct tools',new Set(routes).size===all,routes);
   await query.fill('vf-no-such-tool-xyz');check(key+' empty state visible',await root.locator('[data-vf-directory-empty]').isVisible());check(key+' empty count correct',await root.locator('[data-vf-directory-count]').textContent()==='0');
   await query.press('Escape');check(key+' escape resets local search',await root.locator('[data-vf-directory-item]:visible').count()===all);
   for(const filter of ['play','inspect','export','manage']){
    const url=await root.locator(`[data-vf-directory-filter-button="${filter}"]`).getAttribute('data-vf-directory-url');await Promise.all([page.waitForURL(url),root.locator(`[data-vf-directory-filter-button="${filter}"]`).click()]);await page.evaluate(()=>document.fonts.ready);
    const visible=await root.locator('[data-vf-directory-item]:visible').evaluateAll(xs=>xs.map(x=>x.getAttribute('data-vf-directory-category')));check(key+' category '+filter+' scope',visible.length>0&&visible.every(x=>x===filter),visible);
    check(key+' category '+filter+' URL retained',new URL(page.url()).searchParams.get('vf_filter')===filter);
    await Promise.all([page.waitForURL(cases[lang][context]),root.locator('[data-vf-directory-reset]').click()]);
   }
   const details=root.locator('.vf-directory-card-details').first();await details.locator('summary').focus();await page.keyboard.press('Enter');check(key+' keyboard details opens',await details.getAttribute('open')!==null);await page.keyboard.press('Enter');check(key+' keyboard details closes',await details.getAttribute('open')===null);
   check(key+' interaction leaves no overflow',!(await geometry(page)).overflow);
  }
  await page.close();
 }
 console.log('HOME_HUB_CURRENT_PASS',checks.length);
}finally{fs.writeFileSync('proof/home-hub.json',JSON.stringify({status:checks.every(x=>x.pass)?'PASS':'FAIL',checks},null,2));await browser.close();}})().catch(e=>{console.error(e);process.exit(1)});
function locationOrigin(url){return new URL(url).origin;}
