import { test, expect } from '@playwright/test'
import { existsSync, mkdirSync, writeFileSync, rmSync, rmdirSync } from 'node:fs'
import { join } from 'node:path'

// This is executed only on a disposable GitHub Actions Nginx HTTPS -> PHP 8.4
// with an actual extracted immutable official v015 FULL or final-source v016 FULL.
const base = process.env.P08_TEST_BASE_URL || ''
const installed = process.env.P08_HTTPS_VERSION || ''
const allowed = process.env.GITHUB_ACTIONS === 'true'
  && process.env.P08_ISOLATED_INSTALL_TEST === 'YES'
  && process.env.P08_V016_FINAL_HTTPS === 'YES'
  && base === 'https://127.0.0.1:18495'
  && (installed === '0.1.15' || installed === '0.1.16')
test.skip(!allowed, 'P08 v016 final HTTPS requires explicit local isolated Runner fixture')
test.use({ignoreHTTPSErrors: true})

test('real extracted v015/v016 Owner login/status browser safety and responsive widths', async ({page,request}) => {
  test.setTimeout(120_000)
  const errors: string[] = []
  const mutation: string[] = []
  page.on('pageerror', e => errors.push(e.message))
  page.on('request', r => {
    const url = r.url()
    if (r.method() === 'POST' && (
      url.endsWith('/app/system/update/check')
      || url.endsWith('/app/system/update/apply')
      || url.endsWith('/app/system/update/prepare')
    )) mutation.push(url)
  })
  const guest = await request.post('/app/system/update/check', {
    failOnStatusCode: false, maxRedirects: 0,
    headers: {Accept: 'application/json'},
    form: {_token: 'invalid-guest-token'}
  })
  expect([302,401,403,419]).toContain(guest.status())
  await page.goto('/app?tab=updates')
  await expect(page).toHaveURL(/\/login(?:\?.*)?$/, {timeout: 20000})
  await page.setExtraHTTPHeaders({Origin: base})
  await page.getByLabel('邮箱或管理员账号').fill('sqlite_admin')
  await page.getByLabel('密码').fill('Synthetic-SQLite-Owner-12345!')
  await page.getByRole('button', {name:'登录',exact:true}).click()
  await expect(page).toHaveURL(/\/app(?:\?.*)?$/, {timeout:20000})
  await page.getByRole('button', {name:'系统更新'}).click()
  await expect(page.getByRole('heading', {name:'系统更新', exact:true})).toBeVisible()
  await expect(page.getByRole('region', {name:'系统更新工作区'}))
    .toContainText('当前版本 '+installed)
  expect(mutation, 'Page entry must never auto-check or apply an update').toEqual([])
  for (const width of [390, 768, 1440]) {
    await page.setViewportSize({width, height: 860})
    await expect(page.getByRole('region', {name:'系统更新工作区'})).toBeVisible()
    const viewport=await page.evaluate(() => ({
      content: document.documentElement.scrollWidth,
      client: document.documentElement.clientWidth
    }))
    expect(viewport.content, 'No horizontal overflow at '+width+'px')
      .toBeLessThanOrEqual(viewport.client + 1)
  }
  console.log('P08_V016_FINAL_HTTPS_CHROMIUM_390_768_1440_'+installed.replaceAll('.','_')+'=PASS')

  const csrf=await page.context().request.post('/app/system/update/check', {
    failOnStatusCode:false,maxRedirects:0,
    headers:{Accept:'application/json',Origin:base},
    form:{_token:'deliberately-invalid-csrf'}
  })
  expect([403,419]).toContain(csrf.status())
  const hostile=await page.context().request.post('/app/system/update/check', {
    failOnStatusCode:false,maxRedirects:0,
    headers:{Accept:'application/json',Origin:'https://evil.example'},
    form:{_token:'deliberately-invalid-csrf'}
  })
  expect([403,419]).toContain(hostile.status())

  // No official v016 channel is published while this formal release is gated.
  // Original unbridged v015 PHP MUST NOT show an installable v016 offer.
  if (installed === '0.1.15') {
    await expect(page.getByRole('button', {name: /一键安全升级到/})).toHaveCount(0)
    console.log('P08_V016_FINAL_ORIGINAL_ISSUED_V015_BROWSER_NO_UNSAFE_NORMAL_BUTTON=PASS')
  }
  expect(mutation).toEqual([])
  // Genuine installed old/new PHP controller + native private journal:
  // corrupt only a disposable fixture to elicit a real HTTP 503, then remove.
  const siteRoot = process.env.P08_HTTPS_SITE_ROOT || ''
  const tempRoot = process.env.RUNNER_TEMP || ''
  expect(siteRoot.startsWith(tempRoot + '/p08-v016-final-browser-')).toBeTruthy()
  const journal = join(siteRoot, 'storage/app/private/adops/owner-next-update')
  const statusFile = join(journal, 'status.json')
  const journalExisted = existsSync(journal)
  expect(existsSync(statusFile), 'never overwrite an existing journal').toBe(false)
  if (!journalExisted) mkdirSync(journal, {recursive:true,mode:0o700})
  try {
    writeFileSync(statusFile, '{invalid-synthetic-json', {mode:0o600,flag:'wx'})
    const unavailable = await page.context().request.get('/app/system/update/next/status', {
      failOnStatusCode:false,headers:{Accept:'application/json'}
    })
    expect(unavailable.status()).toBe(503)
    expect((await unavailable.json()).status).toBe('STATE_UNAVAILABLE')
  } finally {
    if (existsSync(statusFile)) rmSync(statusFile)
    if (!journalExisted) rmdirSync(journal)
  }
  console.log('P08_V016_FINAL_NATIVE_OWNER_STATUS_HTTP_503_'+installed.replaceAll('.','_')+'=PASS')
  // Read-only status GET throttle: no installed-state mutation, 429 after
  // the genuine v015/v016 Laravel route exceeds its bounded 24/min budget.
  let throttled = false
  for (let n=0; n<28; n++) {
    const response = await page.context().request.get('/app/system/update/next/status', {
      failOnStatusCode:false,headers:{Accept:'application/json'}
    })
    if (response.status() === 429) throttled = true
    else expect(response.status()).toBe(200)
  }
  expect(throttled, 'genuine Owner status route must enforce 429').toBe(true)
  console.log('P08_V016_FINAL_NATIVE_OWNER_STATUS_HTTP_429_'+installed.replaceAll('.','_')+'=PASS')
  const health=await request.get('/up',{failOnStatusCode:false})
  expect(health.status()).toBe(200)
  expect(errors).toEqual([])
  console.log('P08_V016_FINAL_HTTPS_AUTH_CSRF_ORIGIN_NO_AUTO_MUTATION_'+installed.replaceAll('.','_')+'=PASS')
})
