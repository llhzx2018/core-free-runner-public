import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const base = process.env.VF_E2E_BASE_URL || 'http://127.0.0.1:19120';
const evidenceDir = process.env.EVIDENCE || '';
if (!evidenceDir) throw new Error('missing EVIDENCE');
fs.mkdirSync(evidenceDir, { recursive: true });
const password = 'Vf' + crypto.randomUUID().replaceAll('-', '') + 'Aa1';
const report = {
  gate: 'P04_V2812_FINAL_BROWSER_SMOKE',
  status: 'FAIL',
  version: null,
  routes: {},
  mobile: {},
  provider_modal: {},
  post_requests_after_login: 0,
  page_errors: [],
  console_errors: [],
  external_provider_api_called: false,
  production_actions_executed: false,
  real_user_data_used: false,
  failures: [],
};
const clean = (v) => String(v || '').replace(/\s+/g, ' ').trim();
const fail = (m) => report.failures.push(m);
const routes = {
  overview: { title: '个人基础设施概览', onboarding: true },
  domains: { title: '域名', onboarding: true },
  servers: { title: '服务器', onboarding: true },
  providers: { title: '服务商' },
  settings: { title: '设置' },
};
async function overflow(page) {
  return page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth);
}
async function visible(locator) { return locator.isVisible().catch(() => false); }
async function rect(locator) { const b = await locator.boundingBox(); return b ? { width:b.width, height:b.height } : null; }
async function route(page, name, title) {
  await page.evaluate((n) => { location.hash = `#${n}`; }, name);
  await page.waitForFunction((n) => location.hash === `#${n}`, name);
  await page.locator('#v270-app h1').filter({ hasText: title }).first().waitFor({ state:'visible', timeout:15000 });
  await page.waitForTimeout(250);
}

