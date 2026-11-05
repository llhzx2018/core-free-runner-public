'use strict';
const path=require('node:path');
const root=process.argv[2];
if(!root||process.env.P01_TEST_ORIGIN!=='http://127.0.0.1:18631'||!process.env.P01_TEST_PASSWORD)
  throw new Error('DENY_NONDISPOSABLE_CREDENTIAL_TEST');
const {chromium}=require(path.resolve(root,'tests/integration/node_modules/playwright'));
const assert=(ok,msg)=>{if(!ok)throw new Error('P01 credential fallback: '+msg)};
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try {
  const ctx=await browser.newContext();
  const base=process.env.P01_TEST_ORIGIN;
  await ctx.route(/https?:\/\/(?!127\.0\.0\.1)/,r=>r.abort());
  const login=await ctx.request.post(base+'/api.php?action=login',{data:{password:process.env.P01_TEST_PASSWORD}});
  assert(login.ok() && (await login.text()).includes('"ok":true'),'synthetic admin login');
  const fetchStatus=async()=>{
   const r=await ctx.request.get(base+'/api.php?action=update_credential_status');
   assert(r.status()===200,'credential status HTTP');
   const j=await r.json();
   assert(j.ok===true && typeof j.status?.configured==='boolean','status must be boolean');
   assert(!Object.hasOwn(j.status,'token'),'secret not returned');
   return j.status;
  };
  const before=await fetchStatus();
  assert(before.configured===false,'fresh synthetic install must not have credential');
  const page=await ctx.request.get(base+'/update-credential.php',{maxRedirects:0});
  assert(page.status()===200,'independent recovery page');
  const html=await page.text();
  const m=html.match(/name="_csrf" value="([^"]+)"/);
  assert(m && m[1].length>=16,'real hidden CSRF input');
  const invalid='INVALID_SYNTHETIC_READ_TOKEN_1234567890_ABCDEF';
  const submitted=await ctx.request.post(base+'/update-credential.php',{form:{_csrf:m[1],token:invalid},maxRedirects:0});
  assert(submitted.status()===200,'valid CSRF must reach verified-only handler');
  const result=await submitted.text();
  assert(!result.includes(invalid),'invalid token echoed to UI');
  assert(!result.includes('更新授权已验证并启用'),'invalid token accepted');
  const after=await fetchStatus();
  assert(after.configured===before.configured,'credential status changed after rejected token');
  assert(after.source===before.source,'credential source changed after rejected token');
  console.log('P01_IA6_CREDENTIAL_VALID_CSRF_INVALID_TOKEN_FAIL_CLOSED=PASS');
  console.log('P01_IA6_CREDENTIAL_NO_LEAK_NO_INVALID_SAVE=PASS');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
