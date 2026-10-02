const fs=require('fs'),assert=require('assert/strict');
const {chromium}=require('playwright');
const checkBrandPreview=require('../target/tests/brand-preview-browser-check');
const origin='http://127.0.0.1:18880';
const url=origin+'/wp-admin/themes.php?page=vf-theme-modules&tab=brand';
const input=key=>`[data-vf-brand-input="${key}"]`;
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const context=await browser.newContext(),page=await context.newPage();
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(origin+'/wp-login.php');
 await page.locator('#user_login').fill('admin');await page.locator('#user_pass').fill('Synthetic-Only-Update-54!');
 await Promise.all([page.waitForURL(/wp-admin/),page.locator('#wp-submit').click()]);
 let layout;try{layout=await require('../target/tests/layout-v8-browser-check')(page,context,browser,origin);}catch(error){await page.screenshot({path:'proof/layout-failure.png',fullPage:true});throw error;}
 const checks=[];
 for(const width of [1920,1440,1319,1024,768,390]){
  await page.setViewportSize({width,height:1000});await page.goto(url);
  await page.locator('[data-vf-native-body-v8="brand"]').waitFor();
  await page.evaluate(()=>document.fonts.ready);
  const state=await page.evaluate(()=>{
   const root=document.querySelector('[data-vf-native-body-v8="brand"]'),bar=document.querySelector('[data-vf-native-header-v8="brand"]');
   return {overflow:document.documentElement.scrollWidth>innerWidth+1,pagebar:bar.getBoundingClientRect().height,title:parseFloat(getComputedStyle(bar.querySelector('h1')).fontSize),label:parseFloat(getComputedStyle(root.querySelector('.vf-brand-field>span')).fontSize),control:parseFloat(getComputedStyle(root.querySelector('[data-vf-brand-input="siteName"]')).fontSize),fields:root.querySelectorAll('[data-vf-brand-input]').length,ownership:bar.textContent.includes('本页归属：VF Tools Theme 主题')};
  });
  assert(!state.overflow&&state.pagebar<=140&&state.title>=24&&state.label>=14&&state.control>=15&&state.fields===17&&!state.ownership,JSON.stringify({width,state}));
  const align=await page.evaluate(()=>{
   const root=document.querySelector('[data-vf-native-body-v8="brand"]'),head=document.querySelector('[data-vf-native-header-v8="brand"]'),shell=document.querySelector('.vf-admin-one-row-shell');
   const r=root.getBoundingClientRect(),h=head.getBoundingClientRect(),s=shell.getBoundingClientRect(),f=root.querySelector('.vf-brand-form').getBoundingClientRect(),title=head.querySelector('h1').getBoundingClientRect(),label=root.querySelector('.vf-brand-field>span').getBoundingClientRect();
   return {edges:[r.left-s.left,r.right-s.right,h.left-s.left,h.right-s.right],left:label.left-r.left,right:r.right-f.right,title:title.left-h.left,content:f.width};
  });
  assert(align.edges.every(n=>Math.abs(n)<=1)&&Math.abs(align.left-align.right)<=1&&Math.abs(align.left-align.title)<=1&&align.content<=904.1,JSON.stringify({width,align}));
  assert.equal(await page.locator('form form').count(),0);
  assert.equal(await page.locator('[data-vf-brand-workflow]').count(),0);
  assert(!await page.locator('[data-vf-brand-save]').isVisible());
  for(const id of ['identity','colors','layout'])assert(await page.locator('#vf-brand-step-'+id).isVisible());
  assert(await page.evaluate(()=>{
   const nodes=[...document.querySelectorAll('.vf-admin-one-row-inner,.vf-admin-topbar-brand,.vf-admin-topbar-pill,.vf-theme-domain-mobile')];
   const read=()=>nodes.map(n=>{const r=n.getBoundingClientRect(),s=getComputedStyle(n);return [r.width,r.height,s.fontSize,s.padding,s.backgroundColor]});
   const first=read(),sheet=[...document.styleSheets].find(s=>s.href?.includes('admin-page-brand-v8.css'));
   if(!sheet)return false;sheet.disabled=true;const second=read();sheet.disabled=false;return JSON.stringify(first)===JSON.stringify(second);
  }),'frozen header style changed');
  await page.screenshot({path:'proof/live-'+width+'.png',fullPage:true});
  assert(!await page.locator('#vf-brand-step-preview').isVisible());
  for (const selector of ['.vf-brand-tools','.vf-brand-inheritance','.vf-v9-brand-layout','.vf-v9-brand-recipes']) {
   assert(await page.locator(selector).evaluate(el=>el.getBoundingClientRect().height)<=56,'closed disclosure too tall');
  }
  await page.locator('[data-vf-brand-preview-open]').click();
  assert(await page.locator('#vf-brand-step-preview').isVisible());
  const preview=await checkBrandPreview(page,{width,screenshot:'proof/live-preview-'+width+'.png'});
  await page.setViewportSize({width,height:560});
  await checkBrandPreview(page,{width,screenshot:'proof/live-preview-short-'+width+'.png'});
  await page.setViewportSize({width,height:1000});
  await page.keyboard.press('Escape');
  assert(await page.locator('[data-vf-brand-preview-open]').evaluate(n=>n===document.activeElement));
  const original=await page.locator(input('siteName')).inputValue();
  await page.locator(input('siteName')).fill('仅候选值');
  assert.equal(await page.locator('[data-vf-preview-name]').textContent(),'仅候选值');
  await page.locator('[data-vf-brand-discard]').click();assert.equal(await page.locator(input('siteName')).inputValue(),original);
  const save=async name=>{
   await page.locator(input('siteName')).fill(name);
   const invalid=await page.locator('[data-vf-brand-form]').evaluate(n=>[...n.querySelectorAll(':invalid')].map(el=>el.name));
   assert.deepEqual(invalid,[],'test dataset must satisfy existing required fields');
   const response=page.waitForResponse(r=>r.url().includes('admin-ajax.php')&&r.request().postData()?.includes('vf_theme_brand_save'));
   await page.locator('[data-vf-brand-save]').click();
   const payload=await (await response).json();assert(payload.success,JSON.stringify(payload));
   await page.waitForFunction(()=>document.querySelector('[data-vf-brand-page]').dataset.vfBrandDirty==='0');
   assert.equal(await page.locator('[data-vf-brand-revision]').inputValue(),payload.data.revision);
   assert.equal(await page.locator('[data-vf-brand-revision-visible]').textContent(),payload.data.revision.slice(0,10));
   return payload;
  };
  const persisted='验证品牌 '+width+' & "清晰"';await save(persisted);await page.reload();
  assert.equal(await page.locator(input('siteName')).inputValue(),persisted,'actual DB reload lost save');
  assert(!await page.locator('[data-vf-brand-save]').isVisible());
  const security=await page.evaluate(()=>{
   const form=document.querySelector('[data-vf-brand-form]'),fields=Object.fromEntries(new FormData(form));
   return {fields,config:VFThemeBrand};
  });
  const bad=await context.request.post(security.config.ajaxUrl,{form:{...security.fields,action:security.config.saveAction||'vf_theme_brand_save',nonce:'invalid-test-nonce','brand[siteName]':'MUST-NOT-WRITE'}});
  const badPayload=await bad.json();assert.notEqual(badPayload.success,true,'invalid nonce saved');
  const guest=await browser.newContext();const denied=await guest.request.post(security.config.ajaxUrl,{form:{...security.fields,action:security.config.saveAction||'vf_theme_brand_save',nonce:security.config.nonce,'brand[siteName]':'MUST-NOT-WRITE'}});
  assert((await denied.text()).trim()==='0'||denied.status()>=400,'logged-out mutation accepted');await guest.close();
  await page.reload();assert.equal(await page.locator(input('siteName')).inputValue(),persisted);
  // Real revision conflict: a second authenticated page saves while this page retains its revision.
  const other=await context.newPage();await other.goto(url);
  await other.locator(input('siteName')).fill('并发已保存 '+width);
  const otherReply=other.waitForResponse(r=>r.url().includes('admin-ajax.php')&&r.request().postData()?.includes('vf_theme_brand_save'));
  await other.locator('[data-vf-brand-save]').click();assert((await (await otherReply).json()).success);
  await page.locator(input('siteName')).fill('冲突后输入保留');
  const conflict=page.waitForResponse(r=>r.url().includes('admin-ajax.php')&&r.request().postData()?.includes('vf_theme_brand_save'));
  await page.locator('[data-vf-brand-save]').click();const conflictPayload=await (await conflict).json();
  assert(!conflictPayload.success&&conflictPayload.data.failureCode==='REVISION_CONFLICT',JSON.stringify(conflictPayload));
  assert.equal(await page.locator(input('siteName')).inputValue(),'冲突后输入保留');
  await page.waitForFunction(()=>!document.querySelector('[data-vf-brand-save]').disabled);
  assert(await page.locator('[data-vf-brand-save]').isEnabled());await other.close();
  await page.reload();await save(original);await page.reload();assert.equal(await page.locator(input('siteName')).inputValue(),original);
  await page.locator('[data-vf-brand-preview-open]').click();assert(await page.locator('#vf-brand-step-preview').isVisible());
  await page.locator('#vf-brand-runtime-details>summary').focus();await page.keyboard.press('Enter');
  assert(await page.locator('#vf-brand-runtime-details').evaluate(n=>n.open));
  await page.evaluate(()=>document.querySelectorAll('[data-vf-native-body-v8] details').forEach(n=>n.open=true));
  assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),'expanded actual WP overflow');
  await page.keyboard.press('Escape');
  const numbers=await page.locator('.vf-brand-length').evaluateAll(groups=>groups.map(el=>{const r=el.getBoundingClientRect(),n=el.querySelector('input[type="number"]'),u=el.querySelector('span'),s=getComputedStyle(el),ns=getComputedStyle(n),ur=u.getBoundingClientRect();return {key:n.dataset.vfLengthNumber,width:r.width,height:r.height,edge:innerWidth<=782?r.left:r.right,border:s.borderWidth,inputBorder:ns.borderWidth,inputRadius:ns.borderRadius,unitWidth:ur.width,unitHeight:ur.height};}));
  assert.equal(numbers.length,6);assert(numbers.every(n=>n.width===140&&n.height===40&&n.border==='1px'&&n.inputBorder==='0px'&&n.inputRadius==='0px'&&n.unitWidth===38&&n.unitHeight===38),JSON.stringify({width,numbers}));
  assert(Math.max(...numbers.map(n=>n.edge))-Math.min(...numbers.map(n=>n.edge))<=1,'numeric control edges differ');
  const number=page.locator('[data-vf-length-number="baseFontSize"]'),before=await number.inputValue();await number.focus();
  assert.deepEqual(await number.evaluate(el=>{const s=getComputedStyle(el.parentElement);return [s.outlineWidth,s.outlineStyle];}),['2px','solid']);
  await page.keyboard.press('ArrowUp');assert.equal(Number(await number.inputValue()),Number(before)+1);assert.equal(await page.locator(input('baseFontSize')).inputValue(),`${Number(before)+1}px`);
  await number.fill(before);assert.equal(await page.locator(input('baseFontSize')).inputValue(),`${before}px`);
  await number.locator('..').screenshot({path:'proof/live-number-focus-'+width+'.png'});
  await page.locator('.vf-v9-brand-layout').screenshot({path:'proof/live-numbers-'+width+'.png'});
  const advanced=await page.locator('.vf-brand-inheritance').evaluate(root=>{
   const rect=root.getBoundingClientRect();
   return {controls:[...root.querySelectorAll('input:not([type="hidden"]):not([type="checkbox"]),select')].map(n=>{const r=n.getBoundingClientRect(),s=getComputedStyle(n);return {name:n.name,setting:!n.closest('.vf-brand-inheritance__restore'),height:r.height,right:r.right,font:s.fontSize,weight:s.fontWeight,radius:s.borderRadius,disabled:n.disabled,readOnly:!!n.readOnly};}),surfaces:[root.querySelector('.vf-brand-inheritance__head'),...root.querySelectorAll('.vf-brand-inheritance__grid>article,.vf-brand-source-chain>div')].map(n=>{const r=n.getBoundingClientRect(),s=getComputedStyle(n);return {inset:r.left-rect.left,background:s.backgroundColor,shadow:s.boxShadow};}),buttons:[...root.querySelectorAll('.button')].map(n=>n.getBoundingClientRect().height)};
  });
  assert(advanced.controls.length>=9&&advanced.controls.every(n=>n.height===(width<=782?44:40)&&n.font==='15px'&&n.weight==='400'&&n.radius==='5px'&&!n.disabled&&!n.readOnly),JSON.stringify({width,advanced}));
  assert(advanced.surfaces.every(n=>Math.abs(n.inset)<=1&&n.background==='rgba(0, 0, 0, 0)'&&n.shadow==='none'),JSON.stringify({width,advanced}));
  assert(advanced.buttons.every(n=>n===(width<=782?44:40)),JSON.stringify({width,advanced}));
  assert(Math.max(...advanced.controls.filter(n=>n.setting).map(n=>n.right))-Math.min(...advanced.controls.filter(n=>n.setting).map(n=>n.right))<=1);
  const choice=page.locator('.vf-brand-inheritance__check input[type="checkbox"]');
  const originalChoice=await choice.isChecked();
  const geometry=async()=>{const m=await choice.evaluate(el=>{const r=el.getBoundingClientRect(),lr=el.closest('label').getBoundingClientRect(),t=el.closest('label').querySelector('span').getBoundingClientRect(),s=getComputedStyle(el);return {width:r.width,height:r.height,padding:s.padding,radius:s.borderRadius,labelHeight:lr.height,centerDelta:r.top+r.height/2-t.top-t.height/2};});assert(m.width===18&&m.height===18&&m.padding==='0px'&&m.radius==='3px'&&m.labelHeight>=44&&Math.abs(m.centerDelta)<=1,JSON.stringify({width,m}));return m;};
  const choiceMetric=await geometry();
  await choice.locator('..').locator('span').click();assert.equal(await choice.isChecked(),!originalChoice);await geometry();
  await choice.focus();await page.keyboard.press('Space');assert.equal(await choice.isChecked(),originalChoice);await geometry();
  await choice.evaluate(el=>el.disabled=true);await geometry();await choice.evaluate(el=>el.disabled=false);
  const recovery=await page.locator('.vf-brand-inheritance__restore :is(select,button)').evaluateAll(nodes=>nodes.map(el=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el);return {tag:el.tagName,height:r.height,whiteSpace:s.whiteSpace};}));
  assert.equal(recovery.length,3);assert(recovery.every(n=>n.height>=(width<=782?44:40)&&n.height<=(width<=782?46:42)),JSON.stringify({width,recovery}));assert(recovery.filter(n=>n.tag==='BUTTON').every(n=>n.whiteSpace==='nowrap'));
  await choice.locator('..').screenshot({path:'proof/live-choice-'+width+'.png'});
  await page.locator('.vf-brand-inheritance__restore').screenshot({path:'proof/live-recovery-'+width+'.png'});
  await page.screenshot({path:'proof/live-expanded-'+width+'.png',fullPage:true});

  await page.keyboard.press('Escape');
  const temp=page.locator('.vf-brand-inheritance__form--tokens');
  const dates={startsAt:new Date(Date.now()-3600000).toISOString().slice(0,16),expiresAt:new Date(Date.now()+7*86400000).toISOString().slice(0,16)};
  const values={label:'Synthetic editable form '+width,...dates,'temporaryTokens[brand]':'#2563eb','temporaryTokens[accent]':'#0891b2','temporaryTokens[cardRadius]':'14px'};
  for(const [name,value] of Object.entries(values)){await temp.locator(`[name="${name}"]`).fill(value);assert.equal(await temp.locator(`[name="${name}"]`).inputValue(),value);}
  await temp.locator('[name="enabled"]').uncheck();
  await Promise.all([page.waitForURL(u=>u.searchParams.get('vf_theme_notice')==='temporary-visual-saved'),temp.locator('button[type="submit"]').click()]);
  await page.locator('#vf-brand-inheritance').evaluate(n=>n.open=true);
  for(const [name,value] of Object.entries(values))assert.equal(await page.locator('.vf-brand-inheritance__form--tokens').locator(`[name="${name}"]`).inputValue(),value,'actual temporary form readback '+name);
  assert(!await page.locator('.vf-brand-inheritance__check input').isChecked());
  assert.equal(await page.locator(input('siteName')).inputValue(),original,'temporary save changed canonical brand');
  const preset=page.locator('.vf-brand-inheritance__form').filter({has:page.locator('[name="action"][value="vf_theme_site_preset_preflight"]')});
  await preset.locator('[name="preset"]').selectOption({index:0});await preset.locator('[name="mode"]').selectOption('identity_only');
  await Promise.all([page.waitForURL(u=>u.searchParams.get('vf_theme_notice')==='preset-diff-ready'),preset.locator('button[type="submit"]').click()]);
  await page.locator('#vf-brand-inheritance').evaluate(n=>n.open=true);
  assert(await page.locator('.vf-brand-preset-diff').isVisible(),'preset preflight did not render diff');
  const confirm=page.locator('.vf-brand-preset-confirm [name="confirm"]');await confirm.fill('SAFE-PREVIEW-ONLY');assert.equal(await confirm.inputValue(),'SAFE-PREVIEW-ONLY');await confirm.fill('');
  assert.equal(await page.locator(input('siteName')).inputValue(),original,'read-only preset diff mutated brand');
  await page.locator('.vf-brand-inheritance').screenshot({path:'proof/live-advanced-'+width+'.png'});
  const restore=page.locator('.vf-brand-inheritance__restore form').filter({has:page.locator('[name="action"][value="vf_theme_restore_inherited_token"]')});
  await restore.locator('[name="tokenKey"]').selectOption('brand');
  await Promise.all([page.waitForURL(u=>u.searchParams.get('vf_theme_notice')==='inherited-value-restored'),restore.locator('button').click()]);
  await page.locator('#vf-brand-inheritance').evaluate(n=>n.open=true);
  assert.equal(await page.locator('.vf-brand-inheritance__restore select option[value="brand"]').count(),0,'restore retained temporary token');
  const disable=page.locator('.vf-brand-inheritance__restore form').filter({has:page.locator('[name="action"][value="vf_theme_temporary_visual_disable"]')});
  await Promise.all([page.waitForURL(u=>u.searchParams.get('vf_theme_notice')==='temporary-visual-disabled'),disable.locator('button').click()]);
  assert.equal(await page.locator(input('siteName')).inputValue(),original);
  checks.push({width,...state,preview,preview_controls:'PASS',preview_scroll:'PASS',advanced,advanced_controls:'PASS',advanced_interactions:'PASS',numbers,number_controls:'PASS',choice:choiceMetric,choice_controls:'PASS',recovery_controls:'PASS',save_reload:'PASS',discard:'PASS',bad_nonce:'PASS',logged_out_write:'PASS',revision_conflict:'PASS',preview_link:'PASS',keyboard_disclosure:'PASS',frozen_header_parity:'PASS'});
 }
 const regressions=[];
 for(const tab of ['overview','layout','render','navigation','seo','preview','recovery']){
  await page.goto(origin+'/wp-admin/themes.php?page=vf-theme-modules&tab='+tab);
  assert(await page.locator('[data-vf-admin-tab="'+tab+'"]').count(),tab+' route missing');
  assert(!/Fatal error|critical error|Parse error/i.test(await page.locator('body').innerText()),tab+' fatal');regressions.push(tab);
 }
 assert.deepEqual(errors,[],'actual WordPress JS error');
 fs.writeFileSync('proof/live-browser.json',JSON.stringify({pass:true,environment:'isolated actual WordPress 7.1.2 PHP 8.3',checks,layout_cases:layout.cases.length,regressions,errors,owner_product_pass:false},null,2));
 await browser.close();console.log('REAL_WORDPRESS_BRAND_BROWSER=PASS');
})().catch(e=>{console.error(e);process.exit(1)});

