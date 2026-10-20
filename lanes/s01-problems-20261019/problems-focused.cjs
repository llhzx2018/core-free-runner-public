const {chromium}=require('playwright');const fs=require('fs');
const checks=[];function check(name,pass,detail){checks.push({name,pass:!!pass,detail});if(!pass)throw Error(name+': '+JSON.stringify(detail));}
const oldCss=fs.readFileSync('/tmp/prior-reading.css','utf8');
const cases=JSON.parse(fs.readFileSync('proof/cases.json','utf8')).cases;
async function metrics(page,context){return page.evaluate(context=>{
 const root=document.querySelector('.vf-theme-module-stack--'+context);
 const box=x=>{const r=x.getBoundingClientRect();return{x:r.x,y:r.y,right:r.right,bottom:r.bottom,width:r.width,height:r.height}};
 const rows=['.vf-article-hero-inner','.vf-reading-main','.vf-reading-support-shell','.vf-theme-module-frame--steps .container-wide','.vf-theme-module-frame--problems .container-wide','.vf-data-cta-box'].flatMap(sel=>[...root.querySelectorAll(sel)].filter(x=>x.getBoundingClientRect().height>0).map(x=>({sel,...box(x)})));
 const shell=root.querySelector('.vf-reading-shell');
 return{rows,article:box(root.querySelector('.vf-reading-article')),shell:box(shell),main:box(root.querySelector('.vf-reading-main')),className:shell.className,header:box(document.querySelector('#vf-site-header .vf-header-inner')),overflow:document.documentElement.scrollWidth>innerWidth+1,lang:document.documentElement.lang};
},context);}
(async()=>{const browser=await chromium.launch();try{
 const origin='http://127.0.0.1:18880';
 const before=await browser.newPage({viewport:{width:1440,height:1000}});
 await before.route('**/public-reading-final-owner.css*',r=>r.fulfill({status:200,contentType:'text/css',body:oldCss}));
 await before.goto(cases.en.problem_detail+'?vf_detail_mode=inline',{waitUntil:'networkidle'});
 const baseline=await metrics(before,'problem_detail');check('148 baseline uses header rail',Math.abs(baseline.rows[0].x-baseline.header.x)<2,baseline);
 await before.screenshot({path:'proof/reference-before-1440.png',fullPage:true});await before.close();
 for(const context of ['article_detail','guide_detail','problem_detail','glossary_detail'])for(const lang of ['en','zh'])for(const width of [1920,1440,1319,1024])for(const mode of ['inline','sidebar','off','wide','short']){
  const page=await browser.newPage({viewport:{width,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const url=cases[lang][context]+'?vf_detail_mode='+mode;
  const response=await page.goto(url,{waitUntil:'networkidle'});const m=await metrics(page,context),label=`${context}/${lang}/${width}/${mode}`;
  check(label+' correct route and language',response.status()===200&&(lang==='zh'?m.lang.startsWith('zh'):m.lang.startsWith('en'))&&await page.locator('body.vf-page-family-context--'+context).count()===1,m.lang);
  check(label+' shared left baseline',m.rows.length>=3&&m.rows.every(r=>Math.abs(r.x-m.rows[0].x)<2),m);
  check(label+' centered content group',Math.abs(m.rows[0].x-(width-m.rows[0].width)/2)<2,m);
  if(width>=1319)check(label+' reading group independent from header',m.rows[0].x>m.header.x+10,m);
  check(label+' saved reading width',Math.abs(m.article.width-Math.min(m.shell.width-(mode==='sidebar'?308:0),mode==='wide'?900:820))<2,m);
  check(label+' body and diagnostic column agree',Math.abs(m.main.width-m.article.width)<2,m);
  check(label+' no horizontal overflow',!m.overflow,m);
  check(label+' H1 and canonical',await page.locator('h1').count()===1&&await page.locator('link[rel=canonical]').count()===1);
  const toc=page.locator('.vf-reading-toc');
  if(['inline','wide'].includes(mode)){
   check(label+' inline directory before main',await toc.count()===1&&(await toc.boundingBox()).y+(await toc.boundingBox()).height<=m.main.y+1,m);
   check(label+' inline directory has no nested scroll',await toc.locator('nav').evaluate(x=>x.scrollHeight<=x.clientHeight+1));
  }
  if(mode==='sidebar')check(label+' directory right of body',(await page.locator('.vf-sidebar').boundingBox()).x>=m.main.right+40,m);
  if(mode==='off'||mode==='short')check(label+' no spurious directory',await toc.count()===0,m.className);
  if(mode==='inline'){
   const target=await toc.locator('a').first().getAttribute('href');await toc.locator('a').first().click();check(label+' directory anchor works',await page.evaluate(()=>decodeURIComponent(location.hash))===target);
   const faq=page.locator('.vf-reading-faq-list details').last();if(await faq.count()){const was=await faq.getAttribute('open')!==null;await faq.locator('summary').click();check(label+' FAQ disclosure changes',was!==(await faq.getAttribute('open')!==null));}
   const links=await page.locator('.vf-reading-tool-links a').evaluateAll(xs=>xs.map(x=>x.href));check(label+' existing tool routes',links.every(x=>x.startsWith('http://127.0.0.1:18880/')));
  }
  if(width===1440&&['inline','sidebar'].includes(mode)){await page.evaluate(()=>scrollTo(0,0));await page.waitForTimeout(150);await page.screenshot({path:`proof/reference-${context}-${lang}-${mode}.png`,fullPage:true});}
  check(label+' no script errors',errors.length===0,errors);await page.close();
 }
 // Reading final owner must not change unrelated families.
 for(const context of ['home','problem_index','basic_page']){
  const old=await browser.newPage({viewport:{width:1440,height:1000}});await old.route('**/public-reading-final-owner.css*',r=>r.fulfill({status:200,contentType:'text/css',body:oldCss}));await old.goto(cases.en[context],{waitUntil:'networkidle'});
  const now=await browser.newPage({viewport:{width:1440,height:1000}});await now.goto(cases.en[context],{waitUntil:'networkidle'});
  const rect=p=>p.locator('#content').evaluate(x=>{const r=x.getBoundingClientRect();return[r.x,r.width,r.height]});
  check(context+' geometry unchanged',JSON.stringify(await rect(old))===JSON.stringify(await rect(now)));await old.close();await now.close();
 }
 const admin=await browser.newPage({viewport:{width:1440,height:1000}});const target=origin+'/wp-admin/themes.php?page=vf-theme-modules&tab=layout&vf_review_tools=1';
 await admin.goto(origin+'/wp-login.php');await admin.locator('#user_login').fill('admin');await admin.locator('#user_pass').fill('Synthetic-Only-Update-54!');await admin.locator('input[name=redirect_to]').evaluate((e,v)=>e.value=v,target);await admin.locator('#wp-submit').click();await admin.waitForURL('**/wp-admin/**');await admin.waitForLoadState('networkidle');
 check('canonical directory has all 20 types',await admin.locator('[data-vf-page-context]').count()===20);
 const records=admin.locator('.vf-frontend-pages__progress-record');check('20 types plus 2 shared surfaces have criteria',await records.count()===22&&await records.locator('ul[aria-label="原型采用与检查要点"]').count()===22);
 const refs=await records.locator('a[target=_blank]').evaluateAll(xs=>xs.map(x=>x.href));check('all records have primary reference URL',refs.length===22&&refs.every(x=>/^https:\/\/(www.iloveimg.com|cloudconvert.com|www.cloudflare.com|developers.cloudflare.com)\//.test(x)),refs);
 check('mapping does not assert human acceptance',await admin.locator('.vf-frontend-pages__review-overview').innerText().then(x=>x.includes('本版人工确认 0 / 20')));
 await admin.locator('#vf-review-problem_detail > details > summary').click();await admin.locator('#vf-review-problem_detail .vf-frontend-pages__progress-record details > summary').click();await admin.screenshot({path:'proof/reference-admin-1440.png',fullPage:true});await admin.close();
 console.log('REFERENCE_READING_PASS',checks.length);
}finally{fs.writeFileSync('proof/reference-focused.json',JSON.stringify({status:checks.every(x=>x.pass)?'PASS':'FAIL',checks},null,2));await browser.close();}})().catch(e=>{console.error(e);process.exit(1)});
