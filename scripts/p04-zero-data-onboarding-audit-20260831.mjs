import { chromium } from 'playwright';
import fs from 'node:fs';

const base = process.env.VF_E2E_BASE_URL || 'http://127.0.0.1:19078';
const evidence = process.env.EVIDENCE || '';
const source = process.env.SOURCE || '';
if (!evidence || !source) throw new Error('zero-data onboarding gate environment missing');
fs.mkdirSync(evidence, { recursive: true });

const password = 'Vf' + crypto.randomUUID().replaceAll('-', '') + 'Aa1';
const report = {
  schema: 'p04-zero-data-onboarding-gate/v2',
  source_sha: source,
  status: 'FAIL',
  views: {},
  findings: [],
  failures: [],
  page_errors: [],
  console_errors: [],
  fresh_install_zero_assets: true,
  synthetic_test_data_only: false,
  production_actions_executed: false,
};

const routes = {
  overview: { hash: '#overview', title: '先连接服务商账号' },
  domains: { hash: '#domains', title: '先从服务商同步域名' },
  servers: { hash: '#servers', title: '先从服务商同步服务器' },
};
const viewports = {
  desktop: { width: 1440, height: 900 },
  mobile: { width: 390, height: 844 },
};

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: viewports.desktop });
const page = await context.newPage();
page.on('pageerror', (e) => report.page_errors.push(String(e?.stack || e)));
page.on('console', (m) => { if (m.type() === 'error') report.console_errors.push(m.text()); });

function fail(message) {
  report.failures.push(message);
}

async function pointerClick(locator) {
  await locator.waitFor({ state: 'visible', timeout: 15000 });
  await locator.scrollIntoViewIfNeeded();
  await page.waitForTimeout(80);
  const box = await locator.boundingBox();
  if (!box || box.width <= 0 || box.height <= 0) throw new Error('pointer target has no visible box');
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.waitForTimeout(35);
  await page.mouse.up();
  return box;
}

