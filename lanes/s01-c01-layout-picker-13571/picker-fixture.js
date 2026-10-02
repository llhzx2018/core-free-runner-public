const fs=require('fs'),assert=require('assert/strict'),{chromium}=require('playwright');
(async()=>{
 const base=process.env.PICKER_BASELINE==='1';
 const source=(process.env.PICKER_SRC||'layout-polish/src')+'/';
 const css=(base?fs.readFileSync('runner-polish/base-picker.css','utf8'):fs.readFileSync(source+'assets/css/admin/pages/page-structure/admin-page-layout-v8.css','utf8'));
 const script=fs.readFileSync(base?'runner-polish/base-picker.js':source+'assets/js/admin/admin-layout-page-refinement-v1.js','utf8');
 const browser=await chromium.launch({headless:true,executablePath:process.env.PICKER_CHROME,args:['--no-sandbox']});
 const font=fs.readFileSync(process.env.PICKER_FONT||'runtime/fonts/NotoSansSC.ttf').toString('base64');
 const cases=[];
 for(const width of [1920,1440,1319,1024,768,390]){
  const page=await browser.newPage({viewport:{width,height:900}});
  const groups=['核心页面','内容页面','系统页面'];
  const cards=(group)=>Array.from({length:group===2?6:7},(_,i)=>`<a href="/themes.php?context=${group}-${i}" class="vf-layout-context-card" data-vf-layout-context-card="${group}-${i}" data-search="页型 ${group}-${i}"><span class="vf-layout-context-card__top"><strong>${i===0?'当前页面':'文章详情页 '+(i+1)}</strong>${i===0?'<em>当前</em>':''}</span><span class="vf-layout-context-card__route"><small>前台路径</small><code>/guide/${'long-path-'.repeat(i+1)}</code><small>进入编辑</small></span><span class="vf-layout-context-card__meta"><b>3 模块</b><b>2 功能 · 24 控制</b><i data-status="connected">源码已接入</i><em>待真实验收</em><em>受控系统页</em></span></a>`).join('');
  await page.setContent(`<style>@font-face{font-family:Chinese;src:url(data:font/ttf;base64,${font})}body{margin:0;background:#f0f3f4}.vf-theme-admin{font-family:Arial,Chinese,sans-serif}a{text-decoration:none}.vf-layout-context-dialog{position:fixed;top:50%;left:50%;transform:translate(-50%,-50%)}.vf-layout-context-catalog>footer{display:flex;justify-content:space-between}.vf-layout-context-card__meta{display:flex}.vf-layout-context-group__head{padding:12px}.vf-layout-context-card__top em{font-size:13px}</style><style>${css}</style><div id="wpbody-content"><div class="vf-theme-admin"><div class="vf-v8-layout-page" data-vf-layout-page data-vf-page-id="THM-LAYOUT-001"><form data-vf-layout-form><input type="hidden" name="layout[title]" value="原始标题"></form><section class="vf-layout-context-dialog" data-vf-layout-context-catalog-dialog role="dialog" aria-modal="true"><section class="vf-layout-context-catalog" data-vf-layout-context-catalog><header><div><h2>切换前台页型</h2><p>选择后在同一工作区编辑该页型；有未保存内容时会先提醒。</p></div><div class="vf-layout-context-catalog__tools"><label><input type="search" placeholder="搜索名称、路径或标识"></label><button type="button" class="button">全部 20</button><button type="button" class="vf-layout-context-dialog__close">×</button></div></header><nav class="vf-layout-context-filters">${groups.map(g=>`<button type="button"><strong>${g}</strong><span>7</span></button>`).join('')}</nav><div class="vf-layout-context-groups">${groups.map((g,i)=>`<section class="vf-layout-context-group"><div class="vf-layout-context-group__head"><strong>${g}</strong></div><div class="vf-layout-context-grid">${cards(i)}</div></section>`).join('')}</div><footer><span>当前：首页</span><div><button type="button" class="button">返回当前页型</button></div></footer></section></section></div></div></div>`);
  await page.evaluate(()=>{window.initial=[...new FormData(document.querySelector('form'))];window.summaries=[...document.querySelectorAll('.vf-layout-context-card__meta')];window.links=[...document.querySelectorAll('a')].map(n=>n.href);});
  await page.addScriptTag({content:script});await page.evaluate(()=>document.fonts.ready);
  const toggle=page.locator('[data-vf-layout-context-info-toggle]');assert.equal(await toggle.count(),1);
  assert.equal(await page.locator('.vf-layout-context-card__meta:visible').count(),0);
  const geometry=await page.locator('.vf-layout-context-card').evaluateAll(nodes=>nodes.map(n=>{const r=n.getBoundingClientRect(),a=n.querySelector('.vf-layout-context-card__action').getBoundingClientRect();return {left:r.left,right:r.right,action:a.right,font:getComputedStyle(n.querySelector('strong')).fontSize};}));
  assert(geometry.every(n=>n.font==='16px'&&n.action<=n.right));assert(Math.max(...geometry.map(n=>n.left))-Math.min(...geometry.map(n=>n.left))<=1);
  assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1));
  if([1440,390].includes(width))await page.screenshot({path:'runner-polish/picker-'+width+'.png'});
  await toggle.focus();await page.keyboard.press('Enter');assert.equal(await page.locator('.vf-layout-context-card__meta:visible').count(),20);
  assert(await page.evaluate(()=>window.summaries.every(n=>document.querySelector('form').parentElement.contains(n))));
  assert.deepEqual(await page.evaluate(()=>[...new FormData(document.querySelector('form'))]),await page.evaluate(()=>window.initial));
  assert.deepEqual(await page.locator('a').evaluateAll(ns=>ns.map(n=>n.href)),await page.evaluate(()=>window.links));
  await toggle.click();assert.equal(await page.locator('.vf-layout-context-card__meta:visible').count(),0);
  cases.push({width,picker:'PASS',original_fields_links_and_metadata:'PASS',keyboard:'PASS',overflow:'PASS'});await page.close();
 }
 await browser.close();console.log(JSON.stringify({status:'PASS',scope:'Synthetic fixture; native WordPress validation required separately',cases}));
})().catch(e=>{console.error(e);process.exit(1)});
