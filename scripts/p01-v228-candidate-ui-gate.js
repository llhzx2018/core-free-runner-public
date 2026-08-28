const { chromium } = require('playwright');
const fs = require('fs');

(async()=>{
  const ids=JSON.parse(fs.readFileSync('/tmp/p01-v228-final-ids.json','utf8'));
  const base='http://127.0.0.1:18340';
  const browser=await chromium.launch({headless:true});
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  const login=await context.request.post(base+'/api.php?action=login',{data:{password:'P01V228!Final'}});
  if(!login.ok())throw new Error('login http '+login.status());
  const loginBody=await login.json();if(!loginBody.ok)throw new Error('login rejected');
  const page=await context.newPage();
  const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  const noOverflow=async(label)=>{const x=await page.evaluate(()=>({doc:document.documentElement.scrollWidth,win:innerWidth}));if(x.doc>x.win+2)throw new Error(label+' document overflow '+JSON.stringify(x));};
  const closeDialog=async()=>{const b=page.getByRole('button',{name:'关闭'});if(await b.count())await b.first().click();await page.waitForTimeout(180);};

  await page.goto(base+'/surfaces.php?per=30&page=3',{waitUntil:'networkidle'});
  if(!((await page.locator('.vf-workspace-count').innerText()).includes('当前 61–90')))throw new Error('All range missing');
  if(await page.locator('.vf-pagination nav a').count()<4)throw new Error('All numbered pagination missing');
  await noOverflow('desktop all');
  await page.screenshot({path:'/tmp/p01-v228-final-ui/desktop-all.png',fullPage:true});

  await page.goto(base+'/start.php?category='+encodeURIComponent('开发工具')+'&per=30&page=2',{waitUntil:'networkidle'});
  if(!((await page.locator('.vf-workspace-count').innerText()).includes('当前 31–60')))throw new Error('Start range missing');
  await page.locator('[data-open-add]').click();await page.locator('[data-panel="add"]:not([hidden])').waitFor();
  if((await page.locator('[data-add-form] select[name="surface"]').inputValue())!=='start')throw new Error('Start add surface context missing');
  if((await page.locator('[data-add-form] select[name="category_id"]').inputValue())!==String(ids.start))throw new Error('Start add category context missing');
  await closeDialog();

  await page.goto(base+`/channels.php?category=${ids.chA}&per=30&page=2`,{waitUntil:'networkidle'});
  if(!((await page.locator('.vf-workspace-count').innerText()).includes('当前 31–60')))throw new Error('Channels range missing');
  if(await page.locator('.vf-pagination nav a').count()<3)throw new Error('Channels pagination missing');
  await page.locator('[data-open-add]').click();await page.locator('[data-panel="add"]:not([hidden])').waitFor();
  if((await page.locator('[data-add-form] select[name="surface"]').inputValue())!=='channels')throw new Error('Channels add surface context missing');
  if((await page.locator('[data-add-form] select[name="category_id"]').inputValue())!==String(ids.chA))throw new Error('Channels add category context missing');
  await page.locator('[data-add-form] input[name="url"]').fill('https://youtube.com/@final-batch');
  await page.locator('[data-add-form] input[name="title"]').fill('Final Batch Channel');
  await page.locator('[data-add-form] input[name="tags"]').fill('频道, 最终门');
  await page.locator('[data-add-continue]').click();await page.locator('.vf-workspace-toast.show').waitFor();
  if((await page.locator('[data-add-form] input[name="url"]').inputValue())!=='')throw new Error('Add continue did not clear url');
  if((await page.locator('[data-add-form] select[name="category_id"]').inputValue())!==String(ids.chA))throw new Error('Add continue lost category');
  if((await page.locator('[data-add-form] select[name="surface"]').inputValue())!=='channels')throw new Error('Add continue lost surface');
  await closeDialog();await page.waitForTimeout(600);

  await page.goto(base+`/channels.php?category=${ids.chA}&per=30&page=1`,{waitUntil:'networkidle'});
  const boxes=page.locator('[data-select-asset]');await boxes.nth(0).click();await boxes.nth(5).click({modifiers:['Shift']});
  const bulk=page.locator('[data-bulkbar]:not([hidden])');await bulk.waitFor();
  if(!((await bulk.innerText()).includes('6 / 30 项已选择')))throw new Error('Shift range selection failed');
  if(await page.locator('[data-asset-row].is-selected').count()!==6)throw new Error('Selected styling mismatch');
  await page.screenshot({path:'/tmp/p01-v228-final-ui/desktop-channels-bulk.png',fullPage:true});
  const favReq=page.waitForRequest(r=>r.url().includes('/workspace-action.php')&&r.method()==='POST');await bulk.locator('[data-bulk-action="favorite"]').click();await favReq;await page.locator('.vf-workspace-toast.show').waitFor();
  await page.waitForTimeout(120);if(!(await page.locator('[data-bulkbar]').isHidden()))throw new Error('Bulk favorite did not clear selection');
  for(let i=0;i<6;i++){if((await page.locator('[data-asset-row]').nth(i).locator('[data-favorite-id]').getAttribute('data-favorite'))!=='1')throw new Error('Favorite UI not synchronized')}

  const row=page.locator('[data-asset-row]').nth(8);const rid=await row.getAttribute('data-asset-row');await row.click();
  const detail=page.locator('[data-detail-form]');await detail.locator('textarea[name="description"]').fill('V2.28 final keyboard save');await detail.locator('textarea[name="description"]').focus();
  const saveReq=page.waitForRequest(r=>r.url().includes('/workspace-action.php')&&r.method()==='POST');await page.keyboard.press('Control+Enter');await saveReq;await page.waitForTimeout(800);
  await page.locator(`[data-asset-row="${rid}"]`).click();await page.locator('[data-panel="detail"]:not([hidden])').waitFor();
  if((await detail.locator('textarea[name="description"]').inputValue())!=='V2.28 final keyboard save')throw new Error('Detail keyboard save failed');
  await closeDialog();

  await page.goto(base+`/watch.php?category=${ids.wa}&per=30&page=1`,{waitUntil:'networkidle'});
  if(!((await page.locator('.vf-workspace-count').innerText()).includes('50 项')))throw new Error('Watch category count missing');
  if(await page.locator('.vf-pagination nav a').count()<2)throw new Error('Watch pagination missing');
  const firstWatch=await page.locator('.vf-watch-card').first().innerText();if(!/想看|在看|看过|珍藏/.test(firstWatch))throw new Error('Watch status not localized');
  await page.goto(base+'/watch.php?status=want',{waitUntil:'networkidle'});
  const want=page.getByRole('link',{name:/想看/}).first();if(!((await want.getAttribute('class'))||'').includes('active'))throw new Error('Want filter not active');
  await page.screenshot({path:'/tmp/p01-v228-final-ui/desktop-watch.png',fullPage:true});

  await page.setViewportSize({width:390,height:844});
  await page.goto(base+`/channels.php?category=${ids.chA}&per=30`,{waitUntil:'networkidle'});await page.locator('[data-select-asset]').first().click();await page.locator('[data-bulkbar]:not([hidden])').waitFor();
  const rect=await page.locator('[data-bulkbar]').evaluate(el=>{const r=el.getBoundingClientRect();return {left:r.left,right:r.right,win:innerWidth,scroll:el.scrollWidth,client:el.clientWidth}});
  if(rect.left<0||rect.right>rect.win+1||rect.scroll>rect.client+2)throw new Error('Mobile bulk overflow '+JSON.stringify(rect));
  await noOverflow('mobile channels');await page.screenshot({path:'/tmp/p01-v228-final-ui/mobile-bulk.png',fullPage:true});

  const anon=await browser.newContext({viewport:{width:390,height:844}});const publicPage=await anon.newPage();await publicPage.goto(base+'/',{waitUntil:'networkidle'});if(await publicPage.locator('.vf-app-sidebar').count())throw new Error('Anonymous public leaked private workspace shell');await anon.close();
  if(errors.length)throw new Error('page errors: '+errors.join(' | '));
  await browser.close();
  console.log('P01_V228_FINAL_UI=PASS');
})().catch(e=>{console.error(e);process.exit(1)});