const browser = await chromium.launch({ headless:true });
const context = await browser.newContext({ viewport:{ width:1440, height:900 } });
const page = await context.newPage();
page.on('pageerror', e => report.page_errors.push(String(e?.stack || e)));
page.on('console', m => { if (m.type() === 'error') report.console_errors.push(m.text()); });
try {
  await page.goto(`${base}/setup.php`, { waitUntil:'domcontentloaded' });
  await page.locator('#site_name').fill('VF Infra V2.8.12 Final Gate');
  await page.locator('#password').fill(password);
  await page.locator('#password_confirm').fill(password);
  await Promise.all([
    page.waitForURL(/login\.php\?installed=1/, { timeout:30000 }),
    page.getByRole('button', { name:'安装并进入系统' }).click(),
  ]);
  await page.locator('#admin-password').fill(password);
  await Promise.all([
    page.waitForURL(/index\.php(?:#.*)?$/, { timeout:30000 }),
    page.getByRole('button', { name:'登录' }).click(),
  ]);
  report.version = await page.locator('meta[name="app-version"]').getAttribute('content');
  if (report.version !== '2.8.12') fail(`version=${report.version}`);
  page.on('request', r => { if (r.method() === 'POST') report.post_requests_after_login += 1; });

  const sideNav = page.locator('.v270-nav');
  const mobileNav = page.locator('.v270-mobile-nav');
  if (!await visible(sideNav)) fail('desktop sidebar missing');
  if (await visible(mobileNav)) fail('mobile nav leaked to desktop');
  for (const [name, spec] of Object.entries(routes)) {
    await route(page, name, spec.title);
    const h1 = clean(await page.locator('#v270-app h1').first().textContent());
    const result = {
      h1,
      hash: await page.evaluate(() => location.hash),
      overflow_x: await overflow(page),
      recovery_leak: await page.locator('[data-v2814-error-retry]').count(),
      current_v271_owner: await page.locator(`[data-v271-route="${name}"]`).count() > 0,
    };
    if (spec.onboarding) {
      const onboarding = page.locator(`[data-v2813-zero-onboarding="${name}"]`).first();
      const onboardingCta = onboarding.locator('[data-v2813-onboarding-go="providers"]').first();
      result.onboarding_visible = await visible(onboarding);
      result.onboarding_cta_visible = await visible(onboardingCta);
      result.onboarding_copy = clean(await onboarding.textContent().catch(() => ''));
      if (!result.onboarding_visible || !result.onboarding_cta_visible) fail(`${name}: stable onboarding marker/CTA missing`);
    }
    if (name === 'providers') {
      result.connect_visible = await visible(page.locator('[data-v271-action="provider-connect"]').first());
      if (!result.connect_visible) fail('providers: connect CTA missing');
    }
    if (name === 'settings' && !result.current_v271_owner) fail('settings: current v271 owner missing');
    if (h1 !== spec.title) fail(`${name}: h1=${h1}`);
    if (result.overflow_x > 1) fail(`${name}: desktop overflow ${result.overflow_x}`);
    if (result.recovery_leak) fail(`${name}: error recovery leaked into healthy state`);
    report.routes[name] = result;
    await page.screenshot({ path:path.join(evidenceDir, `desktop-${name}.png`), fullPage:true, animations:'disabled' });
  }

  // One stable navigation probe proves onboarding delegates to the existing Providers owner.
  await route(page, 'overview', '个人基础设施概览');
  const onboardingCta = page.locator('[data-v2813-zero-onboarding="overview"] [data-v2813-onboarding-go="providers"]').first();
  await onboardingCta.click();
  await page.waitForFunction(() => location.hash === '#providers');
  await page.locator('[data-v271-route="providers"]').waitFor({ state:'visible', timeout:15000 });
  report.routes.overview.onboarding_to_providers = true;

  await page.setViewportSize({ width:390, height:844 });
  for (const [name, spec] of Object.entries(routes)) {
    await route(page, name, spec.title);
    const ov = await overflow(page);
    report.mobile[name] = { overflow_x:ov };
    if (ov > 1) fail(`${name}: mobile overflow ${ov}`);
  }
  await route(page, 'providers', '服务商');
  const connect = page.locator('[data-v271-action="provider-connect"]').first();
  const connectRect = await rect(connect);
  await connect.click();
  const modal = page.locator('#v271-modal');
  await modal.waitFor({ state:'visible', timeout:5000 });
  const verify = page.getByRole('button', { name:'验证连接', exact:true });
  const submit = page.getByRole('button', { name:'连接并首次同步', exact:true });
  const close = page.getByRole('button', { name:'关闭', exact:true });
  report.provider_modal = {
    connect: connectRect,
    verify: await rect(verify),
    submit: await rect(submit),
    close: await rect(close),
    overflow_x: await overflow(page),
  };
  for (const [name, box] of Object.entries({ connect:report.provider_modal.connect, verify:report.provider_modal.verify, submit:report.provider_modal.submit, close:report.provider_modal.close })) {
    if ((box?.height || 0) < 40) fail(`mobile ${name} touch height ${box?.height || 0}`);
  }
  if (report.provider_modal.overflow_x > 1) fail(`provider modal mobile overflow ${report.provider_modal.overflow_x}`);
  await page.screenshot({ path:path.join(evidenceDir, 'mobile-provider-modal.png'), fullPage:true, animations:'disabled' });
  await close.click();

  if (report.post_requests_after_login !== 0) fail(`unexpected POST after login ${report.post_requests_after_login}`);
  if (report.page_errors.length) fail(`page errors ${JSON.stringify(report.page_errors)}`);
  if (report.console_errors.length) fail(`console errors ${JSON.stringify(report.console_errors)}`);
  report.status = report.failures.length ? 'FAIL' : 'PASS';
} catch (e) {
  fail(String(e?.stack || e));
  report.status = 'FAIL';
} finally {
  fs.writeFileSync(path.join(evidenceDir, 'browser-report.json'), JSON.stringify(report, null, 2) + '\n');
  await context.close();
  await browser.close();
}
console.log(`P04_V2812_FINAL_BROWSER_SMOKE=${report.status}`);
if (report.failures.length) console.error(report.failures.join('\n'));
if (report.status !== 'PASS') process.exit(1);
