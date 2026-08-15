import assert from 'node:assert/strict';
import { chromium } from 'playwright-core';

const base = process.env.PHASE3_BASE_URL ?? 'http://127.0.0.1:3105';
const username = process.env.VF_ADMIN_USERNAME;
const password = process.env.VF_ADMIN_PASSWORD;
const executablePath = process.env.CHROME_EXECUTABLE;
if (!username || !password || !executablePath) throw new Error('BROWSER_ENV_REQUIRED');

const browser = await chromium.launch({ executablePath, headless: true, args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const consoleErrors = [];
const apiErrors = [];
page.on('console', (msg) => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
let watchApi = false;
page.on('response', (response) => {
  if (watchApi && response.url().includes('/api/') && response.status() >= 400) apiErrors.push(`${response.status()} ${response.url()}`);
});

try {
  await page.goto(base, { waitUntil: 'networkidle' });
  await page.getByPlaceholder('管理员').fill(username);
  await page.getByPlaceholder('密码').fill(password);
  await page.getByRole('button', { name: '登录' }).click();
  await page.getByRole('heading', { name: '决策总览' }).waitFor();
  consoleErrors.length = 0;
  watchApi = true;

  for (const label of ['网站中心', 'Observed 关键词', '页面中心', 'SEO Audit', '设置', '备份 / 升级']) {
    await page.getByRole('button', { name: label, exact: true }).click();
    await page.waitForTimeout(250);
    assert.equal(await page.locator('.error').count(), 0, `${label} has visible error`);
  }

  const searchInput = page.locator('input[type="search"], input[placeholder*="搜索"], input[aria-label*="搜索"]');
  assert.ok(await searchInput.count() > 0, 'global Search must be available in browser UI');
  await searchInput.first().fill('Phase 3');
  await page.waitForTimeout(400);
  assert.match(await page.locator('body').innerText(), /Phase 3 Synthetic (Project|Site)/, 'browser search result');

  await page.getByRole('button', { name: '备份 / 升级', exact: true }).click();
  const backupResponse = page.waitForResponse((r) => r.url().includes('/api/backups') && r.request().method() === 'POST');
  await page.getByRole('button', { name: '创建功能级备份', exact: true }).click();
  assert.equal((await backupResponse).status(), 201, 'browser backup action');
  assert.equal(await page.locator('.error').count(), 0, 'backup UI error');

  assert.deepEqual(consoleErrors, [], `console errors: ${consoleErrors.join(' | ')}`);
  assert.deepEqual(apiErrors, [], `API errors: ${apiErrors.join(' | ')}`);
  console.log(JSON.stringify({ result: 'PASS', pages: ['LOGIN', 'DASHBOARD', 'WEBSITE', 'KEYWORD', 'PAGE', 'AUDIT', 'SEARCH', 'SETTINGS', 'BACKUP'], consoleErrors: 0, apiErrors: 0 }));
} finally {
  await browser.close();
}
