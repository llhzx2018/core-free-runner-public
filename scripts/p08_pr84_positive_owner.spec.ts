import {test, expect} from '@playwright/test'

/**
 * CI-only P08 PR84 proof: genuine installed v013 old PHP one-time gateway,
 * localhost strictly isolated synthetic (NOT ISSUED) v014 GitHub metadata,
 * verified bytes and rootless Owner Worker. No public release/Production.
 */
const base=process.env.P08_TEST_BASE_URL||''
const enabled=process.env.GITHUB_ACTIONS==='true'
 && process.env.P08_ISOLATED_INSTALL_TEST==='YES'
 && process.env.P08_PR84_UNISSUED_POSITIVE==='YES'
 && base==='https://127.0.0.1:18519'
test.skip(!enabled,'P08 PR84 isolated loopback only')
test.use({ignoreHTTPSErrors:true})

test('one real authenticated Owner click → old v013 worker → real native Atomic to synthetic v014',async({page,request})=>{
  test.setTimeout(240_000)
  const pageErrors:string[]=[]
  page.on('pageerror',e=>pageErrors.push(e.message))
  await page.goto('/p08-owner-first-forward.php')
  await expect(page.getByRole('heading',{name:'验证管理员身份'})).toBeVisible()
  const pw=process.env.P08_TEST_DB_DRIVER==='sqlite'
    ? 'Synthetic-SQLite-Owner-12345!' : 'Synthetic-Owner-Only-12345!'
  await page.locator('#ownerpassword').fill(pw)
  const login=page.waitForResponse(r=>r.url().endsWith('/p08-owner-first-forward.php')
    && r.request().method()==='POST')
  await page.getByRole('button',{name:'验证并继续'}).click()
  expect((await login).status()).toBe(200)
  await expect(page.getByRole('heading',{name:'首次安全升级'})).toBeVisible()
  console.log('P08_PR84_OWNER_REAL_LOGIN_ISOLATED=PASS')
  const clicked=page.waitForResponse(r=>r.url().endsWith('/p08-owner-first-forward.php')
    && r.request().method()==='POST')
  await page.getByRole('button',{name:'检查正式更新并安全升级'}).click()
  expect((await clicked).status()).toBe(200)
  await expect(page.getByRole('heading',{name:'升级任务已提交'})).toBeVisible()
  console.log('P08_PR84_SINGLE_OWNER_SUBMIT_NATIVE_INTENT=PASS')
  const state=await request.get('/p08-owner-first-forward.php')
  expect(state.status()).toBe(200)
  await expect.poll(async()=>{
    const response=await page.goto('/p08-owner-first-forward.php')
    if(response?.status()!==200)return 'HTTP_BLOCKED'
    return (await page.locator('h1').textContent())?.trim()||'NO_HEADING'
  },{timeout:180000,intervals:[700,1300,2000,3000]})
    .toBe('首次升级已完成')
  console.log('P08_PR84_REAL_WORKER_ATOMIC_013_TO_UNISSUED_014=PASS')
  expect(pageErrors).toEqual([])
  // The one-time gate remains incapable of a second POST on the new version.
  const oldPost=await request.post('/p08-owner-first-forward.php',{
    failOnStatusCode:false,form:{action:'activate',csrf:'fake-repeat'},maxRedirects:0})
  expect(oldPost.status()).toBe(409)
  console.log('P08_PR84_ONE_TIME_GATE_REUSE_REFUSED=PASS')
})
