import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const base = process.env.VF_E2E_BASE_URL || 'http://127.0.0.1:19055';
const evidence = process.env.EVIDENCE;
const candidate = process.env.CANDIDATE;
const webRoot = process.env.WEB_ROOT;
const productRoot = process.env.PRODUCT_ROOT || path.join(process.cwd(), 'product');
if (!evidence || !candidate || !webRoot) throw new Error('detail technical-language gate environment missing');

const password = 'Vf' + crypto.randomUUID().replaceAll('-', '') + 'Aa1';
const report = {
  schema: 'p04-detail-technical-language-gate/v1',
  source_sha: candidate,
  status: 'FAIL',
  server: {},
  provider: {},
  mobile: {},
  page_errors: [],
  console_errors: [],
  production_actions_executed: false,
  synthetic_test_data_only: true,
};
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1365, height: 900 } });
const page = await context.newPage();
page.on('pageerror', (e) => report.page_errors.push(String(e?.stack || e)));
page.on('console', (m) => { if (m.type() === 'error') report.console_errors.push(m.text()); });
const assert = (value, message) => { if (!value) throw new Error(message); };
const visibleText = async () => (await page.locator('#v270-app').innerText()).replace(/\s+/g, ' ').trim();
const pageOverflow = async () => page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - window.innerWidth);

async function cold(hash) {
  await page.goto('about:blank');
  await page.goto(`${base}/index.php#${hash}`, { waitUntil: 'domcontentloaded' });
  await page.locator('#v270-app h1').waitFor({ state: 'visible', timeout: 15000 });
  await page.waitForTimeout(700);
}

function hasStandalone(text, token) {
  return new RegExp(`(^|\\s|[：:·|/])${token}(?=$|\\s|[：:·|/])`, 'i').test(text);
}

