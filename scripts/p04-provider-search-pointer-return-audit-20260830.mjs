import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const base = process.env.VF_E2E_BASE_URL || 'http://127.0.0.1:19062';
const evidence = process.env.EVIDENCE;
const candidate = process.env.CANDIDATE;
const webRoot = process.env.WEB_ROOT;
const productRoot = process.env.PRODUCT_ROOT || path.join(process.cwd(), 'product');
if (!evidence || !candidate || !webRoot) throw new Error('provider pointer audit environment missing');

fs.mkdirSync(evidence, { recursive: true });
const password = 'Vf' + crypto.randomUUID().replaceAll('-', '') + 'Aa1';
const report = {
  schema: 'p04-provider-search-pointer-return-audit/v1',
  source_sha: candidate,
  status: 'FAIL',
  desktop: {},
  mobile: {},
  page_errors: [],
  console_errors: [],
  production_provider_actions_executed: false,
  synthetic_test_data_only: true,
};

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1365, height: 900 } });
const page = await context.newPage();
page.on('pageerror', (e) => report.page_errors.push(String(e?.stack || e)));
page.on('console', (m) => { if (m.type() === 'error') report.console_errors.push(m.text()); });
const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();
const assert = (value, message) => { if (!value) throw new Error(message); };

async function pointerClick(locator) {
  await locator.waitFor({ state: 'visible', timeout: 12000 });
  await locator.scrollIntoViewIfNeeded();
  await page.waitForTimeout(80);
  const box = await locator.boundingBox();
  if (!box || box.width <= 0 || box.height <= 0) throw new Error('provider pointer target has no box');
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.waitForTimeout(35);
  await page.mouse.up();
}

async function waitProviderList() {
  const toolbar = page.locator('[data-v275-toolbar="providers"]');
  await toolbar.waitFor({ state: 'visible', timeout: 15000 });
  const input = toolbar.locator('[data-v275-query]');
  await input.waitFor({ state: 'visible', timeout: 10000 });
  const account = page.locator('.v271-provider-list > .v271-provider-account')
    .filter({ hasText: 'V260 Linode 异常账号' }).first();
  await account.waitFor({ state: 'visible', timeout: 10000 });
  const manage = account.locator('[data-v271-action="provider-open"]');
  await manage.waitFor({ state: 'visible', timeout: 10000 });
  return { toolbar, input, account, manage };
}

async function freshProviders() {
  await page.goto(`${base}/index.php?audit=${Date.now()}#providers`, { waitUntil: 'domcontentloaded' });
  return await waitProviderList();
}

