const fs=require('fs'),cp=require('child_process'),{chromium}=require('playwright');
const checks=[];let browser;
function gate(pass,name,detail={}){checks.push({pass:!!pass,name,...detail});if(!pass)throw Error(name+': '+JSON.stringify(detail));}
const sourcePath='src/assets/css/public/vf-theme-public-runtime.css';
const css=fs.readFileSync('target/'+sourcePath,'utf8');
const baseline=cp.execFileSync('git',['-C','target','show',process.env.BASE_SHA+':'+sourcePath],{encoding:'utf8',maxBuffer:2e6});
const script=fs.readFileSync('target/src/assets/js/modules/public-shell-navigation.js','utf8');
const oldScript=cp.execFileSync('git',['-C','target','show',process.env.BASE_SHA+':src/assets/js/modules/public-shell-navigation.js'],{encoding:'utf8'});
async function setup(page,lang,old=false,js=true){
 await page.route('**/*',r=>r.abort());
 await page.setContent(fs.readFileSync('lane/fixture-'+lang+'.html','utf8'));
 // Match production order: the runtime bundle precedes runtime token styles.
 await page.evaluate(text=>{document.querySelector('[data-vf-test-runtime]').textContent=text},old?baseline:css);
 await page.evaluate(()=>document.querySelectorAll('.vf-site-header,.vf-production-footer').forEach(e=>e.setAttribute('data-vf-frontend-design','reference-v1')));
 if(js)await page.addScriptTag({content:old?oldScript:script});
 await page.evaluate(()=>document.fonts.ready);
}
async function measure(p){return p.evaluate(()=>{
 const rect=n=>{const r=n.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height,right:r.right,bottom:r.bottom,cy:r.y+r.height/2}};
 const header=document.querySelector('.vf-header-inner'),cta=document.querySelector('.vf-header-actions'),brand=document.querySelector('.vf-brand'),mark=document.querySelector('.vf-brand-mark');
 const footer=document.querySelector('.vf-production-footer-grid');
 let dot=null;if(mark){const d=getComputedStyle(mark,'::after'),s=getComputedStyle(mark),t=new DOMMatrix(d.transform==='none'?undefined:d.transform);dot={position:d.position,cx:parseFloat(s.borderLeftWidth)+parseFloat(d.left)+parseFloat(d.width)/2+t.e,cy:parseFloat(s.borderTopWidth)+parseFloat(d.top)+parseFloat(d.height)/2+t.f};}
 return {header:rect(header),cta:cta?rect(cta):null,brand:rect(brand),mark:mark?{...rect(mark),rows:getComputedStyle(mark).gridTemplateRows,dot}:null,footer:rect(footer),groups:[...footer.children].map(x=>({class:x.className,...rect(x)})),width:innerWidth,scroll:document.documentElement.scrollWidth};
});}
(async()=>{
 browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const p=await browser.newPage({viewport:{width:1440,height:1000}});
 for(const lang of ['en','zh-configured-synthetic'])for(const width of [1920,1440,1319,1024]){
  await p.setViewportSize({width,height:1000});await setup(p,lang);const m=await measure(p);
  gate(m.scroll<=width,'no desktop horizontal overflow',{lang,width,m});
  gate(m.cta&&Math.abs(m.cta.right-m.header.right)<1,'header actions align to container right edge',{lang,width,m});
  gate(Math.abs(m.brand.cy-m.cta.cy)<1,'header brand and actions share vertical center',{lang,width});
  gate(m.mark&&m.mark.dot.position==='absolute'&&Math.abs(m.mark.dot.cx-m.mark.w/2)<1&&Math.abs(m.mark.dot.cy-m.mark.h/2)<1,'brand dot is centered in both axes',{lang,width,m:m.mark});
  const navs=m.groups.slice(1);gate(navs.length===3&&navs.every(x=>Math.abs(x.y-navs[0].y)<1),'all three footer navigation headings share a row',{lang,width,m});
  gate(Math.abs(m.groups[0].y-navs[0].y)<1&&m.groups[0].x===m.footer.x,'brand and three navigation groups share the approved desktop row',{lang,width});
  await p.screenshot({path:'proof/candidate-'+lang+'-'+width+'.png',fullPage:true});
  // Existing one/two/four layouts retain their column settings and all links.
  const originalLinks=await p.locator('.vf-production-footer-grid a').count();
  for(const mode of ['one','two','four']){
   await p.evaluate(mode=>{const n=document.querySelector('[data-vf-footer-config]');n.classList.replace('vf-footer-columns-three','vf-footer-columns-'+mode);},mode);
   const z=await measure(p);gate(z.scroll<=width&&await p.locator('.vf-production-footer-grid a').count()===originalLinks,'alternate saved footer layout preserves links and fit',{lang,width,mode});
   await p.evaluate(mode=>document.querySelector('[data-vf-footer-config]').classList.replace('vf-footer-columns-'+mode,'vf-footer-columns-three'),mode);
  }
 }
 // The actual Chinese public output has no bound language menus. Preserve and
 // report that configuration gap; do not turn it into invented navigation.
 await p.setViewportSize({width:1440,height:1000});await setup(p,'zh');
 gate(await p.locator('[data-vf-footer-section]').count()===0&&await p.locator('#vf-site-header').getAttribute('data-vf-header-menu-id')==='0','actual Chinese unbound-menu configuration is reproduced and remains an explicit operational gap');
 gate((await measure(p)).scroll<=1440,'actual unbound Chinese shell still fits desktop viewport');
 await p.screenshot({path:'proof/actual-zh-unbound-1440.png',fullPage:true});
 // A real keyboard and pointer workflow, rather than an ARIA-only assertion.
 await p.setViewportSize({width:1440,height:1000});await setup(p,'en');
 const group=p.locator('#vf-primary-nav>.vf-nav-item.has-children').first(),a=group.locator(':scope > a'),panel=group.locator(':scope > .vf-nav-submenu');
 await a.focus();await a.press('ArrowDown');
 gate(await panel.isVisible()&&await panel.getAttribute('aria-hidden')==='false','ArrowDown opens the actual desktop panel');
 gate(await panel.evaluate(n=>n.contains(document.activeElement)),'ArrowDown moves focus into the panel');
 await p.keyboard.press('Escape');
 gate(!await panel.isVisible()&&await panel.getAttribute('aria-hidden')==='true'&&await a.getAttribute('aria-expanded')==='false','Escape closes the visual panel and ARIA state');
 gate(await a.evaluate(n=>document.activeElement===n),'Escape restores focus to the parent link');
 await a.press('ArrowDown');gate(await panel.isVisible(),'menu reopens with keyboard after dismissal');
 // Moving the mouse away must not hide a panel containing keyboard focus.
 await a.hover();await p.mouse.move(8,800);await p.waitForTimeout(250);
 gate(await panel.isVisible(),'mouse leave preserves a keyboard-focused panel');
 await p.keyboard.press('Escape');await p.mouse.click(8,800);await a.hover();
 gate(await panel.isVisible(),'pointer entry reopens a dismissed menu');
 await a.locator('.vf-nav-caret').click();gate(!await panel.isVisible(),'caret click really closes a hovered and focused menu');
 await a.locator('.vf-nav-caret').click();gate(await panel.isVisible(),'caret click reopens menu');
 await p.mouse.click(8,800);gate(!await panel.isVisible(),'outside click closes menu');
 // Optional header regions cannot create empty tracks.
 for(const remove of ['.vf-header-actions','#vf-primary-nav']){
  await setup(p,'en');await p.locator(remove).evaluate(n=>n.remove());const m=await measure(p);
  const right=await p.locator(remove==='.vf-header-actions'?'#vf-primary-nav':'.vf-header-actions').evaluate(n=>n.getBoundingClientRect().right);
  gate(Math.abs(right-m.header.right)<1,'remaining header region aligns when optional region is absent',{remove});
 }
 const ctx=await browser.newContext({javaScriptEnabled:false,viewport:{width:1440,height:1000}}),n=await ctx.newPage();
 // setContent/evaluation here are test harness CDP operations; site JavaScript remains disabled.
 await setup(n,'en',false,false);const ng=n.locator('#vf-primary-nav>.vf-nav-item.has-children').first();await ng.locator(':scope > a').focus();
 gate(await ng.locator('.vf-nav-submenu').isVisible(),'CSS keyboard submenu fallback remains available without site JavaScript');
 gate(await n.locator('.vf-production-footer-col a:visible').count()>10,'desktop footer links stay available without JavaScript');
 await ctx.close();
 fs.writeFileSync('proof/shell-result.json',JSON.stringify({status:'PASS',checks,source_sha:process.env.TARGET_SHA,source_tree:process.env.TARGET_TREE,scope:'public header/footer desktop CSS and dropdown dismissal',fixture:'EN and unbound ZH are anonymous public-rendered shells; populated ZH layout is explicitly synthetic',production_menu_gap:'OPEN_OWNER_CONFIGURATION: existing ZH menus have no Polylang term language/translation relations; zero runtime menu IDs observed',production_operational_readiness:'NOT_PASS',mobile:'NOT_RUN_OWNER_DEFERRED',full_product_ux:'NOT_CLAIMED',release:'NOT_EXECUTED'},null,2));
 await browser.close();
})().catch(async e=>{fs.writeFileSync('proof/shell-result.json',JSON.stringify({status:'FAIL',checks,error:e.stack},null,2));if(browser)await browser.close();process.exitCode=1;});
