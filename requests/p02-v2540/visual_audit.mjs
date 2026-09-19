import { chromium } from 'playwright';
import fs from 'node:fs';

const base=process.env.VF_UX_E2E_BASE_URL;
const password=process.env.VF_UX_E2E_PASSWORD;
const out=process.env.VF_VISUAL_OUTPUT;
if(!base||!password||!out) throw new Error('missing visual audit environment');
fs.mkdirSync(out,{recursive:true});

const browser=await chromium.launch({headless:true});
const context=await browser.newContext({viewport:{width:1440,height:900}});
const page=await context.newPage();

async function login(){
  await page.goto(base+'/',{waitUntil:'networkidle'});
  const unlock=page.locator('[data-open-login]').first();
  if(await unlock.count()){
    await page.waitForFunction(()=>typeof openLogin==='function');
    await page.evaluate(()=>openLogin());
    await page.locator('#loginForm input[name="password"]').fill(password);
    await page.locator('#loginSubmit').click();
    await page.waitForFunction(async()=>{const j=await (await fetch('/api.php?action=session',{cache:'no-store'})).json();return Boolean(j?.ok&&j?.site?.auth);});
  }
  await page.waitForFunction(()=>document.body.classList.contains('v2537-desktop-shell'));
}

try{
  await login();
  await page.screenshot({path:out+'/01-list-1440.png',fullPage:true});
  const listMenu=page.locator('#listWorkbenchMenuTrigger');
  if(await listMenu.count()){
    await listMenu.click();
    await page.waitForSelector('.workbench-menu-context');
    await page.screenshot({path:out+'/02-list-menu-1440.png',fullPage:true});
    await page.keyboard.press('Escape');
  }
  await page.evaluate(()=>setContentView('notebook'));
  await page.waitForSelector('.notebook-list-pane');
  const first=page.locator('.notebook-title-row').first();
  if(await first.count())await first.click();
  await page.waitForSelector('.article-workspacebar');
  await page.screenshot({path:out+'/03-reader-1440.png',fullPage:true});
  const edit=page.locator('[data-workspace-command="edit"]');
  if(await edit.count()){
    await edit.click();
    await page.waitForSelector('.article-workspace.mode-edit');
    await page.screenshot({path:out+'/04-editor-1440.png',fullPage:true});
  }
  const read=page.locator('[data-workspace-command="read"]');
  if(await read.count())await read.click();
  await page.locator('#settingsBtn').click();
  await page.waitForSelector('.settings-page');
  await page.screenshot({path:out+'/05-settings-1440.png',fullPage:true});
  await page.locator('#settingsBack').click();
  await page.setViewportSize({width:1024,height:768});
  await page.waitForTimeout(150);
  await page.screenshot({path:out+'/06-medium-1024.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.waitForFunction(()=>!document.body.classList.contains('v2537-desktop-shell'));
  await page.waitForTimeout(150);
  await page.screenshot({path:out+'/07-mobile-390.png',fullPage:true});
  console.log('P02_V2540_VISUAL_AUDIT_CAPTURE=PASS');
} finally {
  await browser.close();
}
