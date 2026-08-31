import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const base = process.env.VF_E2E_BASE_URL || 'http://127.0.0.1:19048';
const evidence = process.env.EVIDENCE;
const candidate = process.env.CANDIDATE;
const webRoot = process.env.WEB_ROOT;
const productRoot = process.env.PRODUCT_ROOT || path.join(process.cwd(), 'product');
if (!evidence || !candidate || !webRoot) throw new Error('P04 provider UX browser environment missing');

const password = 'Vf' + crypto.randomUUID().replaceAll('-', '') + 'Aa1';
const report = {
  status: 'FAIL', source_sha: candidate,
  list: {}, detail: {}, mobile: {},
  page_errors: [], console_errors: [],
  production_provider_actions_executed: false,
};
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1365, height: 900 } });
const page = await context.newPage();
page.on('pageerror', (e) => report.page_errors.push(String(e?.stack || e)));
page.on('console', (m) => { if (m.type() === 'error') report.console_errors.push(m.text()); });
const assert = (value, message) => { if (!value) throw new Error(message); };

async function cold(hash) {
  await page.goto('about:blank');
  await page.goto(`${base}/index.php#${hash}`, { waitUntil: 'domcontentloaded' });
  await page.locator('#v270-app h1').waitFor({ state: 'visible', timeout: 15000 });
  await page.waitForTimeout(650);
}

async function providerAccount() {
  const account = page.locator('.v271-provider-list > .v271-provider-account').filter({ hasText: 'V260 Linode 异常账号' }).first();
  await account.waitFor({ state: 'visible', timeout: 10000 });
  return account;
}

try {
  await page.goto(`${base}/setup.php`, { waitUntil: 'domcontentloaded' });
  await page.locator('#site_name').fill('VF Infra Provider Daily UX Gate');
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

  const fixture = execFileSync('php', ['tests/fixtures/v260-user-task-fixture.php', webRoot], { cwd: productRoot, encoding: 'utf8' });
  assert(fixture.includes('P04_V260_USER_TASK_FIXTURE_PASS'), 'provider fixture failed');

  // 1) Current degraded-provider scenario with known billing data.
  await cold('providers');
  assert(await page.locator('body.v2813-provider-ux').count() === 1, 'provider UX body class missing');
  let account = await providerAccount();
  assert((await account.getAttribute('data-v2813-provider-risk')) === 'attention', 'degraded provider attention missing');
  let manage = account.locator('[data-v271-action="provider-open"]');
  assert((await manage.getAttribute('aria-label')) === '管理 V260 Linode 异常账号', 'provider manage aria missing');
  const providerId = await manage.getAttribute('data-id');
  assert(Boolean(providerId), 'provider account id missing');
  const brief = page.locator('.v2813-provider-brief');
  await brief.waitFor({ state: 'visible', timeout: 10000 });
  const initialBrief = (await brief.innerText()).replace(/\s+/g, ' ').trim();
  assert(initialBrief.includes('当前 1 个连接账号'), `provider brief count mismatch: ${initialBrief}`);
  assert(initialBrief.includes('1 个需优先处理'), `provider attention brief mismatch: ${initialBrief}`);
  assert(!initialBrief.includes('费用未记录'), `known billing should not be unknown: ${initialBrief}`);
  report.list.attention = 'PASS';
  report.list.summary = 'PASS';
  report.list.known_billing = 'PASS';
  await page.screenshot({ path: `${evidence}/01-providers-known-billing.png`, fullPage: true, animations: 'disabled' });

  // 2) Remove only the synthetic billing snapshot to prove unknown-cost communication.
  execFileSync('php', ['-r', 'require getenv("WEB_ROOT")."/bootstrap.php"; Database::connection()->exec("DELETE FROM provider_billing_snapshots WHERE provider_account_id IN (SELECT id FROM provider_accounts WHERE external_account_id=\'v260-linode-account\')");'], {
    cwd: productRoot,
    env: { ...process.env, WEB_ROOT: webRoot },
    encoding: 'utf8',
  });
  await cold('providers');
  account = await providerAccount();
  assert((await account.getAttribute('data-v2813-provider-risk')) === 'attention', 'provider attention lost after billing snapshot removal');
  const unknownBrief = (await page.locator('.v2813-provider-brief').innerText()).replace(/\s+/g, ' ').trim();
  assert(unknownBrief.includes('1 个费用未记录'), `unknown billing brief missing: ${unknownBrief}`);
  const costCell = account.locator('.v271-provider-cell').filter({ hasText: '本月费用' }).first();
  assert((await costCell.innerText()).includes('未记录'), 'provider row must expose unknown monthly cost');
  report.list.unknown_billing = 'PASS';
  await page.screenshot({ path: `${evidence}/02-providers-unknown-billing.png`, fullPage: true, animations: 'disabled' });

  // 3) Existing Current provider-open action must still own pointer navigation.
  manage = account.locator('[data-v271-action="provider-open"]');
  await manage.click();
  await page.waitForFunction((id) => location.hash === `#provider/${encodeURIComponent(id)}`, providerId, { timeout: 10000 });
  await page.locator('.v271-provider-summary').waitFor({ state: 'visible', timeout: 10000 });
  assert(await page.locator('.v271-provider-summary .v271-summary-card[data-v2813-provider-priority]').count() >= 1, 'provider detail priority missing');
  const nextHelp = page.locator('.v271-help[data-v2813-provider-next]').first();
  await nextHelp.waitFor({ state: 'visible', timeout: 10000 });
  assert((await nextHelp.locator('strong').innerText()).trim() === '下一步：', 'provider next-action copy not simplified');
  const causePanel = page.locator('.v271-panel[data-v2813-provider-cause="attention"]').first();
  assert(await causePanel.count() === 1, 'provider cause panel attention hierarchy missing');
  report.detail.pointer_navigation = 'PASS';
  report.detail.priority = 'PASS';
  report.detail.next_action = 'PASS';
  report.detail.cause = 'PASS';
  await page.screenshot({ path: `${evidence}/03-provider-detail.png`, fullPage: true, animations: 'disabled' });

  // 4) Mobile account view remains readable and actionable.
  await page.setViewportSize({ width: 390, height: 844 });
  await cold('providers');
  account = await providerAccount();
  assert((await account.getAttribute('data-v2813-provider-risk')) === 'attention', 'mobile provider risk missing');
  manage = account.locator('[data-v271-action="provider-open"]');
  assert((await manage.getAttribute('aria-label')) === '管理 V260 Linode 异常账号', 'mobile provider aria missing');
  const box = await manage.boundingBox();
  assert(box && box.height >= 40, `mobile provider action target ${JSON.stringify(box)}`);
  const overflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - window.innerWidth);
  assert(overflow <= 1, `mobile horizontal overflow ${overflow}`);
  report.mobile.risk = 'PASS';
  report.mobile.action_target = 'PASS';
  report.mobile.no_overflow = 'PASS';
  await page.screenshot({ path: `${evidence}/04-providers-mobile-390.png`, fullPage: true, animations: 'disabled' });

  assert(report.page_errors.length === 0, `page errors ${JSON.stringify(report.page_errors)}`);
  assert(report.console_errors.length === 0, `console errors ${JSON.stringify(report.console_errors)}`);
  report.status = 'PASS';
} finally {
  fs.mkdirSync(evidence, { recursive: true });
  fs.writeFileSync(`${evidence}/P04_PROVIDER_DAILY_UX_REPORT.json`, JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}

if (report.status !== 'PASS') process.exit(1);
console.log('P04_PROVIDER_DAILY_UX_BROWSER=PASS');
