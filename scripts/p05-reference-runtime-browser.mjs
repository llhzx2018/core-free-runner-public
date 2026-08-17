import puppeteer from 'puppeteer-core';
import assert from 'node:assert/strict';

const base=process.env.P05_BASE_URL??'http://127.0.0.1:3105';
const password=process.env.P05_TEST_ADMIN_PASSWORD??'P05-Browser-Gate-2026!';
const chrome=process.env.CHROME_BIN;
if(!chrome) throw new Error('CHROME_BIN_MISSING');

const browser=await puppeteer.launch({
  executablePath:chrome,
  headless:true,
  args:['--no-sandbox','--disable-dev-shm-usage'],
});
const page=await browser.newPage();
const consoleErrors=[];
const pageErrors=[];
const apiFailures=[];
page.on('console',msg=>{ if(msg.type()==='error') consoleErrors.push(msg.text()); });
page.on('pageerror',err=>pageErrors.push(String(err)));
page.on('response',res=>{
  const u=res.url();
  if(u.includes('/api/') && res.status()>=400) apiFailures.push(`${res.status()} ${u}`);
});

const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function textIncludes(value){return await page.evaluate(v=>document.body.innerText.includes(v),value);}
async function clickText(selector,text){
  const ok=await page.evaluate(({selector,text})=>{
    const el=[...document.querySelectorAll(selector)].find(x=>(x.textContent??'').trim()===text);
    if(!el)return false;
    el.click();
    return true;
  },{selector,text});
  assert.equal(ok,true,`missing clickable ${text}`);
  await sleep(600);
}
async function assertNoOverflow(label){
  const m=await page.evaluate(()=>({
    innerWidth:window.innerWidth,
    scrollWidth:document.documentElement.scrollWidth,
    bodyWidth:document.body.scrollWidth,
  }));
  assert.ok(m.scrollWidth<=m.innerWidth+2,`${label} document overflow ${JSON.stringify(m)}`);
  assert.ok(m.bodyWidth<=m.innerWidth+2,`${label} body overflow ${JSON.stringify(m)}`);
}

await page.setViewport({width:1440,height:1000,deviceScaleFactor:1});
await page.goto(base,{waitUntil:'networkidle2'});
const usernameValue=await page.$eval('input[autocomplete="username"]',el=>el.value);
assert.equal(usernameValue,'admin','default admin username changed unexpectedly');
await page.type('input[autocomplete="current-password"]',password);
await page.click('button.primary');
await page.waitForSelector('.workspace-shell',{timeout:10000});
await sleep(800);

// The unauthenticated App boot intentionally probes /api/auth/me and receives 401.
// Start the strict browser error gate only after authenticated workspace entry.
consoleErrors.length=0;
pageErrors.length=0;
apiFailures.length=0;

assert.ok(await textIncludes('Kewaro Owner Review'));
for(const label of ['概览','网站检查','关键词','页面','AI / AEO','变更记录','设置','全局搜索','备份与恢复','系统状态']){
  assert.ok(await textIncludes(label),`missing ${label}`);
}
const primaryLabels=await page.$$eval('.site-nav button',els=>els.map(x=>(x.textContent??'').trim()));
assert.deepEqual(primaryLabels,['概览','网站检查','关键词','页面','AI / AEO','变更记录','设置']);
assert.ok(!primaryLabels.includes('Opportunities'));
assert.ok(!primaryLabels.includes('Operations'));
for(const label of ['SEO 健康度','搜索流量趋势','关键词趋势','AI 可见度','Top Keywords','Errors','Warnings','Last Audit','NEEDS ATTENTION']){
  assert.ok(await textIncludes(label),`overview missing ${label}`);
}
await assertNoOverflow('desktop-overview');

await clickText('.site-nav button','网站检查');
for(const label of ['Health','Priority','Issue','Affected Pages','Fix','Verify']){
  assert.ok(await textIncludes(label),`audit missing ${label}`);
}
await page.waitForSelector('.issue-row',{timeout:10000});
await page.click('.issue-row');
await sleep(500);
for(const q of ['1. 发生什么？','2. 为什么重要？','3. 影响什么？','4. 怎么处理？','5. 处理后如何确认？']){
  assert.ok(await textIncludes(q),`issue detail missing ${q}`);
}
await assertNoOverflow('desktop-issue-detail');

