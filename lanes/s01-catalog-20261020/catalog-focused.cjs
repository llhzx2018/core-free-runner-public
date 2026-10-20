const {chromium}=require('playwright'),fs=require('fs');
const cases=JSON.parse(fs.readFileSync('proof/cases.json','utf8')).cases;
const seed=JSON.parse(fs.readFileSync('proof/seed.json','utf8'));
const checks=[];function check(name,pass,detail){checks.push({name,pass:!!pass,detail});if(!pass)throw Error(name+': '+JSON.stringify(detail));}
function url(base,args={}){const u=new URL(base);u.searchParams.set('vf_catalog_review','1');for(const[k,v]of Object.entries(args))u.searchParams.set(k,v);return u.href;}
async function load(page,u){await page.goto(u,{waitUntil:'load'});await page.evaluate(()=>document.fonts.ready);}
const directory=p=>p.locator('[data-vf-directory-context]').first();
const identities=p=>directory(p).locator('[data-vf-directory-item]').evaluateAll(xs=>xs.map(x=>x.href));
async function geometry(page,key){const g=await page.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth+1,clipped:[...document.querySelectorAll('main h1,main h2,main h3')].filter(x=>x.getClientRects().length&&!x.classList.contains('screen-reader-text')&&x.scrollWidth>x.clientWidth+2).map(x=>x.textContent)}));check(key+' no horizontal overflow',!g.overflow,g);check(key+' no clipped heading',!g.clipped.length,g);check(key+' one H1',await page.locator('main h1').count()===1);}
async function escapeReset(page,key,clearFirst=false){const root=directory(page),query=root.locator('[data-vf-directory-query]');check(key+' server filtered',await root.getAttribute('data-vf-directory-server-filter')==='true');const reset=await root.locator('[data-vf-directory-reset]').getAttribute('href');if(clearFirst)await query.fill('');await query.focus();await Promise.all([page.waitForURL(reset),query.press('Escape')]);await page.waitForLoadState('load');check(key+' real reset removes filters and paging',!['vf_q','vf_filter','vf_letter','paged','page'].some(k=>new URL(page.url()).searchParams.has(k)),page.url());check(key+' original scope restored',await identities(page).then(x=>x.length>0));}
(async()=>{const browser=await chromium.launch();try{
 // The old actual script must reproduce the stale empty result before accepting the fix.
 const old=await browser.newPage();let oldHits=0;await old.route('**/assets/js/main.js*',r=>{oldHits++;return r.fulfill({status:200,contentType:'text/javascript',body:fs.readFileSync('/tmp/prior-main.js','utf8')});});
 await load(old,url(cases.en.blog_index,{vf_q:'vf-no-match-xyz'}));await directory(old).locator('[data-vf-directory-query]').press('Escape');await old.waitForTimeout(150);check('prior source reproduces stale filtered URL and zero cards',oldHits>0&&new URL(old.url()).searchParams.has('vf_q')&&(await identities(old)).length===0,{oldHits,url:old.url()});await old.close();
 for(const lang of ['en','zh']){
  const rows=['blog_index','guide_index','problem_index','glossary_index','archive_list','search'].map(context=>({context,url:cases[lang][context]}));
  for(const width of [1920,1440,1319,1024])for(const row of rows){
   const p=await browser.newPage({viewport:{width,height:1000}}),errors=[];p.on('pageerror',e=>errors.push(e.message));await load(p,url(row.url));const key=`${lang}/${width}/${row.context}`;await geometry(p,key);check(key+' no script errors',!errors.length,errors);if(width===1440)await p.screenshot({path:`proof/${row.context}-${lang}-${width}.png`,fullPage:true});
   const links=await p.locator('main [data-vf-directory-item]').evaluateAll(xs=>xs.map(x=>({href:x.href,text:x.textContent})));check(key+' only current-language public cards',links.length>0&&links.every(x=>(lang==='zh'?new URL(x.href).pathname.startsWith('/zh/'):!new URL(x.href).pathname.startsWith('/zh/'))&&!x.text.includes('HIDDEN')),links);
   if(row.context!=='search'){
    const root=directory(p),q=root.locator('[data-vf-directory-query]'),original=await identities(p);await q.fill('vf-local-no-match-xyz');check(key+' local empty state',await root.locator('[data-vf-directory-empty]').isVisible());const prior=p.url();await q.press('Escape');check(key+' local Escape stays on page and restores cards',p.url()===prior&&JSON.stringify(await identities(p))===JSON.stringify(original));
    if(width===1440){
     await load(p,url(row.url,{vf_q:'vf-no-match-xyz'}));check(key+' native empty result has zero cards',(await identities(p)).length===0);await escapeReset(p,key+' empty Escape');check(key+' full first page restored exactly',JSON.stringify(await identities(p))===JSON.stringify(original));
     await load(p,url(row.url,{vf_q:'vf-no-match-xyz'}));await escapeReset(p,key+' already blank input Escape',true);
     const filter=root.locator('[data-vf-directory-filter-button]:not([data-vf-directory-filter-button="all"])').first();if(await filter.count()){
      const dest=await filter.getAttribute('data-vf-directory-url')||await filter.getAttribute('href');await load(p,dest);const chosen=await root.getAttribute('data-vf-directory-active-filter');check(key+' native category scope',await root.locator('[data-vf-directory-item]').evaluateAll((xs,v)=>xs.length>0&&xs.every(x=>x.getAttribute('data-vf-directory-category')===v),chosen));await escapeReset(p,key+' category Escape');
     }
     if(row.context==='glossary_index'){
      await load(p,url(row.url,{vf_letter:'a'}));check(key+' native letter scope',await root.locator('[data-vf-directory-item]').evaluateAll(xs=>xs.length>0&&xs.every(x=>x.getAttribute('data-vf-directory-letter')==='a')));await escapeReset(p,key+' letter Escape');
     }
     const next=p.locator('.vf-theme-pagination a.next').first();if(await next.count()){
      const dest=await next.getAttribute('href');await load(p,dest);const second=await identities(p);const disjoint=second.length>0&&second.every(x=>!original.includes(x));const info={dest,actual:p.url(),original,second,diag:(await p.content()).match(/search-archive-diag:([\s\S]*?) -->/)?.[1]};checks.push({name:key+' pages have disjoint cards',pass:disjoint,detail:info});if(!disjoint){fs.writeFileSync(`proof/pagination-${row.context}-${lang}.html`,await p.content());console.log('CATALOG_PAGINATION_DIAG',JSON.stringify(info));}
      if(['guide_index','problem_index','glossary_index'].includes(row.context)){
       const seen=[...original,...second];let more=p.locator('.vf-theme-pagination a.next').first();let pages=2;
       while(await more.count()){
        check(key+' bounded next-page traversal',pages<10);await load(p,await more.getAttribute('href'));const part=await identities(p);check(key+' later pages remain disjoint',part.length>0&&part.every(x=>!seen.includes(x)),{pages,part,seen});seen.push(...part);pages++;more=p.locator('.vf-theme-pagination a.next').first();
       }
       check(key+' all-page results unique',seen.length===new Set(seen).size,{seen,pages});
      }
      const word=(await root.locator('[data-vf-directory-item] h3').first().textContent()).trim().split(/\s+/)[0];await load(p,url(row.url,{vf_q:word,paged:'2'}));await escapeReset(p,key+' paginated Escape');
     }
    }
   }else if(width===1440){
    const input=p.locator('[name="s"]').first();check(key+' query preserved',await input.inputValue()==='Searchwork');
    const first=links.map(x=>x.href),next=p.locator('.vf-theme-pagination--search a.next').first();if(await next.count()){await load(p,await next.getAttribute('href'));const second=await p.locator('.vf-theme-search-results-grid a[data-vf-directory-item]').evaluateAll(xs=>xs.map(x=>x.href));check(key+' search page preserves query and disjoint result',new URL(p.url()).searchParams.get('s')==='Searchwork'&&second.length>0&&second.every(x=>!first.includes(x)));}
    const article=p.locator('[data-vf-search-type-filters] a[href*="type=article"]').first();await load(p,await article.getAttribute('href'));check(key+' search type is article',await p.locator('[data-vf-search-type]').evaluateAll(xs=>xs.length>0&&xs.every(x=>x.getAttribute('data-vf-search-type')==='article')));
    await load(p,url(cases[lang].home,{s:'vf-no-match-xyz'}));check(key+' search empty recovery visible',await p.locator('.vf-theme-search-empty-state').isVisible());const clear=await p.locator('.vf-theme-search-clear').getAttribute('href');await load(p,clear);check(key+' clear search removes submitted query',!new URL(p.url()).searchParams.has('s')&&!new URL(p.url()).searchParams.has('q'));
   }
   await p.close();
  }
  // Native archive variants come from the seeded WordPress term/author/date identities.
  for(const kind of ['category','tag','author','year','month','day']){
   const row=seed.archives[lang][kind],p=await browser.newPage({viewport:{width:1440,height:1000}}),key=`${lang}/archive/${kind}`;await load(p,url(row.url));await geometry(p,key);const cards=await identities(p);check(key+' bounded current archive',cards.length>0&&cards.every(x=>row.urls.includes(x)),{cards,allowed:row.urls});await load(p,url(row.url,{vf_q:'vf-no-match-xyz'}));await escapeReset(p,key+' empty Escape');check(key+' scope retained after reset',(await identities(p)).every(x=>row.urls.includes(x)));await p.close();
  }
 }
 if(checks.some(x=>!x.pass))throw Error('Catalog diagnostic collected failing assertions');
 console.log('CATALOG_RECOVERY_PASS',checks.length);
}finally{fs.writeFileSync('proof/catalog-focused.json',JSON.stringify({status:checks.every(x=>x.pass)?'PASS':'FAIL',checks},null,2));await browser.close();}})().catch(e=>{console.error(e);process.exit(1)});
