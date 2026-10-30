const {chromium}=require('playwright');const fs=require('fs'),assert=require('assert/strict');
(async()=>{const browser=await chromium.launch({headless:true});const proof=[];try{
for(const lang of ['en','zh'])for(const width of [1024,1440]){
const page=await browser.newPage({viewport:{width,height:1000}});await page.addInitScript(()=>{Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async value=>{window.__copiedText=value}}})});let before=[];page.on('request',r=>{if(/\.m3u8(?:[?#]|$)/i.test(r.url()))before.push(r.url())});
await page.goto('http://127.0.0.1:18880'+(lang==='zh'?'/zh/embed/':'/embed/'),{waitUntil:'networkidle'});
const root=page.locator('[data-vf-embed-generator]').first();await root.waitFor();
assert.equal(await page.locator('h1').count(),1);assert.equal(before.length,0,'initial render must not load a stream');
assert.equal(await page.locator('.vf-tool-breadcrumb').isVisible(),false);assert.ok(await root.locator('[data-vf-embed-url]').isVisible());assert.ok(await root.locator('[data-vf-embed-generate]').isVisible());
const geometry=await page.evaluate(()=>({w:document.documentElement.clientWidth,sw:document.documentElement.scrollWidth}));assert.ok(geometry.sw<=geometry.w+1);
await root.locator('[data-vf-embed-url]').fill('https://example.invalid/stream.m3u8');await root.locator('[data-vf-embed-generate]').click();await root.locator('[data-vf-embed-recommended-code]').waitFor({state:'visible',timeout:10000});
const code=await root.locator('[data-vf-embed-recommended-code]').inputValue();assert.ok(code.includes('<iframe'),'actual iframe code');
const label=(await root.locator('[data-vf-embed-copy-recommended]').innerText()).trim();
fs.writeFileSync('proof/embed-primary-'+lang+'.json',JSON.stringify({label}));
assert.ok(lang==='zh'?label.includes('复制'):/copy/i.test(label),'generated code primary action must describe copying, got: '+label);
await root.locator('[data-vf-embed-copy-recommended]').click();await page.waitForFunction(()=>typeof window.__copiedText==='string');assert.equal(await page.evaluate(()=>window.__copiedText),code,'copy must write recommended code');
await root.locator('[data-vf-embed-mode-button="pro"]').click();await root.locator('[data-vf-embed-mode-button="pro"][aria-selected="true"]').waitFor({timeout:5000});
await root.locator('[data-vf-embed-mode-button="simple"]').click();await root.locator('[data-vf-embed-mode-button="simple"][aria-selected="true"]').waitFor({timeout:5000});
await page.screenshot({path:`proof/embed-${lang}-${width}.png`,fullPage:true});
await root.locator('[data-vf-embed-clear]').click();assert.equal(await root.locator('[data-vf-embed-url]').inputValue(),'');
proof.push({language:lang,width,initialMedia:'NONE',generatedIframe:'PASS',mode:'PASS',clear:'PASS',previewPlayback:'NOT_RUN'});await page.close();}
fs.writeFileSync('proof/embed.json',JSON.stringify({status:'PASS',cases:proof,production:'UNTOUCHED'},null,2));
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