async function installAndLogin() {
  await page.goto(`${base}/setup.php`, { waitUntil: 'domcontentloaded' });
  await page.locator('#site_name').fill('VF Infra Zero Data Onboarding Gate');
  await page.locator('#password').fill(password);
  await page.locator('#password_confirm').fill(password);
  await Promise.all([
    page.waitForURL(/login\.php\?installed=1/, { timeout: 30000 }),
    page.getByRole('button', { name: '安装并进入系统' }).click(),
  ]);
  await page.locator('#admin-password').fill(password);
  await Promise.all([
    page.waitForURL(/index\.php(?:#.*)?$/, { timeout: 30000 }),
    page.getByRole('button', { name: '登录' }).click(),
  ]);
  const version = await page.locator('meta[name="app-version"]').getAttribute('content');
  if (version !== '2.8.11') throw new Error(`version mismatch ${version}`);
}

async function go(hash) {
  await page.evaluate((target) => { location.hash = target; }, hash);
  await page.waitForFunction((target) => location.hash === target, hash, { timeout: 10000 });
  await page.waitForTimeout(450);
}

async function inspectProvider(viewportName) {
  const key = `${viewportName}:providers`;
  await go('#providers');
  await page.getByRole('heading', { name: '服务商', exact: true }).waitFor({ state: 'visible', timeout: 15000 });
  const injectedCount = await page.locator('[data-v2813-zero-onboarding]').count();
  const connect = page.locator('[data-v271-action="provider-connect"]').first();
  await connect.waitFor({ state: 'visible', timeout: 15000 });
  const box = await connect.boundingBox();
  const empty = page.locator('.v271-empty').filter({ hasText: '还没有连接账号。点击“连接新账号”开始。' }).first();
  const emptyVisible = await empty.isVisible().catch(() => false);
  const overflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth);
  const label = (await connect.textContent() || '').trim();
  report.views[key] = {
    hash: await page.evaluate(() => location.hash),
    injected_onboarding_count: injectedCount,
    connect_label: label,
    connect_size: { width: box?.width || 0, height: box?.height || 0 },
    empty_copy_visible: emptyVisible,
    overflow_x: overflow,
  };
  if (injectedCount !== 0) fail(`${key}: provider route must not receive duplicate onboarding`);
  if (label !== '连接新账号') fail(`${key}: missing real connect-account action`);
  if (!emptyVisible) fail(`${key}: mature provider empty-state copy missing`);
  if (viewportName === 'mobile' && (!box || box.height < 40)) fail(`${key}: connect action under 40px`);
  if (overflow > 1) fail(`${key}: horizontal overflow ${overflow}`);
  await page.screenshot({ path: `${evidence}/${viewportName}-providers-zero-data-gate.png`, fullPage: true, animations: 'disabled' });
}

async function inspectOnboardingRoute(routeName, def, viewportName) {
  const key = `${viewportName}:${routeName}`;
  await go(def.hash);
  const card = page.locator(`[data-v2813-zero-onboarding="${routeName}"]`);
  await card.waitFor({ state: 'visible', timeout: 15000 });
  const count = await page.locator('[data-v2813-zero-onboarding]').count();
  const heading = card.locator('h3').first();
  const headingText = (await heading.textContent() || '').trim();
  const button = card.locator('[data-v2813-onboarding-go="providers"]').first();
  await button.waitFor({ state: 'visible', timeout: 15000 });
  const buttonLabel = (await button.textContent() || '').trim();
  const aria = await button.getAttribute('aria-label');
  const box = await button.boundingBox();
  const overflowBefore = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth);

  report.views[key] = {
    hash_before: await page.evaluate(() => location.hash),
    onboarding_count: count,
    title: headingText,
    action_label: buttonLabel,
    action_aria: aria || '',
    action_size: { width: box?.width || 0, height: box?.height || 0 },
    overflow_before: overflowBefore,
    provider: {},
    onboarding_reappears_after_return: false,
  };

  if (count !== 1) fail(`${key}: expected exactly one onboarding card, got ${count}`);
  if (headingText !== def.title) fail(`${key}: wrong onboarding title ${headingText}`);
  if (!/服务商/.test(buttonLabel)) fail(`${key}: CTA does not clearly point to provider ${buttonLabel}`);
  if (!/服务商/.test(aria || '')) fail(`${key}: CTA aria does not explain provider destination`);
  if (viewportName === 'mobile' && (!box || box.height < 40)) fail(`${key}: onboarding action under 40px`);
  if (overflowBefore > 1) fail(`${key}: horizontal overflow ${overflowBefore}`);

  await page.screenshot({ path: `${evidence}/${viewportName}-${routeName}-zero-data-gate.png`, fullPage: true, animations: 'disabled' });

  await pointerClick(button);
  await page.waitForFunction(() => location.hash === '#providers', null, { timeout: 10000 });
  await page.waitForTimeout(450);
  const connect = page.locator('[data-v271-action="provider-connect"]').first();
  await connect.waitFor({ state: 'visible', timeout: 15000 });
  const connectBox = await connect.boundingBox();
  const providerInjected = await page.locator('[data-v2813-zero-onboarding]').count();
  const providerEmpty = await page.locator('.v271-empty').filter({ hasText: '还没有连接账号。点击“连接新账号”开始。' }).first().isVisible().catch(() => false);
  report.views[key].provider = {
    hash: await page.evaluate(() => location.hash),
    connect_label: (await connect.textContent() || '').trim(),
    connect_size: { width: connectBox?.width || 0, height: connectBox?.height || 0 },
    injected_onboarding_count: providerInjected,
    mature_empty_copy_visible: providerEmpty,
  };
  if (providerInjected !== 0) fail(`${key}: provider destination received duplicate onboarding`);
  if ((await connect.textContent() || '').trim() !== '连接新账号') fail(`${key}: destination lacks real connect action`);
  if (!providerEmpty) fail(`${key}: destination lacks mature provider empty copy`);
  if (viewportName === 'mobile' && (!connectBox || connectBox.height < 40)) fail(`${key}: provider connect target under 40px`);

  await go(def.hash);
  const returned = page.locator(`[data-v2813-zero-onboarding="${routeName}"]`);
  await returned.waitFor({ state: 'visible', timeout: 15000 });
  report.views[key].onboarding_reappears_after_return = true;
  const overflowAfter = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth);
  report.views[key].overflow_after_return = overflowAfter;
  if (overflowAfter > 1) fail(`${key}: overflow after return ${overflowAfter}`);
}

try {
  await installAndLogin();
  for (const [viewportName, viewport] of Object.entries(viewports)) {
    await page.setViewportSize(viewport);
    for (const [routeName, def] of Object.entries(routes)) {
      await inspectOnboardingRoute(routeName, def, viewportName);
    }
    await inspectProvider(viewportName);
  }
  if (report.page_errors.length) fail(`page errors: ${JSON.stringify(report.page_errors)}`);
  if (report.console_errors.length) fail(`console errors: ${JSON.stringify(report.console_errors)}`);
  report.status = report.failures.length === 0 ? 'PASS' : 'FAIL';
} catch (error) {
  fail(String(error?.stack || error));
  report.status = 'FAIL';
} finally {
  fs.writeFileSync(`${evidence}/P04_ZERO_DATA_ONBOARDING_AUDIT.json`, JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}

console.log(`P04_ZERO_DATA_ONBOARDING_GATE=${report.status}`);
if (report.failures.length) console.error(report.failures.join('\n'));
if (report.status !== 'PASS') process.exit(1);
