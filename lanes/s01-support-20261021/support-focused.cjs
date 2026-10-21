const {chromium}=require('playwright'),fs=require('fs');
const cases=JSON.parse(fs.readFileSync('proof/cases.json','utf8')).cases,seed=JSON.parse(fs.readFileSync('proof/seed.json','utf8'));
const checks=[];function check(name,pass,detail){checks.push({name,pass:!!pass,detail});}
function url(base,state=''){const u=new URL(base);u.searchParams.set('vf_support_review','1');if(state)u.searchParams.set('review_state',state);return u.href;}
async function load(p,u){const r=await p.goto(u,{waitUntil:'load'});await p.evaluate(()=>document.fonts.ready);return r;}
async function geometry(p,key){const g=await p.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth+1,clipped:[...document.querySelectorAll('main h1,main h2,main h3')].filter(x=>x.getClientRects().length&&!x.classList.contains('screen-reader-text')&&x.scrollWidth>x.clientWidth+2).map(x=>x.textContent)}));check(key+' no page overflow',!g.overflow,g);check(key+' readable headings',!g.clipped.length,g);check(key+' one H1',await p.locator('main h1').count()===1);}
(async()=>{const browser=await chromium.launch();try{
 for(const lang of ['en','zh']){
  for(const width of [1920,1440,1319,1024])for(const context of ['about_page','contact_page','legal','basic_page','not_found','html_sitemap']){
   const p=await browser.newPage({viewport:{width,height:1000}}),errors=[];p.on('pageerror',e=>errors.push(e.message));const response=await load(p,url(cases[lang][context]));const key=`${lang}/${width}/${context}`;await geometry(p,key);check(key+' no script errors',!errors.length,errors);check(key+' correct HTTP status',response.status()===(context==='not_found'?404:200),response.status());
   if(width===1440){await p.screenshot({path:`proof/${context}-${lang}-${width}.png`,fullPage:true});
    if(context==='about_page')check(key+' owner body retained',(await p.locator('[data-vf-content-source="wordpress"]').first().textContent()).includes('Owner published text '+lang));
    if(context==='contact_page'){check(key+' actual email actionable',await p.locator('main a[href="mailto:support@example.invalid"]').count()===1);check(key+' no fabricated form',await p.locator('main form').count()===0);}
    if(context==='legal'){
     check(key+' official body retained',(await p.locator('.vf-policy-user-content').textContent()).includes('Owner published text '+lang));
     check(key+' current policy navigation',await p.locator('.vf-policy-nav a[aria-current="page"]').count()===1);
     const anchors=await p.locator('.vf-policy-section-toc a[href*="#"]').evaluateAll(xs=>xs.map(x=>x.hash));check(key+' section targets exist',anchors.length>=2&&await p.evaluate(hs=>hs.every(h=>!!document.getElementById(decodeURIComponent(h.slice(1)))),anchors),anchors);
     const policies=await p.locator('.vf-policy-nav a').evaluateAll(xs=>xs.map(x=>x.href));check(key+' policies use current language',policies.every(x=>(lang==='zh')===new URL(x).pathname.startsWith('/zh/')),policies);
    }
    if(context==='basic_page')check(key+' owner basic body retained',(await p.locator('main').textContent()).includes('Owner basic body '+lang+' retained.'));
    if(context==='not_found'){
     const form=p.locator('main form[role="search"]').first(),q=form.locator('input[type="search"]');await q.fill('Searchwork');await Promise.all([p.waitForURL(u=>u.searchParams.get('s')==='Searchwork'||u.searchParams.get('q')==='Searchwork'),q.press('Enter')]);check(key+' keyboard search recovers to real search',new URL(p.url()).pathname===(lang==='zh'?'/zh/':'/')||new URL(p.url()).pathname.includes('search'),p.url());check(key+' search keeps language',(lang==='zh')===new URL(p.url()).pathname.startsWith('/zh/'),p.url());
    }
    if(context==='html_sitemap'){
     const links=await p.locator('.vf-theme-sitemap-link').evaluateAll(xs=>xs.map(x=>({href:x.href,text:x.textContent})));check(key+' real public sitemap links',links.length>0&&links.every(x=>x.href.startsWith('http://127.0.0.1:18880/')&&!x.text.includes('HIDDEN')),links);check(key+' current-language links',links.every(x=>(lang==='zh')===new URL(x.href).pathname.startsWith('/zh/')),links);
    }
   }await p.close();
  }
  const p=await browser.newPage({viewport:{width:1024,height:1000}});
  for(const kind of ['basiclong','basicempty']){await load(p,url(seed.basic[lang][kind]));await geometry(p,lang+'/'+kind);if(kind==='basiclong')check(lang+' long body table and code retained',await p.locator('main table').count()===1&&(await p.locator('main pre').textContent()).includes('Owner preserved code'));else check(lang+' empty basic offers recovery',await p.locator('.vf-basic-page-empty').count()===1);}
  for(const state of ['empty','information']){
   await load(p,url(cases[lang].contact_page,state));await geometry(p,lang+'/contact/'+state);const text=await p.locator('main').textContent();check(lang+' contact '+state+' no invented contact method',await p.locator('main a[href^="mailto:"],main form').count()===0);
   if(state==='empty')check(lang+' empty contact explicit help',await p.locator('.vf-contact-no-channel a').count()>=2);
   else {check(lang+' contact instructions retained',text.includes('Owner informational guidance only'));check(lang+' informational content has no channel promise',!text.includes('Use a channel below')&&!text.includes('通过以下渠道发送'));}
  }
  await load(p,url(cases[lang].legal,'empty'));check(lang+' missing policy explicit state',await p.locator('.vf-policy-missing').count()===1);check(lang+' missing policy no invented text',await p.locator('.vf-policy-user-content').count()===0);await p.close();
 }
}finally{fs.writeFileSync('proof/support-focused.json',JSON.stringify({status:checks.every(x=>x.pass)?'PASS':'FAIL',checks},null,2));console.log('SUPPORT_RESULTS',checks.length,'FAIL',checks.filter(x=>!x.pass));await browser.close();}if(checks.some(x=>!x.pass))throw Error('Support focused checks failed');})().catch(e=>{console.error(e);process.exit(1)});
