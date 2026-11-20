import { test, expect } from '@playwright/test'

/** One-off real old installed 0.1.12 PHP+Vue HTTPS, no mock browser routes.
 * Only the isolated locally trusted GitHub API is synthetic. Real candidate
 * v013 ZIP, real old PHP worker, real SQLite backup and pointer transaction.
 */
test.use({ ignoreHTTPSErrors: true })
test('authentic v012 Atomic-installed 607b origin: one Owner click through real HTTPS to v013', async ({page,request}) => {
  test.setTimeout(170_000)
  expect(process.env.GITHUB_ACTIONS).toBe('true')
  expect(process.env.P08_ISOLATED_INSTALL_TEST).toBe('YES')
  expect(process.env.P08_TEST_BASE_URL).toBe('https://127.0.0.1:18497')

  const browserErrors: string[] = []
  let actualOwnerPosts = 0
  page.on('pageerror', e => browserErrors.push(e.message))
  page.on('request', r => {
    if (r.url().endsWith('/app/system/update/next/one-click') && r.method()==='POST')
      actualOwnerPosts++
  })
  const guest = await request.get('/app/system/update/next/status', {
    maxRedirects: 0, failOnStatusCode: false
  })
  expect([302,401,403]).toContain(guest.status())
  await page.goto('/login')
  await page.getByLabel('邮箱或管理员账号').fill('sqlite_admin')
  await page.getByLabel('密码').fill('Synthetic-SQLite-Owner-12345!')
  await page.getByRole('button', {name:'登录', exact:true}).click()
  await expect(page).toHaveURL(/\/app(?:\?.*)?$/, {timeout:20000})
  await page.getByRole('button',{name:'系统更新'}).click()
  const workspace = page.locator('[aria-label="系统更新工作区"]')
  await expect(workspace).toBeVisible()
  await expect(workspace).toContainText('0.1.12')
  for (const width of [390,768,1440]) {
    await page.setViewportSize({width,height:820})
    const horizontal = await page.evaluate(() => document.documentElement.scrollWidth >
      document.documentElement.clientWidth+1)
    expect(horizontal,'No horizontal overflow at '+width).toBe(false)
  }
  expect(actualOwnerPosts).toBe(0)
  const bad = await page.request.post('/app/system/update/next/one-click',{
    failOnStatusCode:false, headers:{Accept:'application/json'},
    form:{_token:'deliberately-invalid-p08-v013-test'}
  })
  expect(bad.status()).toBe(419)
  const checkedPromise=page.waitForResponse(r=>
    r.url().endsWith('/app/system/update/next/check') && r.request().method()==='POST'
  )
  await page.getByRole('button',{name:'检查官方更新'}).click()
  const checked=await checkedPromise
  expect(checked.status()).toBe(200)
  expect(await checked.json()).toMatchObject({
    status:'OFFICIAL_NEXT_VERIFIED_NOT_STAGED',
    source_version:'0.1.12',
    target_version:'0.1.13',
    can_install:false
  })
  await expect(page.getByRole('button',{name:'一键安全升级到 0.1.13'})).toBeVisible()
  expect(actualOwnerPosts).toBe(0)
  console.log('P08_607B_OLD_CLIENT_AUTHENTICATED_HTTPS_CHECK_AND_NO_AUTO_APPLY=PASS')
  const click=page.waitForResponse(r=>
    r.url().endsWith('/app/system/update/next/one-click') && r.request().method()==='POST',
    {timeout:30000})
  await page.getByRole('button',{name:'一键安全升级到 0.1.13'}).click()
  const submitted=await click
  expect(submitted.status()).toBe(202)
  expect(await submitted.json()).toMatchObject({
    status:'PENDING_PREPARE',
    worker_dispatch:'STARTED'
  })
  expect(actualOwnerPosts).toBe(1)
  console.log('P08_607B_OLD_CLIENT_SINGLE_OWNER_CLICK_ACCEPTED=PASS')
  await expect.poll(async () => {
    const r=await page.request.get('/app/system/update/next/status',{
      failOnStatusCode:false,timeout:9000,
      headers:{Accept:'application/json'}
    })
    if(r.status()!==200)return 'HTTP_'+r.status()
    const value=await r.json()
    if(value.status==='NEEDS_RECOVERY')return 'NEEDS_RECOVERY'
    if(value.status==='SUCCEEDED'&&value.target_version==='0.1.13')
      return 'SUCCEEDED'
    return 'WAIT'
  }, {timeout:110000, intervals:[500,1200,2500,3500]}).toBe('SUCCEEDED')
  console.log('P08_607B_OLD_CLIENT_NATIVE_WORKER_PREPARE_AND_APPLY=PASS')
  await page.reload()
  if (await workspace.count()===0) {
    await page.getByRole('button',{name:'系统更新'}).click()
  }
  await expect(page.locator('[aria-label="系统更新工作区"]')).toContainText('0.1.13')
  expect(actualOwnerPosts).toBe(1)
  expect(browserErrors).toEqual([])
  console.log('P08_607B_AUTHENTIC_OLD_PHP_TO_NEW_VUE_READBACK=PASS')
})
