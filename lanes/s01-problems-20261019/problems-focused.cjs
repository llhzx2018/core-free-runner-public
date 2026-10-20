const {chromium}=require('playwright');const fs=require('fs');
const checks=[];function check(name,pass,detail){checks.push({name,pass:!!pass,detail});if(!pass)throw Error(name+': '+JSON.stringify(detail));}
const oldCss=fs.readFileSync('/tmp/prior-public.css','utf8');
const cases=JSON.parse(fs.readFileSync('proof/cases.json','utf8')).cases;
async function setup(page,lang,width,baseline=false){if(baseline)await page.route('**/vf-theme-public-runtime.css*',r=>r.fulfill({status:200,contentType:'text/css',body:oldCss}));await page.setViewportSize({width,height:1000});await page.goto(cases[lang].home,{waitUntil:'load'});await page.evaluate(()=>document.fonts.ready);}
async function variant(page,mode){await page.evaluate(mode=>{const w=document.querySelector('.vf-production-footer-wrap');if(['one','two','three','four'].includes(mode)){for(const c of [...w.classList])if(c.startsWith('vf-footer-columns-'))w.classList.remove(c);w.classList.add('vf-footer-columns-'+mode);}if(['simple','seo'].includes(mode)){for(const c of [...w.classList])if(c.startsWith('vf-footer-variant-'))w.classList.remove(c);w.classList.add('vf-footer-variant-'+mode);}if(mode==='short')document.querySelectorAll('[data-vf-menu-location=footer_tools] .vf-footer-section-panel > :nth-child(n+3)').forEach(x=>x.remove());if(mode==='missing')document.querySelector('[data-vf-menu-location=footer_company]').remove();},mode);}
async function metrics(page){return page.evaluate(()=>{const f=document.querySelector('[data-site-footer]'),w=f.querySelector('.vf-production-footer-wrap'),g=f.querySelector('.vf-production-footer-grid'),t=f.querySelector('[data-vf-menu-location=footer_tools] .vf-footer-section-panel');const box=x=>{const r=x.getBoundingClientRect();return{x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom}};return{height:f.getBoundingClientRect().height,grid:box(g),tools:box(t),links:[...t.querySelectorAll('a')].map(x=>({text:x.textContent,url:x.href,target:x.target,rel:x.rel,...box(x)})),content:box(document.querySelector('#content')),header:box(document.querySelector('#vf-site-header')),overflow:document.documentElement.scrollWidth>innerWidth+1,classes:w.className};});}
const identity=m=>m.links.map(({text,url,target,rel})=>({text,url,target,rel}));
(async()=>{const browser=await chromium.launch();try{
 for(const lang of ['en','zh'])for(const width of [1920,1440,1319,1024])for(const mode of ['three','four','one','two','seo','simple','short','missing']){
  const before=await browser.newPage(),now=await browser.newPage();await setup(before,lang,width,true);await setup(now,lang,width);await variant(before,mode);await variant(now,mode);const a=await metrics(before),b=await metrics(now),label=`${lang}/${width}/${mode}`;
  check(label+' no link removed or reordered',JSON.stringify(identity(a))===JSON.stringify(identity(b)),{a:identity(a),b:identity(b)});
  check(label+' no horizontal overflow',!b.overflow,b);
  check(label+' header and content geometry unchanged',JSON.stringify(a.header)===JSON.stringify(b.header)&&JSON.stringify(a.content)===JSON.stringify(b.content),{a,b});
  if(['three','four'].includes(mode)){
   const xs=[...new Set(b.links.map(x=>Math.round(x.x)))];check(label+' 15 links use two columns',b.links.length===15&&xs.length===2,{xs,b});
   check(label+' footer height reduced at least 20 percent',b.height<=a.height*.8,{old:a.height,new:b.height});
   check(label+' links contained by tools region',b.links.every(x=>x.x>=b.tools.x-1&&x.right<=b.tools.right+1),b);
   check(label+' original column reading order',b.links.every((x,i)=>!i||x.x>b.links[i-1].x+10||x.y>=b.links[i-1].bottom-1),b.links);
   if(width===1440&&mode==='three'){
    await before.locator('[data-site-footer]').screenshot({path:`proof/footer-before-${lang}.png`});await now.locator('[data-site-footer]').screenshot({path:`proof/footer-after-${lang}.png`});
    const links=now.locator('[data-vf-menu-location=footer_tools] .vf-footer-section-panel a');await links.first().focus();for(let i=1;i<15;i++){await now.keyboard.press('Tab');check(label+' keyboard menu order '+i,await links.nth(i).evaluate(x=>x===document.activeElement));}
    const href=await links.last().getAttribute('href');await links.last().click();check(label+' existing destination opens',now.url()===href);
   }
  }else{check(label+' alternate layout geometry unchanged',JSON.stringify(a)===JSON.stringify(b),{a,b});}
  await before.close();await now.close();
 }
 // Shared-footer coverage uses the canonical case inventory, not a second route list.
 for(const lang of ['en','zh'])for(const [context,url]of Object.entries(cases[lang])){
  const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(url,{waitUntil:'load'});await page.evaluate(()=>document.fonts.ready);
  const m=await metrics(page);check(`${lang}/${context} one footer and all 15 links`,await page.locator('[data-site-footer]').count()===1&&m.links.length===15);check(`${lang}/${context} no overflow or script errors`,!m.overflow&&errors.length===0,{overflow:m.overflow,errors});await page.close();
 }
 console.log('FOOTER_DENSITY_PASS',checks.length);
}finally{fs.writeFileSync('proof/footer-focused.json',JSON.stringify({status:checks.every(x=>x.pass)?'PASS':'FAIL',checks},null,2));await browser.close();}})().catch(e=>{console.error(e);process.exit(1)});
