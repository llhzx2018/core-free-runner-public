const {chromium}=require('playwright');const fs=require('fs');
const checks=[];function check(name,pass,detail){checks.push({name,pass:!!pass,detail});if(!pass)throw Error(name+': '+JSON.stringify(detail));}
const fixtures=JSON.parse(fs.readFileSync('proof/problems-fixture.json','utf8'));
const oldCss=fs.readFileSync('/tmp/prior-reading.css','utf8');
async function metrics(page){return page.evaluate(()=>{
 const root=document.querySelector('.vf-theme-module-stack--problem_detail');
 const sels=['.vf-article-hero-inner','.vf-reading-main','.vf-reading-support-shell','.vf-theme-module-frame--problems .container-wide','.vf-theme-module-frame--steps .container-wide','.vf-data-cta-box'];
 const rows=sels.flatMap(sel=>[...root.querySelectorAll(sel)].filter(x=>x.getBoundingClientRect().height>0).map(x=>{const r=x.getBoundingClientRect();return{sel,x:r.x,right:r.right,width:r.width}}));
 return {rows,overflow:document.documentElement.scrollWidth>innerWidth+1,main:root.querySelector('.vf-reading-main').getBoundingClientRect().toJSON(),shell:root.querySelector('.vf-reading-shell').className};
});}
(async()=>{const browser=await chromium.launch();try{
 const origin='http://127.0.0.1:18880';
 const old=await browser.newPage({viewport:{width:1440,height:1000}});
 await old.route('**/public-reading-final-owner.css*',route=>route.fulfill({status:200,contentType:'text/css',body:oldCss}));
 await old.goto(fixtures.en[0].url+'?vf_detail_mode=inline',{waitUntil:'networkidle'});
 const baseline=await metrics(old);const spread=Math.max(...baseline.rows.map(x=>x.x))-Math.min(...baseline.rows.map(x=>x.x));
 check('146 reproduces misaligned reading columns',spread>24,baseline);
 await old.screenshot({path:'proof/detail-before-1440.png',fullPage:true});await old.close();
 for(const lang of ['en','zh'])for(const width of [1440,1024])for(const mode of ['inline','sidebar','off','wide','short']){
  const page=await browser.newPage({viewport:{width,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const url=fixtures[lang][0].url+'?vf_detail_mode='+mode;
  const response=await page.goto(url,{waitUntil:'networkidle'});const m=await metrics(page);const label=`${lang}/${width}/${mode}`;
  check(label+' correct published language title',(await page.locator('h1').innerText()).trim()===fixtures[lang][0].title);
  check(label+' HTTP and module surfaces',response.status()===200&&m.rows.length>=5,m.rows);
  check(label+' common left edge',m.rows.every(r=>Math.abs(r.x-m.main.x)<=1.5),m);
  check(label+' common right edge',m.rows.every(r=>Math.abs(r.right-m.main.right)<=1.5),m);
  check(label+' no horizontal overflow',!m.overflow);
  check(label+' H1 and canonical',await page.locator('h1').count()===1&&await page.locator('link[rel=canonical]').count()===1);
  check(label+' saved reading width',mode!=='wide'||Math.abs(m.main.width-900)<2,m.main.width);
  const toc=page.locator('.vf-reading-toc');
  if(['inline','wide'].includes(mode))check(label+' inline TOC above content',(await toc.boundingBox()).y+(await toc.boundingBox()).height<=(await page.locator('.vf-reading-main').boundingBox()).y+1);
  if(mode==='sidebar')check(label+' sidebar beside article',(await page.locator('.vf-sidebar').boundingBox()).x>=m.main.right-1,m.shell);
  if(mode==='off')check(label+' TOC disabled',await toc.count()===0);
  if(mode==='inline'){
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