try {
  await page.goto(`${base}/setup.php`, { waitUntil: 'domcontentloaded' });
  await page.locator('#site_name').fill('VF Infra Detail Technical Language Gate');
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
  assert(fixture.includes('P04_V260_USER_TASK_FIXTURE_PASS'), 'fixture failed');

  // Server detail through the ordinary Current management pointer.
  await cold('servers');
  const serverAction = page.locator('table.server-table [data-v270-action="server"]').first();
  await serverAction.waitFor({ state: 'visible', timeout: 10000 });
  const serverId = await serverAction.getAttribute('data-id');
  assert(Boolean(serverId), 'server id missing');
  await serverAction.click();
  await page.waitForFunction((id) => location.hash === `#server/${encodeURIComponent(id)}`, serverId, { timeout: 10000 });
  await page.locator('.v270-ref-summary[data-ref-lock="server-summary"]').waitFor({ state: 'visible', timeout: 10000 });
  await page.waitForTimeout(500);
  const serverText = await visibleText();
  assert(!serverText.includes('Region / IP'), 'server still exposes Region / IP');
  assert(!serverText.includes('Provider 权威控制台'), 'server still exposes Provider authority wording');
  assert(serverText.includes('区域与 IP'), 'server human region/IP copy missing');
  assert(serverText.includes('服务商官方控制台'), 'server official-console copy missing');
  assert(serverText.includes('下一步'), 'server next-step copy missing');
  report.server.pointer_navigation = 'PASS';
  report.server.region_ip = 'PASS';
  report.server.official_console = 'PASS';
  await page.screenshot({ path: `${evidence}/01-server-detail-desktop.png`, fullPage: true, animations: 'disabled' });

  // Provider detail through the ordinary Current management pointer.
  await cold('providers');
  const providerAccount = page.locator('.v271-provider-account').filter({ hasText: 'V260 Linode 异常账号' }).first();
  await providerAccount.waitFor({ state: 'visible', timeout: 10000 });
  const providerAction = providerAccount.locator('[data-v271-action="provider-open"]');
  const providerId = await providerAction.getAttribute('data-id');
  assert(Boolean(providerId), 'provider id missing');
  await providerAction.click();
  await page.waitForFunction((id) => location.hash === `#provider/${encodeURIComponent(id)}`, providerId, { timeout: 10000 });
  await page.locator('.v271-provider-summary').waitFor({ state: 'visible', timeout: 10000 });
  await page.waitForTimeout(600);
  const providerText = await visibleText();
  assert(!/\bProvider\b/.test(providerText), `provider still exposes Provider: ${providerText}`);
  assert(!providerText.includes('compute_instance'), 'provider still exposes compute_instance');
  assert(!providerText.includes('Inventory / Billing'), 'provider still exposes Inventory / Billing');
  assert(!hasStandalone(providerText, 'high'), 'provider still exposes standalone high severity');
  assert(providerText.includes('服务商'), 'provider human service-provider copy missing');
  assert(providerText.includes('服务器'), 'provider human asset type missing');
  assert(providerText.includes('资产 / 费用'), 'provider human sync-result label missing');
  assert(providerText.includes('高风险'), 'provider human severity missing');
  assert(providerText.includes('API Token'), 'API Token must remain a meaningful technical term');
  assert(providerText.includes('下一步：'), 'provider next-step copy missing');
  report.provider.pointer_navigation = 'PASS';
  report.provider.provider_word = 'PASS';
  report.provider.asset_type = 'PASS';
  report.provider.sync_result = 'PASS';
  report.provider.severity = 'PASS';
  report.provider.api_token_preserved = 'PASS';
  await page.screenshot({ path: `${evidence}/02-provider-detail-desktop.png`, fullPage: true, animations: 'disabled' });

  // Mobile server detail.
  await page.setViewportSize({ width: 390, height: 844 });
  await cold(`server/${serverId}`);
  const mobileServerText = await visibleText();
  assert(!mobileServerText.includes('Region / IP') && !mobileServerText.includes('Provider 权威控制台'), 'mobile server technical copy remains');
  assert(mobileServerText.includes('区域与 IP') && mobileServerText.includes('服务商官方控制台'), 'mobile server human copy missing');
  assert((await pageOverflow()) <= 1, `mobile server overflow ${await pageOverflow()}`);
  report.mobile.server = 'PASS';
  await page.screenshot({ path: `${evidence}/03-server-detail-mobile-390.png`, fullPage: true, animations: 'disabled' });

  // Mobile provider detail.
  await cold(`provider/${providerId}`);
  const mobileProviderText = await visibleText();
  assert(!/\bProvider\b/.test(mobileProviderText), 'mobile provider still exposes Provider');
  assert(!mobileProviderText.includes('compute_instance') && !mobileProviderText.includes('Inventory / Billing'), 'mobile provider raw internal labels remain');
  assert(!hasStandalone(mobileProviderText, 'high'), 'mobile provider raw severity remains');
  assert(mobileProviderText.includes('服务商') && mobileProviderText.includes('服务器') && mobileProviderText.includes('资产 / 费用') && mobileProviderText.includes('高风险'), 'mobile provider human copy missing');
  assert(mobileProviderText.includes('API Token'), 'mobile provider lost API Token term');
  assert((await pageOverflow()) <= 1, `mobile provider overflow ${await pageOverflow()}`);
  report.mobile.provider = 'PASS';
  await page.screenshot({ path: `${evidence}/04-provider-detail-mobile-390.png`, fullPage: true, animations: 'disabled' });

  assert(report.page_errors.length === 0, `page errors ${JSON.stringify(report.page_errors)}`);
  assert(report.console_errors.length === 0, `console errors ${JSON.stringify(report.console_errors)}`);
  report.status = 'PASS';
} finally {
  fs.mkdirSync(evidence, { recursive: true });
  fs.writeFileSync(`${evidence}/P04_DETAIL_TECHNICAL_LANGUAGE_REPORT.json`, JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}

console.log(`P04_DETAIL_TECHNICAL_LANGUAGE_GATE=${report.status}`);
if (report.status !== 'PASS') process.exit(1);
