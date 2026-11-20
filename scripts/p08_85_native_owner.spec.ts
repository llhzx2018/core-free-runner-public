import { test, expect } from '@playwright/test'

/** P08 #85: issued v0.1.13 authentic Laravel/Vue Owner page and worker.
 * ONLY synthetic localhost publisher v0.1.14; not a Release/Production proof. */
const base=process.env.P08_TEST_BASE_URL||''
const approved=process.env.GITHUB_ACTIONS==='true'
 && process.env.P08_ISOLATED_INSTALL_TEST==='YES'
 && process.env.P08_85_UNISSUED_POSITIVE==='YES'
 && base==='https://127.0.0.1:18519'
test.skip(!approved,'P08 #85 strictly isolated loopback HTTPS only')
test.use({ignoreHTTPSErrors:true})

test('issued v013 in-app normal one-click → native backup → 014 same-site readback',async({page,request})=>{
  test.setTimeout(180000)
  const errors:string[]=[]
  page.on('pageerror',e=>errors.push(e.message))

  const unauthorized=await request.post('/app/system/update/next/one-click',{
    form:{_token:'wrong-guest-csrf'},failOnStatusCode:false,maxRedirects:0,
    headers:{Accept:'application/json'},
  })
  expect([401,419,302,403]).toContain(unauthorized.status())

  await page.goto('/app?tab=updates')
  await expect(page).toHaveURL(/\/login(?:\?.*)?$/)
  const isSqlite=process.env.P08_TEST_DB_DRIVER==='sqlite'
  const username=isSqlite?'sqlite_admin':'mysql_admin'
  const password=isSqlite
    ?'Synthetic-SQLite-Owner-12345!'
    :'Synthetic-Owner-Only-12345!'
  await page.getByLabel('邮箱或管理员账号').fill(username)
  await page.getByLabel('密码').fill(password)
  await page.getByRole('button',{name:'登录',exact:true}).click()
  await expect(page).toHaveURL(/\/app(?:\?.*)?$/, {timeout:20000})
  await page.getByRole('button',{name:'系统更新'}).click()
  const panel=page.getByRole('region',{name:'系统更新工作区'})
  await expect(panel).toBeVisible()
  await expect(panel).toContainText('当前版本 0.1.13')
  await expect(page.getByRole('region',{name:'官方更新与升级'})).toBeVisible()
  await expect(page.getByRole('button',{name:'检查官方更新',exact:true})).toBeEnabled()
  await expect(page.getByRole('button',{name:/一键安全升级到/})).toHaveCount(0)
  for(const width of [390,768,1440]){
    await page.setViewportSize({width,height:860})
    expect(await page.evaluate(()=>document.documentElement.scrollWidth
      <= document.documentElement.clientWidth+1)).toBe(true)
  }
  console.log('P08_85_REAL_ISSUED_V013_NORMAL_OWNER_UI=PASS')

  const csrfDenied=await page.context().request.post('/app/system/update/next/one-click',{
    form:{_token:'definitely-invalid-csrf'},failOnStatusCode:false,maxRedirects:0,
    headers:{Accept:'application/json'},
  })
  expect(csrfDenied.status()).toBe(419)
  console.log('P08_85_NORMAL_OWNER_ONE_CLICK_CSRF_DENIAL=PASS')

  const checkResponse=page.waitForResponse(r=>r.url().endsWith('/app/system/update/next/check')
     && r.request().method()==='POST')
  await page.getByRole('button',{name:'检查官方更新',exact:true}).click()
  const check=await checkResponse
  expect(check.status()).toBe(200)
  expect(await check.json()).toMatchObject({
    status:'OFFICIAL_NEXT_VERIFIED_NOT_STAGED',target_version:'0.1.14',
    can_install:false,
  })
  await expect(page.getByRole('button',{name:'一键安全升级到 0.1.14'})).toBeEnabled()
  console.log('P08_85_REAL_ISSUED_OWNER_NEXT_CHANNEL_CHECK=PASS')

  const accepted=page.waitForResponse(r=>r.url().endsWith('/app/system/update/next/one-click')
      && r.request().method()==='POST')
  await page.getByRole('button',{name:'一键安全升级到 0.1.14'}).click()
  const response=await accepted
  expect(response.status()).toBe(202)
  const receipt=await response.json() as {status:string;preparation_id:string;worker_dispatch:string}
  expect(receipt.status).toBe('PENDING_PREPARE')
  expect(receipt.preparation_id).toMatch(/^[a-f0-9]{32}$/)
  expect(receipt.worker_dispatch).toBe('STARTED')
  console.log('P08_85_ONE_REAL_OWNER_BUTTON_SUBMITTED_AND_WORKER_STARTED=PASS')

  await expect.poll(async()=>{
    const state=await page.context().request.get('/app/system/update/next/status',{
      timeout:10000,failOnStatusCode:false})
    if(state.status()!==200)return 'WAIT_HTTP'
    const s=await state.json() as {status?:string;preparation_id?:string;target_version?:string}
    if(s.preparation_id!==receipt.preparation_id)return 'UNKNOWN_GENERATION'
    if(s.status==='NEEDS_RECOVERY')return 'BLOCKED_RECOVERY'
    return s.status==='SUCCEEDED'&&s.target_version==='0.1.14'
      ? 'SUCCEEDED':'WAIT'
  },{timeout:120000,intervals:[1000,2000,3000]}).toBe('SUCCEEDED')
  const runtime=await page.context().request.get('/app/system/update/status',{
    failOnStatusCode:false,timeout:10000})
  expect(runtime.status()).toBe(200)
  expect(await runtime.json()).toMatchObject({version:'0.1.14'})
  console.log('P08_85_ISSUED_PHP_REAL_WORKER_BACKUP_NATIVE_ATOMIC=PASS')

  // Same Owner client remains an authenticated dashboard after pointer switch.
  await page.reload()
  await page.getByRole('button',{name:'系统更新'}).click()
  await expect(page.getByRole('region',{name:'系统更新工作区'}))
    .toContainText('当前版本 0.1.14',{timeout:30000})
  const replay=await page.context().request.post('/app/system/update/next/one-click',{
    form:{_token:'repeat-old-intent'},failOnStatusCode:false,maxRedirects:0,
    headers:{Accept:'application/json'},
  })
  expect([419,409]).toContain(replay.status())
  expect(errors).toEqual([])
  console.log('P08_85_NATIVE_OWNER_POST_SWITCH_SAME_PAGE_RUNTIME=PASS')
  console.log('P08_85_PUBLISHED_V014=NO')
})
