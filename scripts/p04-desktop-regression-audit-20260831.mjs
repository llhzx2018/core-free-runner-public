import { chromium } from 'playwright';
import fs from 'node:fs';

const base = process.env.VF_E2E_BASE_URL || 'http://127.0.0.1:19080';
const evidence = process.env.EVIDENCE || '';
const source = process.env.SOURCE || '';
if (!evidence || !source) throw new Error('desktop regression audit environment missing');
fs.mkdirSync(evidence, { recursive: true });

const password = 'Vf' + crypto.randomUUID().replaceAll('-', '') + 'Aa1';
const report = {
  schema: 'p04-desktop-regression-audit/v1',
  source_sha: source,
  status: 'FAIL',
  viewport: { width: 1440, height: 900 },
  real_user_data_used: false,
  external_provider_api_called: false,
  production_actions_executed: false,
  post_requests_after_login: 0,
  routes: {},
  provider_modal: {},
  shell: {},
  failures: [],
  page_errors: [],
  console_errors: [],
};
const routeSpecs = {
  overview: { title: '个人基础设施概览', owner: 'v270', onboarding: 1 },
  domains: { title: '域名', owner: 'v270', onboarding: 1, desktopTable: true },
  servers: { title: '服务器', owner: 'v270', onboarding: 1, desktopTable: true },
  providers: { title: '服务商', owner: 'v271', onboarding: 0 },
  settings: { title: '设置', owner: 'v271', onboarding: 0 },
};
const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();
const fail = (message) => report.failures.push(message);

async function overflowX(page) {
  return page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth);
}
async function visible(locator) {
  return locator.isVisible().catch(() => false);
}
async function rect(locator) {
  const box = await locator.boundingBox();
  return box ? { width: box.width, height: box.height, x: box.x, y: box.y } : null;
}

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: report.viewport });
const page = await context.newPage();
page.on('pageerror', (error) => report.page_errors.push(String(error?.stack || error)));
page.on('console', (message) => { if (message.type() === 'error') report.console_errors.push(message.text()); });

