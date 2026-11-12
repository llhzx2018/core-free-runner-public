import { expect, test } from '@playwright/test'
import { spawnSync } from 'node:child_process'

const site = '/home/p08ci/htdocs/adops.kewaro.com'
const origin = 'https://127.0.0.1:18443'
const chromeChannel = process.env.P08_R46_CHROME_CHANNEL === 'chrome' ? { channel: 'chrome' } : {}
test.use({ ignoreHTTPSErrors: true, launchOptions: { ...chromeChannel, args: ['--no-sandbox'] } })
test.setTimeout(145_000)

test('real HTTPS Owner session + CSRF click → Linux cron site-user worker → live version status', async ({ page, request }) => {
  // An unauthenticated visitor must not even read the private upgrade status.
  const guest = await request.get(origin + '/app/system/update/status', { maxRedirects: 0 })
  expect(guest.status()).toBe(302)
  expect(guest.headers().location).toContain('/login')
  console.log('P08_R46_UNAUTHENTICATED_UPGRADE_STATUS_DENIED=PASS')

  await page.goto(origin + '/login')
  await page.getByLabel('邮箱').fill('owner@isolated.example')
  await page.getByLabel('密码').fill('Synthetic-Owner-Test-1234!')
  await page.getByRole('button', { name: '登录' }).click()
  await page.waitForURL(/\/app(?:\?|$)/, { timeout: 20_000 })

  await page.goto(origin + '/app?tab=updates')
  await expect(page.getByRole('button', { name: '执行原子升级' })).toBeEnabled({ timeout: 20_000 })
  await expect(page.getByText('0.1.0', { exact: true })).toBeVisible()
  const ready = await page.evaluate(async () => {
    const r = await fetch('/app/system/update/status', {
      credentials: 'same-origin', headers: { Accept: 'application/json' }
    })
    return { status: r.status, body: r.ok ? await r.json() : null }
  })
  expect(ready.status).toBe(200)
  expect(ready.body?.can_upgrade).toBe(true)
  expect(ready.body?.job_status).toBe('NONE')

  // Signed Owner state is not a CSRF bypass. Browser fetch omits _token and
  // X-CSRF-TOKEN. The actual button uses the Laravel-generated form token.
  const noCsrf = await page.evaluate(async () => {
    const r = await fetch('/app/system/update/request', {
      method: 'POST', credentials: 'same-origin',
      headers: { Accept: 'application/json' }
    })
    return r.status
  })
  expect(noCsrf).toBe(419)
  console.log('P08_R46_OWNER_SESSION_AND_CSRF_NEGATIVE=PASS')

  await page.getByRole('button', { name: '执行原子升级' }).click()
  await expect(page.locator('.upgrade-grid [role="status"]')).toContainText('等待独立升级程序', { timeout: 20_000 })
  const pending = await page.evaluate(async () => {
    const r = await fetch('/app/system/update/status', {
      credentials: 'same-origin', headers: { Accept: 'application/json' }
    })
    return r.ok ? await r.json() : null
  })
  expect(pending?.job_status).toBe('PENDING')
  expect(pending?.can_upgrade).toBe(false)
  expect(pending?.version).toBe('0.1.0')
  console.log('P08_R46_REAL_OWNER_BROWSER_CLICK_PENDING_NO_SWITCH=PASS')

  // A separate real system-cron schedule wakes the installed site-user CLI.
  // The test itself NEVER calls OwnerUpgradeJob::work() and never executes the
  // worker directly. Site-user owner-job locking and signed V2 offer guard
  // still apply. No root-owned updater gets its input from the browser.
  const line = '* * * * * /usr/bin/php8.4 ' + site +
    '/current/src/Upgrade/owner-upgrade-worker.php ' + site +
    ' >> /home/p08ci/r46-cron.log 2>&1\n'
  const scheduled = spawnSync('sudo', ['crontab', '-u', 'p08ci', '-'], {
    input: line, encoding: 'utf8', timeout: 10_000
  })
  expect(scheduled.status, scheduled.stderr).toBe(0)
  console.log('P08_R46_REAL_SITE_USER_CRONTAB_INSTALLED_IN_ISOLATION=PASS')

  // On each read the stable public gateway resolves the current immutable
  // SHA. If PHP-FPM remains on the old code or the worker fails, this fails.
  await expect(page.locator('.upgrade-grid [role="status"]')).toContainText('已完成', { timeout: 115_000 })
  await expect(page.getByText('0.1.1', { exact: true })).toBeVisible()
  const finished = await page.evaluate(async () => {
    const r = await fetch('/app/system/update/status', {
      credentials: 'same-origin', headers: { Accept: 'application/json' }
    })
    return { status: r.status, data: r.ok ? await r.json() : null }
  })
  expect(finished.status).toBe(200)
  expect(finished.data?.job_status).toBe('SUCCEEDED')
  expect(finished.data?.version).toBe('0.1.1')
  const log = spawnSync('sudo', ['cat', '/home/p08ci/r46-cron.log'], {
    encoding: 'utf8', timeout: 10_000
  })
  expect(log.status, log.stderr).toBe(0)
  expect(log.stdout).toContain('P08_OWNER_UPDATE_WORKER=SUCCEEDED')
  console.log('P08_R46_REAL_CRON_SEPARATE_WORKER_APPLIED_SIGNED_ATOMIC=PASS')
  console.log('P08_R46_BROWSER_LIVE_FPM_NEW_RELEASE_READBACK=PASS')
})
