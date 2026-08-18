import { chromium } from 'playwright';

const base = 'http://127.0.0.1:18159';
const password = process.env.AUDIT_PASSWORD;
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [];
page.on('pageerror', e => errors.push('pageerror:' + String(e)));
page.on('console', m => { if (m.type() === 'error' && !/409 \(Conflict\)/.test(m.text())) errors.push('console:' + m.text()); });
const box = async s => { const l = page.locator(s).first(); return await l.isVisible() ? await l.boundingBox() : null; };
const overlap = (a,b) => !!(a && b && Math.max(0,Math.min(a.x+a.width,b.x+b.width)-Math.max(a.x,b.x))*Math.max(0,Math.min(a.y+a.height,b.y+b.height)-Math.max(a.y,b.y))>0);

await page.goto(base + '/', { waitUntil: 'networkidle' });
let sess = await page.evaluate(async () => await (await fetch('/api.php?action=session',{cache:'no-store'})).json());
if (!sess.site.auth) {
  await page.locator('[data-open-login]').click();
  await page.locator('#loginForm input[name="password"]').fill(password);
  await page.locator('#loginSubmit').click();
  await page.waitForFunction(async () => Boolean((await (await fetch('/api.php?action=session',{cache:'no-store'})).json()).site.auth);
  sess = await page.evaluate(async () => await (await fetch('/api.php?action=session',{cache:'no-store'})).json());
}
if (await page.evaluate(() => state.contentView) !== 'notebook') throw new Error('fresh default workspace is not notebook');
const csrf = sess.csrf;
const post = async (action, body) => page.evaluate(async ({action,body,csrf}) => await (await fetch('/api.php?action='+action,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify(body)})).json(), {action,body,csrf});

const cat = await post('category_save',{name:'V250 Final Audit',description:'',icon:'folder'});
if (!cat.ok) throw new Error('category seed failed ' + JSON.stringify(cat));
const cid = Number(cat.id);
const item = await post('content_save',{category_id:cid,title:'V2.5.0 UAUI Final',description:'摘要只在用户主动选择摘要模式时显示。',content:'# V2.5.0 UAUI Final\n\n正文阅读验证。\n\n## 第二节\n\n'+('舒适阅读需要合适字号、行距、字重和内容宽度。 '.repeat(120)),content_mode:'article',content_format:'markdown',primary_action:'read',status:'active'});
if (!item.ok) throw new Error('item seed failed ' + JSON.stringify(item));
const iid = Number(item.id);
const favAction = await post('content_favorite',{id:iid,favorite:true});
if (!favAction.ok) throw new Error('favorite action failed ' + JSON.stringify(favAction));

await page.reload({waitUntil:'networkidle'});
await page.evaluate(async cid0 => { await setContentView('list'); await selectCategory(cid0); }, cid);
await page.waitForFunction(iid0 => state.items.some(x => Number(x.id) === Number(iid0)), iid, {timeout:10000});
await page.locator('[data-item-row="'+iid+'"]').waitFor({state:'visible'});
await page.waitForFunction(() => document.body.dataset.v250ListMode === 'minimal');
const listMode = page.locator('select[data-v250-list-mode]').first();
await listMode.waitFor({state:'visible'});
if (await page.locator('[data-item-row="'+iid+'"] .content-meta').isVisible()) throw new Error('minimal mode meta visible');
await listMode.selectOption('standard');
await page.waitForFunction(() => document.body.dataset.v250ListMode === 'standard');
await listMode.selectOption('summary');
await page.waitForFunction(() => document.body.dataset.v250ListMode === 'summary');
await page.locator('[data-item-row="'+iid+'"] .v250-item-summary:not([hidden])').waitFor({state:'visible'});
await listMode.selectOption('minimal');
await page.waitForFunction(() => document.body.dataset.v250ListMode === 'minimal');

await page.evaluate(async ({cid0,iid0}) => { await setContentView('notebook'); await selectCategory(cid0); await openReader(iid0,true); }, {cid0:cid,iid0:iid});
await page.waitForFunction(iid0 => Number(state.readerItem?.id) === Number(iid0), iid, {timeout:10000});
await page.locator('.markdown-body').first().waitFor({state:'visible'});
const typography = await page.evaluate(() => {
  const r=document.querySelector('.markdown-body');
  return {body:parseFloat(getComputedStyle(document.body).fontSize),reader:parseFloat(getComputedStyle(r).fontSize),line:parseFloat(getComputedStyle(r).lineHeight),mode:document.body.dataset.v250ListMode};
});
if (typography.body < 14.5 || typography.reader < 16.8 || typography.line < 29 || typography.mode !== 'minimal') throw new Error('typography ' + JSON.stringify(typography));

