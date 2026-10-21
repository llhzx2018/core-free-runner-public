const {chromium}=require('playwright'),fs=require('fs');
const seed=JSON.parse(fs.readFileSync('proof/seed.json','utf8')),cases=JSON.parse(fs.readFileSync('proof/cases.json','utf8')).cases,baseline=process.argv[2]==='baseline';
const checks=[];function check(name,pass,detail){checks.push({name,pass:!!pass,detail});if(!pass)throw Error(name+': '+JSON.stringify(detail));}
const root=p=>p.locator('[data-vf-directory-context="archive_list"]').first(),cards=p=>root(p).locator('[data-vf-directory-item]'),visible=p=>root(p).locator('[data-vf-directory-item]:visible'),input=p=>root(p).locator('[data-vf-directory-query]'),reset=p=>root(p).locator('[data-vf-directory-reset]');
const ids=p=>cards(p).evaluateAll(xs=>xs.map(x=>x.href));
async function load(p,u){const r=await p.goto(u,{waitUntil:'load'});await p.evaluate(()=>document.fonts.ready);return r;}
async function seo(p){return p.evaluate(()=>({canonical:[...document.querySelectorAll('link[rel=canonical]')].map(x=>x.href),robots:[...document.querySelectorAll('meta[name=robots]')].map(x=>x.content),alternates:[...document.querySelectorAll('link[hreflang]')].map(x=>[x.hreflang,x.href])}));}
async function local(p,key){const before=await ids(p),start=p.url();await input(p).fill('vf-archive-check-no-match-20261021');
 check(key+' zero matches hide every real card',before.length>0&&await visible(p).count()===0);
 check(key+' zero count and empty feedback agree',await root(p).locator('[data-vf-content-result-count]').textContent().then(x=>x.trim()==='0')&&await root(p).locator('[data-vf-directory-empty]').isVisible());
 check(key+' clear action becomes visible',await reset(p).isVisible());
 await input(p).press('Escape');check(key+' Escape restores current page and all cards',p.url()===start&&await visible(p).count()===before.length&&JSON.stringify(await ids(p))===JSON.stringify(before));
 check(key+' restored clear and empty states are hidden',!await reset(p).isVisible()&&!await root(p).locator('[data-vf-directory-empty]').isVisible());
}
(async()=>{const b=await chromium.launch();try{
 if(baseline){const p=await b.newPage({viewport:{width:1440,height:1000}}),old={};for(const lang of ['en','zh']){await load(p,seed.archives[lang].author.url);old[lang+'-first']=await seo(p);await p.locator('main .pagination a.next').click();await p.waitForLoadState('load');old[lang+'-second']=await seo(p);}
 await load(p,seed.archives.en.author.url);await input(p).fill('vf-archive-check-no-match-20261021');
 check('160 reproduces hidden attribute overridden by grid',await cards(p).evaluateAll(xs=>xs.length>0&&xs.every(x=>x.hidden&&getComputedStyle(x).display!=='none')));
 check('160 reproduces missing local clear action',!await reset(p).isVisible());await p.screenshot({path:'proof/archive160-local-empty-before.png',fullPage:true});fs.writeFileSync('proof/prior-seo.json',JSON.stringify(old));console.log('ARCHIVE160_BASELINE_PASS');return;}
 const old=JSON.parse(fs.readFileSync('proof/prior-seo.json','utf8'));
 for(const lang of ['en','zh']){
  const row=seed.archives[lang].author;
  for(const width of [1920,1440,1319,1024]){const p=await b.newPage({viewport:{width,height:1000}}),errors=[];p.on('pageerror',e=>errors.push(e.message));const response=await load(p,row.url),key=lang+'/'+width+'/author';const original=await ids(p);
   check(key+' existing author scope and language preserved',response.status()===200&&original.length>0&&original.every(x=>row.urls.includes(x))&&(lang==='zh'?original.every(x=>x.includes('/zh/')):original.every(x=>!x.includes('/zh/'))));
   check(key+' initial cards really visible',await visible(p).count()===original.length&&!await reset(p).isVisible());await local(p,key);
   check(key+' one H1 and no overflow',await p.locator('main h1').count()===1&&await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   if(width===1440){
    check(key+' first-page SEO byte-equivalent to160',JSON.stringify(await seo(p))===JSON.stringify(old[lang+'-first']));
    await p.locator('main .pagination a.next').click();await p.waitForLoadState('load');const next=await ids(p);
    check(key+' next page is disjoint and same author',next.length>0&&next.every(x=>row.urls.includes(x)&&!original.includes(x)));
    check(key+' paginated SEO policy preserved',JSON.stringify(await seo(p))===JSON.stringify(old[lang+'-second']));await local(p,key+'/page2');
    await input(p).fill('vf-archive-check-no-match-20261021');await p.screenshot({path:`proof/archive161-${lang}-local-empty.png`,fullPage:true});
    await Promise.all([p.waitForURL(u=>u.searchParams.get('vf_q')==='vf-archive-check-no-match-20261021'),root(p).locator('button[type=submit]').click()]);await p.waitForLoadState('load');
    check(key+' native submit resets paging in same archive',new URL(p.url()).pathname===new URL(row.url).pathname&&await cards(p).count()===0&&await p.locator('main h1').textContent().then(x=>x.includes(row.name)));
    check(key+' server empty recovery retains real clear URL',await reset(p).isVisible()&&await reset(p).getAttribute('href')===row.url);
    await Promise.all([p.waitForURL(row.url),reset(p).click()]);await p.waitForLoadState('load');
    check(key+' clear restores exact first slice',JSON.stringify(await ids(p))===JSON.stringify(original)&&await visible(p).count()===original.length);
    await p.screenshot({path:`proof/archive161-${lang}-restored.png`,fullPage:true});
   }
   check(key+' no script errors',errors.length===0,errors);await p.close();
  }
  // Only local hidden-state regression for the other existing archive variants.
  for(const kind of ['category','tag','month']){const p=await b.newPage({viewport:{width:1440,height:1000}}),r=seed.archives[lang][kind];await load(p,r.url);const actual=await ids(p);check(lang+'/'+kind+' existing scope remains intact',actual.length>0&&actual.every(x=>r.urls.includes(x)));await local(p,lang+'/'+kind);await p.close();}
 }
 const p=await b.newPage({viewport:{width:1440,height:1000}});await load(p,cases.en.home);check('unrelated public home still available',await p.locator('main h1').count()===1);console.log('ARCHIVE_FOCUSED_PASS',checks.length);
 }finally{fs.writeFileSync('proof/'+(baseline?'baseline-results':'browser-results')+'.json',JSON.stringify({status:checks.every(x=>x.pass)?'PASS':'FAIL',count:checks.length,passed:checks.filter(x=>x.pass).length,checks},null,2));await b.close();}})().catch(e=>{console.error(e);process.exit(1)});
