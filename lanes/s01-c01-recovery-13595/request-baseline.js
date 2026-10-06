'use strict';
const fs=require('fs'),assert=require('assert/strict'),{chromium}=require('playwright');
const check=require('../target/tests/recovery-request-browser-check');
(async()=>{
 const browser=await chromium.launch(),page=await browser.newPage();
 await page.goto('http://127.0.0.1:18880/wp-login.php');await page.locator('#user_login').fill('admin');await page.locator('#user_pass').fill('Synthetic-Only-Update-54!');await Promise.all([page.waitForURL(/wp-admin/),page.locator('#wp-submit').click()]);
 const result=await check(page,{baseline:true});assert.equal(result.status,'PASS');fs.writeFileSync('proof/previous-request-defects.json',JSON.stringify(result,null,2));await browser.close();
})().catch(error=>{console.error(error);process.exit(1)});
