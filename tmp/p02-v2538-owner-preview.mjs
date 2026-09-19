import { chromium } from 'playwright';
import fs from 'node:fs';
const base=process.env.PREVIEW_BASE;
const password=process.env.PREVIEW_PASSWORD;
const out=process.env.PREVIEW_OUT;
if(!base||!password||!out)throw new Error('missing preview env');
fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({headless:true});
const context=await browser.newContext({viewport:{width:1440,height:900}});
const page=await context.newPage();
await page.goto(base+'/',{waitUntil:'networkidle'});
const unlock=page.locator('[data-open-login]').first();
if(await unlock.count()){
  await page.waitForFunction(()=>typeof openLogin==='function');
  await page.evaluate(()=>openLogin());
  await page.waitForSelector('#loginForm input[name="password"]');
  await page.locator('#loginForm input[name="password"]').fill(password);
  await page.locator('#loginSubmit').click();
  await page.waitForFunction(async()=>{const j=await (await fetch('/api.php?action=session',{cache:'no-store'})).json();return Boolean(j?.ok&&j?.site?.auth);});
}
const fixture=await page.evaluate(async()=>{
  const s=await (await fetch('/api.php?action=session',{cache:'no-store'})).json();
  const post=async(action,body)=>{const r=await fetch('/api.php?action='+action,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':s.csrf},body:JSON.stringify(body)});const j=await r.json();if(!j.ok)throw new Error(action+': '+JSON.stringify(j));return j;};
  const cat=await post('category_save',{name:'产品设计',description:'Owner preview fixture',icon:'folder'});
  const notes=[
    ['Inkstone UX 对齐计划','# Inkstone UX 对齐计划\n\n这是用于 OWNER Preview 的示例资料。\n\n## 核心原则\n- 低噪音\n- 高密度\n- 内容优先\n\n## 下一步\n继续压缩低频操作，并保持阅读舒适度。'],
    ['P02 发布检查清单','# P02 发布检查清单\n\n- Source Identity\n- Browser Gate\n- Update Continuity\n- Owner Real Use\n- Release Readback'],
    ['长期资料库整理方法','# 长期资料库整理方法\n\n将临时资料逐步整理为长期资料，保持分类简单、检索直接。']
  ];
  const ids=[];
  for(const [title,content] of notes){
    const saved=await post('content_save',{category_id:cat.id,title,content,content_mode:'article',content_format:'markdown',primary_action:'read',status:'active'});
    ids.push(saved.id);
  }
  return {categoryId:cat.id,ids};
});
await page.evaluate(async categoryId=>{if(state.contentView!=='list')await setContentView('list');await selectCategory(categoryId);},fixture.categoryId);
await page.waitForFunction(()=>state.loading===false&&document.querySelectorAll('.content-row').length>=3);
await page.screenshot({path:out+'/01-library-list.png',fullPage:true});
await page.evaluate(()=>setContentView('notebook'));
await page.waitForSelector('.notebook-list-pane');
await page.locator('.notebook-title-row').first().click();
await page.waitForSelector('.article-workspacebar');
await page.screenshot({path:out+'/02-notebook-reader.png',fullPage:true});
await page.locator('[data-workspace-mode="edit"]').click();
await page.waitForTimeout(250);
await page.screenshot({path:out+'/03-editor.png',fullPage:true});
await page.locator('#settingsBtn').click();
await page.waitForSelector('.settings-page');
await page.screenshot({path:out+'/04-settings.png',fullPage:true});
await browser.close();
console.log('P02_V2538_OWNER_PREVIEW_SCREENSHOTS=PASS');