try {
  await page.goto(`${base}/setup.php`, { waitUntil: 'domcontentloaded' });
  await page.locator('#site_name').fill('VF Infra Provider Pointer Return Audit');
  await page.locator('#password').fill(password);
  await page.locator('#password_confirm').fill(password);
  await Promise.all([
    page.waitForURL(/login\.php\?installed=1/),
    page.getByRole('button', { name: '安装并进入系统' }).click(),
  ]);
  await page.locator('#admin-password').fill(password);
  await Promise.all([
    page.waitForURL(/index\.php(?:#.*)?$/),
    page.getByRole('button', { name: '登录' }).click(),
  ]);
  assert((await page.locator('meta[name="app-version"]').getAttribute('content')) === '2.8.11', 'version mismatch');

  const fixture = execFileSync('php', ['tests/fixtures/v260-user-task-fixture.php', webRoot], {
    cwd: productRoot,
    encoding: 'utf8',
  });
  assert(fixture.includes('P04_V260_USER_TASK_FIXTURE_PASS'), 'provider fixture failed');

  let current = await freshProviders();
  await current.input.fill('V260 Linode');
  await page.waitForTimeout(240);
  report.desktop.before = {
    query: await current.input.inputValue(),
    count: clean(await current.toolbar.locator('[data-v275-count]').innerText()),
    active: await page.evaluate(() => document.activeElement?.matches?.('[data-v275-query]') || false),
  };
  assert(report.desktop.before.query === 'V260 Linode', 'desktop provider query not set');
  assert(report.desktop.before.active === true, 'desktop provider search must still own focus before pointer click');
  const providerId = await current.manage.getAttribute('data-id');
  assert(Boolean(providerId), 'provider id missing');

  await pointerClick(current.manage);
  await page.waitForFunction((id) => location.hash === `#provider/${encodeURIComponent(id)}`, providerId, { timeout: 10000 });
  report.desktop.detail_after_pointer = await page.evaluate(() => location.hash);
  await page.goBack();
  await page.waitForFunction(() => location.hash === '#providers', null, { timeout: 10000 });
  current = await waitProviderList();
  await page.waitForTimeout(220);
  report.desktop.after_browser_back = {
    query: await current.input.inputValue(),
    count: clean(await current.toolbar.locator('[data-v275-count]').innerText()),
  };
  await page.screenshot({ path: `${evidence}/01-provider-after-browser-back.png`, fullPage: true, animations: 'disabled' });

  await current.input.fill('V260 Linode');
  await page.waitForTimeout(180);
  await pointerClick(current.manage);
  await page.waitForFunction((id) => location.hash === `#provider/${encodeURIComponent(id)}`, providerId, { timeout: 10000 });
  const backbar = page.locator('[data-v275-context-backbar]');
  await backbar.waitFor({ state: 'visible', timeout: 10000 });
  const back = backbar.locator('[data-v275-go="#providers"]');
  await pointerClick(back);
  await page.waitForFunction(() => location.hash === '#providers', null, { timeout: 10000 });
  current = await waitProviderList();
  await page.waitForTimeout(220);
  report.desktop.after_context_back = {
    query: await current.input.inputValue(),
    count: clean(await current.toolbar.locator('[data-v275-count]').innerText()),
  };

  await page.setViewportSize({ width: 390, height: 844 });
  current = await freshProviders();
  await current.input.fill('V260 Linode');
  await page.waitForTimeout(220);
  const mobileBox = await current.manage.boundingBox();
  report.mobile.before = {
    query: await current.input.inputValue(),
    active: await page.evaluate(() => document.activeElement?.matches?.('[data-v275-query]') || false),
    action_height: mobileBox?.height || 0,
  };
  await pointerClick(current.manage);
  await page.waitForFunction((id) => location.hash === `#provider/${encodeURIComponent(id)}`, providerId, { timeout: 10000 });
  report.mobile.detail_after_pointer = await page.evaluate(() => location.hash);
  await page.goBack();
  await page.waitForFunction(() => location.hash === '#providers', null, { timeout: 10000 });
  current = await waitProviderList();
  await page.waitForTimeout(220);
  report.mobile.after_browser_back = {
    query: await current.input.inputValue(),
    overflow: await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth),
  };
  await page.screenshot({ path: `${evidence}/02-provider-mobile-after-browser-back.png`, fullPage: true, animations: 'disabled' });

  assert(report.desktop.after_browser_back.query === 'V260 Linode', `provider browser Back lost query: ${report.desktop.after_browser_back.query}`);
  assert(report.desktop.after_context_back.query === 'V260 Linode', `provider context Back lost query: ${report.desktop.after_context_back.query}`);
  assert(report.mobile.before.active === true, 'mobile provider search must still own focus before pointer click');
  assert(report.mobile.before.action_height >= 40, `mobile provider action target ${report.mobile.before.action_height}`);
  assert(report.mobile.after_browser_back.query === 'V260 Linode', `mobile provider Back lost query: ${report.mobile.after_browser_back.query}`);
  assert(report.mobile.after_browser_back.overflow <= 1, `mobile provider overflow ${report.mobile.after_browser_back.overflow}`);
  assert(report.page_errors.length === 0, `page errors ${JSON.stringify(report.page_errors)}`);
  assert(report.console_errors.length === 0, `console errors ${JSON.stringify(report.console_errors)}`);
  report.status = 'PASS';
} finally {
  fs.writeFileSync(`${evidence}/P04_PROVIDER_SEARCH_POINTER_RETURN_AUDIT.json`, JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}

console.log(`P04_PROVIDER_SEARCH_POINTER_RETURN_AUDIT=${report.status}`);
if (report.status !== 'PASS') process.exit(1);
