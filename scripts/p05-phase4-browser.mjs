import assert from 'node:assert/strict';
import { chromium } from 'playwright-core';

const base = process.env.PHASE4_BASE_URL ?? 'http://127.0.0.1:3105';
const username = process.env.VF_ADMIN_USERNAME;
const password = process.env.VF_ADMIN_PASSWORD;
const executablePath = process.env.CHROME_EXECUTABLE;
if (!username || !password || !executablePath) throw new Error('BROWSER_ENV_REQUIRED');

const browser = await chromium.launch({ executablePath, headless: true, args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const consoleErrors = [];
const apiErrors = [];
let watchApi = false;
page.on('console', (msg) => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
page.on('response', (response) => {
  if (watchApi && response.url().includes('/api/') && response.status() >= 400) apiErrors.push(`${response.status()} ${response.url()}`);
});

const expectNoVisibleErrors = async (stage) => {
  const errors = page.locator('.error-banner:visible, .inline-error:visible');
  assert.equal(await errors.count(), 0, `${stage} has visible UI error`);
};

const nav = async (label) => {
  const button = page.getByRole('button', { name: label, exact: true });
  await button.scrollIntoViewIfNeeded();
  await button.click();
  await page.waitForTimeout(220);
  await expectNoVisibleErrors(label);
};

try {
  await page.goto(base, { waitUntil: 'networkidle' });
  await page.getByPlaceholder('管理员').fill(username);
  await page.getByPlaceholder('密码').fill(password);
  await page.getByRole('button', { name: '登录', exact: true }).click();
  await page.getByRole('heading', { name: '决策总览', exact: true }).waitFor();
  consoleErrors.length = 0;
  watchApi = true;

  await nav('网站中心');
  await page.getByLabel('项目名称').fill('Phase 4 Synthetic Project');
  await page.getByRole('button', { name: '创建项目', exact: true }).click();
  await page.getByText('项目已创建。', { exact: true }).waitFor();
  await page.getByLabel('网站名称').fill('Phase 4 Synthetic Site');
  await page.getByLabel('网址').fill('https://phase4.example.test');
  await page.getByRole('button', { name: '添加网站', exact: true }).click();
  await page.getByText('网站已添加。', { exact: true }).waitFor();
  await expectNoVisibleErrors('Website create');

  await nav('关键词');
  await nav('页面中心');
  await nav('SEO 检查');

  const searchInput = page.getByRole('searchbox', { name: '全局搜索' });
  await searchInput.fill('Phase 4');
  await page.waitForTimeout(450);
  assert.match(await page.locator('body').innerText(), /Phase 4 Synthetic (Project|Site)/, 'Search result must include Phase 4 synthetic fixture');
  await expectNoVisibleErrors('Search');

  await nav('设置');
  await nav('备份 / 升级');
  const backupResponse = page.waitForResponse((r) => r.url().includes('/api/backups') && r.request().method() === 'POST');
  await page.getByRole('button', { name: '创建功能级备份', exact: true }).click();
  assert.equal((await backupResponse).status(), 201, 'Backup UI action');
  await page.getByText('功能级备份已创建。', { exact: true }).waitFor();
  await expectNoVisibleErrors('Backup');

  await page.setViewportSize({ width: 390, height: 844 });
  for (const label of ['决策总览', '网站中心', '关键词', '页面中心', 'SEO 检查', '设置', '备份 / 升级']) await nav(label);
  const overflow = await page.evaluate(() => ({ scrollWidth: document.documentElement.scrollWidth, innerWidth: window.innerWidth }));
  assert.ok(overflow.scrollWidth <= overflow.innerWidth + 2, `mobile body overflow: ${JSON.stringify(overflow)}`);
  assert.ok(await page.getByRole('searchbox', { name: '全局搜索' }).isVisible(), 'mobile Search must stay visible');

  assert.deepEqual(consoleErrors, [], `console errors: ${consoleErrors.join(' | ')}`);
  assert.deepEqual(apiErrors, [], `API errors: ${apiErrors.join(' | ')}`);
  console.log(JSON.stringify({
    result: 'PASS',
    pages: ['LOGIN', 'DASHBOARD', 'WEBSITE', 'KEYWORD', 'PAGE', 'AUDIT', 'SEARCH', 'SETTINGS', 'BACKUP'],
    desktop: 'PASS', mobile: 'PASS', consoleErrors: 0, apiErrors: 0, criticalUiBugs: 0,
  }));
} finally {
  await browser.close();
}