try {
  await page.goto(`${base}/setup.php`, { waitUntil: 'domcontentloaded' });
  await page.locator('#site_name').fill('VF Infra Desktop Regression Audit');
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
  if (version !== '2.8.11') fail(`version mismatch: ${version}`);

  page.on('request', (request) => {
    if (request.method() === 'POST') report.post_requests_after_login += 1;
  });

  const sideNav = page.locator('.v270-nav');
  const mobileNav = page.locator('.v270-mobile-nav');
  const topbar = page.locator('.v270-topbar');
  const searchInput = page.locator('#v270-search-input');
  const searchButton = page.locator('#v270-search-form button[type="submit"]');
  report.shell = {
    side_nav_visible: await visible(sideNav),
    mobile_nav_visible: await visible(mobileNav),
    topbar_visible: await visible(topbar),
    search_visible: await visible(searchInput),
    side_nav_rect: await rect(sideNav),
    search_button_rect: await rect(searchButton),
    overflow_x: await overflowX(page),
  };
  if (!report.shell.side_nav_visible) fail('desktop sidebar navigation is not visible');
  if (report.shell.mobile_nav_visible) fail('mobile primary navigation leaked into 1440px desktop');
  if (!report.shell.topbar_visible || !report.shell.search_visible) fail('desktop topbar/search shell is missing');
  if (report.shell.overflow_x > 1) fail(`desktop shell horizontal overflow ${report.shell.overflow_x}`);
  if ((report.shell.side_nav_rect?.width || 0) < 180) fail(`desktop sidebar collapsed unexpectedly (${report.shell.side_nav_rect?.width || 0}px)`);

  for (const [routeName, spec] of Object.entries(routeSpecs)) {
    const nav = page.locator(`.v270-nav [data-v270-nav="${routeName}"]`).first();
    await nav.click();
    await page.waitForFunction((name) => location.hash === `#${name}`, routeName);

    if (spec.owner === 'v271') {
      await page.locator(`[data-v271-route="${routeName}"]`).waitFor({ state: 'visible', timeout: 15000 });
    } else {
      await page.getByRole('heading', { name: spec.title, exact: true }).waitFor({ state: 'visible', timeout: 15000 });
    }
    await page.waitForTimeout(250);

    const h1 = clean(await page.locator('#v270-app h1').first().textContent().catch(() => ''));
    const routeResult = {
      h1,
      hash: await page.evaluate(() => location.hash),
      overflow_x: await overflowX(page),
      side_nav_visible: await visible(sideNav),
      mobile_nav_visible: await visible(mobileNav),
      error_visible: await page.locator('.v270-error:visible, .v271-help.danger:visible').count() > 0,
      recovery_ui_count: await page.locator('[data-v2814-route-error], [data-v2814-error-recovery="1"], [data-v2814-error-retry]').count(),
      onboarding_count: await page.locator('[data-v2813-zero-onboarding]').count(),
      current_v271_owner: await page.locator(`[data-v271-route="${routeName}"]`).count() > 0,
    };

    if (spec.desktopTable) {
      routeResult.desktop_table_visible = await visible(page.locator('#v270-app .v270-desktop-table').first());
      routeResult.mobile_cards_visible = await visible(page.locator('#v270-app .v270-mobile-cards').first());
    }
    if (routeName === 'providers') {
      routeResult.empty_visible = await visible(page.locator('.v271-empty'));
      routeResult.connect_visible = await visible(page.locator('[data-v271-action="provider-connect"]'));
    }
    if (routeName === 'settings') {
      routeResult.settings_layout_visible = await visible(page.locator('.v271-settings-layout'));
    }

    report.routes[routeName] = routeResult;
    if (h1 !== spec.title) fail(`${routeName}: desktop h1 ${JSON.stringify(h1)} != ${JSON.stringify(spec.title)}`);
    if (routeResult.hash !== `#${routeName}`) fail(`${routeName}: route hash mismatch ${routeResult.hash}`);
    if (routeResult.overflow_x > 1) fail(`${routeName}: desktop horizontal overflow ${routeResult.overflow_x}`);
    if (!routeResult.side_nav_visible || routeResult.mobile_nav_visible) fail(`${routeName}: desktop/mobile nav visibility regressed`);
    if (routeResult.error_visible) fail(`${routeName}: healthy desktop route shows an error state`);
    if (routeResult.recovery_ui_count !== 0) fail(`${routeName}: error-recovery overlay leaked into healthy desktop state`);
    if (routeResult.onboarding_count !== spec.onboarding) fail(`${routeName}: onboarding count ${routeResult.onboarding_count} != ${spec.onboarding}`);
    if (spec.owner === 'v271' && !routeResult.current_v271_owner) fail(`${routeName}: Current v271 owner marker missing`);
    if (spec.desktopTable && !routeResult.desktop_table_visible) fail(`${routeName}: desktop table is not visible at 1440px`);
    if (spec.desktopTable && routeResult.mobile_cards_visible) fail(`${routeName}: mobile cards leaked into 1440px desktop`);
    if (routeName === 'providers' && (!routeResult.empty_visible || !routeResult.connect_visible)) fail('providers: zero-data desktop owner/CTA missing');
    if (routeName === 'settings' && !routeResult.settings_layout_visible) fail('settings: unified desktop layout missing');

    await page.screenshot({ path: `${evidence}/desktop-${routeName}.png`, fullPage: true, animations: 'disabled' });
  }

  // Verify the recent mobile-only Provider modal touch floor does not inflate desktop controls.
  await page.locator('.v270-nav [data-v270-nav="providers"]').first().click();
  await page.locator('[data-v271-route="providers"]').waitFor({ state: 'visible', timeout: 15000 });
  const connect = page.locator('[data-v271-action="provider-connect"]').first();
  await connect.click();
  const modal = page.locator('#v271-modal');
  await modal.waitFor({ state: 'visible', timeout: 5000 });
  const verify = page.getByRole('button', { name: '验证连接', exact: true });
  const submit = page.getByRole('button', { name: '连接并首次同步', exact: true });
  const close = page.getByRole('button', { name: '关闭', exact: true });
  report.provider_modal = {
    visible: await visible(modal),
    verify: await rect(verify),
    submit: await rect(submit),
    close: await rect(close),
    overflow_x: await overflowX(page),
  };
  for (const [name, box] of Object.entries({ verify: report.provider_modal.verify, submit: report.provider_modal.submit, close: report.provider_modal.close })) {
    const height = box?.height || 0;
    if (height < 36 || height >= 40) fail(`provider modal ${name}: desktop height should remain below mobile 40px floor, got ${height}`);
  }
  if (report.provider_modal.overflow_x > 1) fail(`provider modal: desktop horizontal overflow ${report.provider_modal.overflow_x}`);
  await page.screenshot({ path: `${evidence}/desktop-provider-connect-modal.png`, fullPage: true, animations: 'disabled' });
  await close.click();

  // Search shell smoke: search should stay desktop and remain usable without any write action.
  await searchInput.fill('not-a-real-infrastructure-item');
  await searchButton.click();
  await page.waitForFunction(() => location.hash.startsWith('#search/'));
  await page.waitForTimeout(300);
  report.shell.search_result_h1 = clean(await page.locator('#v270-app h1').first().textContent().catch(() => ''));
  report.shell.search_overflow_x = await overflowX(page);
  report.shell.mobile_nav_visible_after_search = await visible(mobileNav);
  if (!report.shell.search_result_h1.startsWith('搜索：')) fail(`desktop search result heading missing: ${report.shell.search_result_h1}`);
  if (report.shell.search_overflow_x > 1) fail(`desktop search horizontal overflow ${report.shell.search_overflow_x}`);
  if (report.shell.mobile_nav_visible_after_search) fail('mobile navigation leaked into desktop search state');
  await page.screenshot({ path: `${evidence}/desktop-search.png`, fullPage: true, animations: 'disabled' });

  if (report.post_requests_after_login !== 0) fail(`desktop audit issued POST requests after login: ${report.post_requests_after_login}`);
  if (report.page_errors.length) fail(`page errors: ${JSON.stringify(report.page_errors)}`);
  if (report.console_errors.length) fail(`console errors: ${JSON.stringify(report.console_errors)}`);
  report.status = report.failures.length === 0 ? 'PASS' : 'FAIL';
} catch (error) {
  fail(String(error?.stack || error));
  report.status = 'FAIL';
} finally {
  fs.writeFileSync(`${evidence}/P04_DESKTOP_REGRESSION_AUDIT.json`, JSON.stringify(report, null, 2) + '\n');
  await context.close();
  await browser.close();
}

console.log(`P04_DESKTOP_REGRESSION_GATE=${report.status}`);
if (report.failures.length) console.error(`FAILURES\n${report.failures.join('\n')}`);
if (report.status !== 'PASS') process.exit(1);
