const {chromium}=require('playwright'),fs=require('fs');
(async()=>{const b=await chromium.launch({headless:true}),checks=[];try{
for(const lang of ['en','zh'])for(const width of [1024,1440]){
 const ctx=await b.newContext({viewport:{width,height:900}}),p=await ctx.newPage();let manifests=0;
 p.on('request',r=>{if(/\.m3u8(?:[?#]|$)/i.test(r.url()))manifests++});
 const response=await p.goto('http://127.0.0.1:18880'+(lang==='zh'?'/zh':'')+'/m3u8-test-links/',{waitUntil:'networkidle'});
 if(!response.ok())throw Error('route status '+response.status());
 const root=p.locator('[data-vf-test-links-productized]').first();await root.waitFor();
 if(manifests!==0)throw Error('page made unsolicited manifest request');
 if(await p.locator('.vf-tool-breadcrumb').isVisible()||await p.locator('.vf-m3u8-launchbar__steps').isVisible())throw Error('duplicate navigation visible');
 const dims=await p.evaluate(()=>({scroll:document.documentElement.scrollWidth,client:document.documentElement.clientWidth}));if(dims.scroll>dims.client+1)throw Error('overflow '+JSON.stringify(dims));
 const rows=root.locator('[data-vf-test-links-list] article');if(await rows.count()<3)throw Error('built-in examples missing');
 await p.screenshot({path:'proof/test-links-'+lang+'-'+width+'-initial.png',fullPage:true});
 await root.locator('[data-vf-test-links-search]').fill('NO-SUCH-SAMPLE-583');
 await p.waitForTimeout(250);if(await rows.count()!==0)throw Error('search no-match failed');
 await root.locator('[data-vf-test-links-search]').fill('');await p.waitForTimeout(250);if(await rows.count()<3)throw Error('search reset failed');
 await root.locator('[data-vf-test-links-fav-row]').first().click();await root.locator('[data-vf-test-links-tab-button="favorites"]').click();
 if(await rows.count()<1)throw Error('favorite filter failed');await root.locator('[data-vf-test-links-tab-button="library"]').click();
 await root.locator('[data-vf-test-links-sample]').click();if(!await root.locator('[data-vf-test-links-current]').inputValue())throw Error('sample selection did not populate URL');
 await root.locator('[data-vf-test-links-verify-selected]').click();await root.locator('[data-vf-test-links-result]').waitFor({state:'visible',timeout:15000});
 if(manifests<1)throw Error('test did not make manifest request');
 await p.screenshot({path:'proof/test-links-'+lang+'-'+width+'-result.png',fullPage:true});
 checks.push({lang,width,zeroLoad:'PASS',search:'PASS',favorites:'PASS',sample:'PASS',testRequest:'PASS',overflow:'PASS'});await ctx.close();
}}finally{await b.close()}fs.writeFileSync('proof/test-links-check.json',JSON.stringify({status:'PASS',checks},null,2));console.log(JSON.stringify(checks));})().catch(e=>{console.error(e);process.exitCode=1});