await clickText('.site-nav button','关键词');
for(const label of ['Movement','Landing Page','Evidence','Owner Action']){
  assert.ok(await textIncludes(label),`keywords missing ${label}`);
}
await page.waitForSelector('.keyword-row',{timeout:10000});
assert.ok((await page.$$('.keyword-row')).length>0,'keyword rows absent');
await assertNoOverflow('desktop-keywords');

await clickText('.site-nav button','AI / AEO');
for(const label of ['Engine','Prompt','Mention / Citation','Source','Change','Owner Action','未接入']){
  assert.ok(await textIncludes(label),`AI missing ${label}`);
}
const aiValue=await page.$eval('.metrics-grid .metric-card:first-child strong',el=>(el.textContent??'').trim());
assert.equal(aiValue,'未接入');
await assertNoOverflow('desktop-ai');

await clickText('.site-nav button','页面');
await page.waitForSelector('.page-row',{timeout:10000});
await assertNoOverflow('desktop-pages');

await page.setViewport({width:390,height:844,deviceScaleFactor:1});
await page.goto(base,{waitUntil:'networkidle2'});
await page.waitForSelector('.workspace-shell',{timeout:10000});
await sleep(500);
const selectorVisible=await page.$eval('.site-context select',el=>{
  const r=el.getBoundingClientRect();
  return r.width>0&&r.height>0;
});
assert.equal(selectorVisible,true,'mobile site switch missing');
await assertNoOverflow('mobile-overview');

await clickText('.site-nav button','网站检查');
await page.waitForSelector('.issue-row',{timeout:10000});
await assertNoOverflow('mobile-audit');
const issueRight=await page.$eval('.issue-row',el=>el.getBoundingClientRect().right-window.innerWidth);
assert.ok(issueRight<=2,`mobile issue row clipped ${issueRight}`);

await clickText('.site-nav button','关键词');
await page.waitForSelector('.keyword-row',{timeout:10000});
await assertNoOverflow('mobile-keywords');
const keywordRight=await page.$eval('.keyword-row',el=>el.getBoundingClientRect().right-window.innerWidth);
assert.ok(keywordRight<=2,`mobile keyword row clipped ${keywordRight}`);

await clickText('.site-nav button','AI / AEO');
assert.ok(await textIncludes('未接入'));
await assertNoOverflow('mobile-ai');

await clickText('.site-nav button','页面');
await page.waitForSelector('.page-row',{timeout:10000});
await assertNoOverflow('mobile-pages');

assert.deepEqual(pageErrors,[],`PAGE_ERRORS ${JSON.stringify(pageErrors)}`);
assert.deepEqual(apiFailures,[],`API_FAILURES ${JSON.stringify(apiFailures)}`);
const criticalConsole=consoleErrors.filter(x=>!x.includes('favicon'));
assert.deepEqual(criticalConsole,[],`CONSOLE_ERRORS ${JSON.stringify(criticalConsole)}`);

console.log('DESKTOP_1440=PASS');
console.log('MOBILE_390=PASS');
console.log('SITE_CONTEXT=PASS');
console.log('PRIMARY_IA=PASS');
console.log('OPPORTUNITIES_PRIMARY_NAV=ABSENT');
console.log('OPERATIONS_PRIMARY_NAV=ABSENT');
console.log('DASHBOARD_HEALTH_CHANGE_ATTENTION_ACTION=PASS');
console.log('AUDIT_ACTION_LOOP=PASS');
console.log('ISSUE_DETAIL_FIVE_QUESTION=PASS');
console.log('KEYWORD_MOVEMENT_MODEL=PASS');
console.log('AI_AEO_EXPLAINABILITY=PASS');
console.log('AI_FAKE_SCORE=ABSENT');
console.log('MOBILE_HORIZONTAL_OVERFLOW=0');
console.log('BROWSER_CONSOLE_ERRORS=0');
console.log('API_FAILURES=0');
await browser.close();