const resizer=page.locator('#notebookResizer');
const hb=await resizer.boundingBox();
if(!hb) throw new Error('resizer missing');
const w0=await page.evaluate(()=>state.notebookPaneWidth);
await page.mouse.move(hb.x+3,hb.y+100); await page.mouse.down(); await page.mouse.move(hb.x+73,hb.y+100,{steps:4}); await page.mouse.up();
const resize=await page.evaluate(()=>({w:state.notebookPaneWidth,s:Number(localStorage.getItem('vftb-notebook-pane-width'))}));
if(resize.w<w0+40 || Math.abs(resize.w-resize.s)>2) throw new Error('resize '+JSON.stringify({w0,resize}));

const visibleControls=()=>page.locator('#sidebarRailToggle:visible,#notebookPaneCollapse:visible,#notebookPaneRestore:visible').count();
if(await visibleControls()!==2 || await page.locator('#menuBtn:visible').count()) throw new Error('duplicate pane controls');
const before=await box('#notebookDetailScroll');
await page.locator('#notebookPaneCollapse').click();
await page.waitForFunction(()=>state.notebookListCollapsed===true); await page.waitForTimeout(80);
const afterList=await box('#notebookDetailScroll');
if(!before||!afterList||afterList.width<=before.width+150||await visibleControls()!==2||overlap(await box('#sidebarRailToggle'),await box('#notebookPaneRestore'))) throw new Error('list collapse');
await page.locator('#sidebarRailToggle').click();
await page.waitForFunction(()=>state.sidebarCollapsed===true); await page.waitForTimeout(80);
const afterBoth=await box('#notebookDetailScroll');
if(!afterBoth||afterBoth.width<=afterList.width+100||await visibleControls()!==2||overlap(await box('#sidebarRailToggle'),await box('#notebookPaneRestore'))) throw new Error('both collapse');
await page.locator('#notebookPaneRestore').click(); await page.locator('#sidebarRailToggle').click();
await page.waitForFunction(()=>!state.notebookListCollapsed&&!state.sidebarCollapsed);

const fav=await page.evaluate(async iid0=>Number((await(await fetch('/api.php?action=content_get&id='+iid0,{cache:'no-store'})).json()).item?.is_favorite||0),iid);
if(fav!==1) throw new Error('favorite parity '+fav);

await page.evaluate(async()=>await state.workspaceController.setMode('edit',true));
await page.locator('#articleSource').waitFor({state:'visible'});
await page.locator('.vf-editor-toolbar').first().waitFor({state:'visible'});
const editorSize=await page.locator('#articleSource').evaluate(el=>parseFloat(getComputedStyle(el).fontSize));
if(editorSize<15.5) throw new Error('editor font '+editorSize);
await page.evaluate(async()=>await state.workspaceController.setMode('read',true));

await page.locator('#themeBtn').click();
await page.waitForFunction(()=>document.documentElement.getAttribute('data-theme')==='dark');
const dark=await page.evaluate(()=>({body:getComputedStyle(document.body).backgroundColor,side:getComputedStyle(document.querySelector('.sidebar')).backgroundColor}));
if(/rgb\(247, 247, 247\)|rgb\(255, 255, 255\)/.test(dark.body+' '+dark.side)) throw new Error('dark theme '+JSON.stringify(dark));
await page.locator('#themeBtn').click();

for(const [w,h] of [[1920,1080],[1440,900],[1024,820],[768,900],[390,844]]){
  await page.setViewportSize({width:w,height:h}); await page.waitForTimeout(80);
  const dims=await page.evaluate(()=>({client:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth}));
  if(dims.scroll>dims.client+3) throw new Error('horizontal overflow '+w+' '+JSON.stringify(dims));
}

await page.setViewportSize({width:1440,height:900});
await page.locator('#accountBtn').click();
const confirm=page.locator('[data-dialog-confirm]'); if(await confirm.count()) await confirm.click();
await page.waitForFunction(async()=>!(await(await fetch('/api.php?action=session',{cache:'no-store'})).json()).site.auth);
await page.locator('[data-open-login]').waitFor({state:'visible'});
await page.locator('[data-open-login]').click();
await page.locator('#loginForm input[name="password"]').fill(password);
await page.locator('#loginSubmit').click();
await page.waitForFunction(async()=>Boolean((await(await fetch('/api.php?action=session',{cache:'no-store'})).json()).site.auth);

if(errors.length) throw new Error(errors.join(' | '));
console.log('P02_V250_UAUI_FINAL_PASS='+JSON.stringify({typography,resize,before,afterList,afterBoth,dark,editorSize,errors}));
await browser.close();
