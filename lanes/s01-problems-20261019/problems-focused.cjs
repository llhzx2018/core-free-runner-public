const {chromium}=require('playwright');const fs=require('fs');
const checks=[];function check(name,pass,detail){checks.push({name,pass:!!pass,detail});if(!pass)throw Error(name+': '+JSON.stringify(detail));}
const fixtures=JSON.parse(fs.readFileSync('proof/problems-fixture.json','utf8'));
const oldCss=fs.readFileSync('/tmp/prior-reading.css','utf8');
async function metrics(page){return page.evaluate(()=>{
 const root=document.querySelector('.vf-theme-module-stack--problem_detail');
 const sels=['.vf-article-hero-inner','.vf-reading-main','.vf-reading-support-shell','.vf-theme-module-frame--problems .container-wide','.vf-theme-module-frame--steps .container-wide','.vf-data-cta-box'];
 const rows=sels.flatMap(sel=>[...root.querySelectorAll(sel)].filter(x=>x.getBoundingClientRect().height>0).map(x=>{const r=x.getBoundingClientRect();return{sel,x:r.x,right:r.right,width:r.width}}));
 return {rows,overflow:document.documentElement.scrollWidth>innerWidth+1,header:document.querySelector('#vf-site-header .vf-header-inner').getBoundingClientRect().toJSON(),brand:document.querySelector('#vf-site-header .vf-brand').getBoundingClientRect().toJSON(),article:root.querySelector('.vf-reading-article').getBoundingClientRect().toJSON(),diagnostic:root.querySelector('.vf-problem-diagnostic-panel').getBoundingClientRect().toJSON(),main:root.querySelector('.vf-reading-main').getBoundingClientRect().toJSON(),shell:root.querySelector('.vf-reading-shell').className};
});}
(async()=>{const browser=await chromium.launch();try{
 const origin='http://127.0.0.1:18880';
 const old=await browser.newPage({viewport:{width:1440,height:1000}});
 await old.route('**/public-reading-final-owner.css*',route=>route.fulfill({status:200,contentType:'text/css',body:oldCss}));
 await old.goto(fixtures.en[0].url+'?vf_detail_mode=inline',{waitUntil:'networkidle'});
 const baseline=await metrics(old);const spread=baseline.main.x-baseline.brand.x;
 check('147 reproduces inset from Header logo',spread>24,baseline);
 await old.screenshot({path:'proof/detail-before-1440.png',fullPage:true});await old.close();
 for(const lang of ['en','zh'])for(const width of [1920,1440,1024])for(const mode of ['inline','sidebar','off','wide','short']){
  const page=await browser.newPage({viewport:{width,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const url=fixtures[lang][0].url+'?vf_detail_mode='+mode;
  const response=await page.goto(url,{waitUntil:'networkidle'});const m=await metrics(page);const label=`${lang}/${width}/${mode}`;
  check(label+' correct published language title',(await page.locator('h1').innerText()).trim()===fixtures[lang][0].title);
  check(label+' HTTP and module surfaces',response.status()===200&&m.rows.length>=5,m.rows);
  check(label+' aligns with Header logo',m.rows.every(r=>Math.abs(r.x-m.brand.x)<=1.5),m);
  check(label+' support modules use Header width',m.rows.filter(r=>r.sel!=='.vf-reading-main').every(r=>Math.abs(r.right-m.header.right)<=1.5),m);
  check(label+' diagnostic uses available column',Math.abs(m.diagnostic.width-m.main.width)<=1.5,m);
  check(label+' readable article width',Math.abs(m.article.width-Math.min(m.main.width,mode==='wide'?900:820))<=1.5,m);
  const captions=await page.locator('.vf-theme-module-stack--problem_detail .vf-family-section-head :is(h2,p),.vf-theme-module-stack--problem_detail .vf-reading-support-head :is(h2,p)').evaluateAll(xs=>xs.filter(x=>x.getBoundingClientRect().height>0).map(x=>({text:x.textContent,x:x.getBoundingClientRect().x})));
  check(label+' section heading and description alignment',captions.length>=4&&captions.every(r=>Math.abs(r.x-m.main.x)<=1.5),{main:m.main.x,captions});
  check(label+' no horizontal overflow',!m.overflow);
  check(label+' H1 and canonical',await page.locator('h1').count()===1&&await page.locator('link[rel=canonical]').count()===1);
  check(label+' saved reading width',mode!=='wide'||Math.abs(m.article.width-900)<2,m.article.width);
  const toc=page.locator('.vf-reading-toc');
  if(['inline','wide'].includes(mode))check(label+' inline TOC above content',(await toc.boundingBox()).y+(await toc.boundingBox()).height<=(await page.locator('.vf-reading-main').boundingBox()).y+1);
  if(mode==='sidebar')check(label+' sidebar beside article',(await page.locator('.vf-sidebar').boundingBox()).x>=m.main.right-1,m.shell);
  if(mode==='off')check(label+' TOC disabled',await toc.count()===0);
  if(mode==='inline'){
   const columns=await toc.locator('ol a').evaluateAll(xs=>new Set(xs.map(x=>Math.round(x.getBoundingClientRect().x))).size);check(label+' compact inline TOC',columns===2,columns);
   const target=await toc.locator('a').first().getAttribute('href');await toc.locator('a').first().click();
   check(label+' TOC link works',(await page.evaluate(()=>decodeURIComponent(location.hash)))===target);
   await page.goto(url,{waitUntil:'networkidle'});
   const faq=page.locator('.vf-reading-faq-list details').last();if(await faq.count()){await faq.locator('summary').click();check(label+' FAQ disclosure',await faq.getAttribute('open')!==null);}
   const links=await page.locator('.vf-reading-tool-links a,.vf-problem-diagnostic-tool').evaluateAll(xs=>xs.map(x=>x.href));check(label+' tool routes',links.length>0&&links.every(x=>x.startsWith('http://127.0.0.1:18880/')));
   await page.evaluate(()=>scrollTo(0,0));await page.waitForTimeout(150);
   await page.screenshot({path:`proof/detail-${lang}-${width}.png`,fullPage:true});
  }
  check(label+' no script errors',errors.length===0,errors);await page.close();
 }
 // Unchanged page families must retain their exact baseline geometry.
 const cases=JSON.parse(fs.readFileSync('proof/cases.json','utf8')).cases;
 for(const context of ['guide_detail','article_detail']){
  const url=cases.en[context];const before=await browser.newPage({viewport:{width:1440,height:1000}});
  await before.route('**/public-reading-final-owner.css*',route=>route.fulfill({status:200,contentType:'text/css',body:oldCss}));await before.goto(url,{waitUntil:'networkidle'});
  const rect=p=>p.locator('.vf-article-hero-inner,.vf-reading-main,.vf-reading-support-shell').evaluateAll(xs=>xs.map(x=>{const r=x.getBoundingClientRect();return[r.x,r.width]}));
  const a=await rect(before);const after=await browser.newPage({viewport:{width:1440,height:1000}});await after.goto(url,{waitUntil:'networkidle'});const b=await rect(after);
  check(context+' unchanged geometry',JSON.stringify(a)===JSON.stringify(b),{a,b});await before.close();await after.close();
 }
 console.log('DETAIL_ALIGNMENT_PASS',checks.length);
}finally{fs.writeFileSync('proof/detail-focused.json',JSON.stringify({status:checks.every(x=>x.pass)?'PASS':'FAIL',checks},null,2));await browser.close();}})().catch(e=>{console.error(e);process.exit(1)});
