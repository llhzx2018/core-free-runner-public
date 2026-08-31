import { chromium } from 'playwright';
import fs from 'node:fs';

const base = process.env.VF_E2E_BASE_URL || 'http://127.0.0.1:19080';
const evidence = process.env.EVIDENCE || '';
const source = process.env.SOURCE || '';
if (!evidence || !source) throw new Error('error recovery audit environment missing');
fs.mkdirSync(evidence, { recursive: true });

const password = 'Vf' + crypto.randomUUID().replaceAll('-', '') + 'Aa1';
const faultMessage = 'Synthetic route recovery fault';
const viewports = {
  desktop: { width: 1440, height: 900 },
  mobile: { width: 390, height: 844 },
};
const routes = {
  overview: { title: '个人基础设施概览', owner: 'v270', empty: '[data-v2813-zero-onboarding="overview"]' },
  domains: { title: '域名', owner: 'v270', empty: '[data-v2813-zero-onboarding="domains"]' },
  servers: { title: '服务器', owner: 'v270', empty: '[data-v2813-zero-onboarding="servers"]' },
  providers: { title: '服务商', owner: 'v271', empty: '.v271-empty' },
};
const report = {
  schema: 'p04-primary-route-error-recovery-audit/v1',
  source_sha: source,
  status: 'FAIL',
  synthetic_faults_only: true,
  real_user_data_used: false,
  external_provider_api_called: false,
  production_actions_executed: false,
  settings_error_boundary: 'N_A_CURRENT_ROUTE_NO_SEPARATE_SETTINGS_GET_OBSERVED',
  views: {},
  failures: [],
  page_errors: [],
  console_errors: [],
};
const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();
const fail = (message) => report.failures.push(message);

function isTarget(urlString, routeName) {
  const url = new URL(urlString);
  if (['overview', 'domains', 'servers'].includes(routeName)) {
    return url.pathname.endsWith('/experience.php') && url.searchParams.get('view') === 'snapshot';
  }
  return routeName === 'providers'
    && url.pathname.endsWith('/api.php')
    && url.searchParams.get('action') === 'provider_workspace';
}

function isExpectedSyntheticConsoleError(message) {
  const value = String(message || '');
  return /Failed to load resource/i.test(value) && /503/.test(value);
}

async function overflowX(page) {
  return page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth);
}

const browser = await chromium.launch({ headless: true });
let storageState;

async function installAndLogin() {
  const context = await browser.newContext({ viewport: viewports.desktop });
  const page = await context.newPage();
  await page.goto(`${base}/setup.php`, { waitUntil: 'domcontentloaded' });
  await page.locator('#site_name').fill('VF Infra Error Recovery Audit');
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
  if (version !== '2.8.11') throw new Error(`version mismatch: ${version}`);
  storageState = await context.storageState();
  await context.close();
}

async function runCase(viewName, routeName, spec) {
  const context = await browser.newContext({ viewport: viewports[viewName], storageState });
  const page = await context.newPage();
  const result = {
    route: routeName,
    owner: spec.owner,
    target_get_count: 0,
    post_count: 0,
    fault_injections: 0,
  };
  const pageErrors = [];
  const consoleErrors = [];
  page.on('pageerror', (error) => pageErrors.push(String(error?.stack || error)));
  page.on('console', (message) => {
    if (message.type() === 'error' && !isExpectedSyntheticConsoleError(message.text())) consoleErrors.push(message.text());
  });

  let faulted = false;
  await page.route('**/*', async (route) => {
    const request = route.request();
    if (request.method() === 'POST') result.post_count += 1;
    if (request.method() !== 'GET' || !isTarget(request.url(), routeName)) return route.continue();
    result.target_get_count += 1;
    if (!faulted) {
      faulted = true;
      result.fault_injections += 1;
      return route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({ ok: false, message: faultMessage }),
      });
    }
    return route.continue();
  });

  try {
    await page.goto(`${base}/index.php#${routeName}`, { waitUntil: 'domcontentloaded' });

    if (spec.owner === 'v270') {
      await page.locator(`[data-v2814-route-error="${routeName}"]`).waitFor({ state: 'visible', timeout: 15000 });
    } else {
      await page.locator(`[data-v271-route="${routeName}"][data-v2814-error-recovery="1"]`).waitFor({ state: 'visible', timeout: 15000 });
    }

    const retry = page.locator('[data-v2814-error-retry]').first();
    await retry.waitFor({ state: 'visible', timeout: 5000 });
    result.error_h1 = clean(await page.locator('#v270-app h1').first().textContent().catch(() => ''));
    result.error_text = clean(await page.locator('#v270-app').textContent()).slice(0, 900);
    result.hash_during_error = await page.evaluate(() => location.hash);
    result.shell_nav_count = await page.locator('[data-v270-nav]').count();
    result.overflow_error = await overflowX(page);
    const retryBox = await retry.boundingBox();
    result.retry_size = { width: retryBox?.width || 0, height: retryBox?.height || 0 };

    if (result.error_h1 !== spec.title) fail(`${viewName}/${routeName}: error h1 ${JSON.stringify(result.error_h1)} != ${JSON.stringify(spec.title)}`);
    if (!result.error_text.includes(faultMessage)) fail(`${viewName}/${routeName}: synthetic fault message not visible`);
    if (!result.error_text.includes('重新读取')) fail(`${viewName}/${routeName}: retry copy not visible`);
    if (result.hash_during_error !== `#${routeName}`) fail(`${viewName}/${routeName}: route hash changed during error: ${result.hash_during_error}`);
    if (result.shell_nav_count < 5) fail(`${viewName}/${routeName}: shell navigation disappeared during error`);
    if (result.overflow_error > 1) fail(`${viewName}/${routeName}: error horizontal overflow ${result.overflow_error}`);
    if (viewName === 'mobile' && (retryBox?.height || 0) < 40) fail(`${viewName}/${routeName}: retry action below 40px (${retryBox?.height || 0})`);

    await page.screenshot({ path: `${evidence}/${viewName}-${routeName}-error.png`, fullPage: true, animations: 'disabled' });

    await retry.click();
    result.retry_busy_seen = await page.locator('[data-v2814-error-loading]').isVisible().catch(() => false);

    if (spec.owner === 'v270') {
      await page.getByRole('heading', { name: spec.title, exact: true }).waitFor({ state: 'visible', timeout: 15000 });
      await page.locator(spec.empty).waitFor({ state: 'visible', timeout: 15000 });
    } else {
      await page.locator('[data-v271-route="providers"]').waitFor({ state: 'visible', timeout: 15000 });
      await page.locator(spec.empty).waitFor({ state: 'visible', timeout: 15000 });
      await page.locator('[data-v271-action="provider-connect"]').waitFor({ state: 'visible', timeout: 5000 });
    }
    await page.waitForTimeout(250);

    result.recovered_h1 = clean(await page.locator('#v270-app h1').first().textContent().catch(() => ''));
    result.hash_after_recovery = await page.evaluate(() => location.hash);
    result.retry_remaining = await page.locator('[data-v2814-error-retry]').count();
    result.error_remaining = await page.locator('[data-v2814-route-error], [data-v2814-error-recovery="1"]').count();
    result.onboarding_count = await page.locator('[data-v2813-zero-onboarding]').count();
    result.overflow_recovered = await overflowX(page);

    if (result.target_get_count < 2) fail(`${viewName}/${routeName}: retry did not issue a second target GET (${result.target_get_count})`);
    if (result.fault_injections !== 1) fail(`${viewName}/${routeName}: expected exactly one synthetic fault, got ${result.fault_injections}`);
    if (result.post_count !== 0) fail(`${viewName}/${routeName}: recovery path issued POST requests (${result.post_count})`);
    if (result.recovered_h1 !== spec.title) fail(`${viewName}/${routeName}: recovered h1 ${JSON.stringify(result.recovered_h1)} != ${JSON.stringify(spec.title)}`);
    if (result.hash_after_recovery !== `#${routeName}`) fail(`${viewName}/${routeName}: retry changed route hash to ${result.hash_after_recovery}`);
    if (result.retry_remaining !== 0 || result.error_remaining !== 0) fail(`${viewName}/${routeName}: error recovery UI remained after successful retry`);
    if (result.overflow_recovered > 1) fail(`${viewName}/${routeName}: recovered state horizontal overflow ${result.overflow_recovered}`);
    if (['overview', 'domains', 'servers'].includes(routeName) && result.onboarding_count !== 1) {
      fail(`${viewName}/${routeName}: expected one zero-data onboarding card after recovery, got ${result.onboarding_count}`);
    }
    if (routeName === 'providers' && result.onboarding_count !== 0) {
      fail(`${viewName}/providers: zero-data onboarding leaked into Provider owner after recovery`);
    }

    await page.screenshot({ path: `${evidence}/${viewName}-${routeName}-recovered.png`, fullPage: true, animations: 'disabled' });
  } catch (error) {
    fail(`${viewName}/${routeName}: ${String(error?.stack || error)}`);
  } finally {
    report.page_errors.push(...pageErrors.map((value) => `${viewName}/${routeName}: ${value}`));
    report.console_errors.push(...consoleErrors.map((value) => `${viewName}/${routeName}: ${value}`));
    await context.close();
  }
  return result;
}

try {
  await installAndLogin();
  for (const [viewName] of Object.entries(viewports)) {
    report.views[viewName] = {};
    for (const [routeName, spec] of Object.entries(routes)) {
      report.views[viewName][routeName] = await runCase(viewName, routeName, spec);
    }
  }
  if (report.page_errors.length) fail(`page errors: ${JSON.stringify(report.page_errors)}`);
  if (report.console_errors.length) fail(`console errors: ${JSON.stringify(report.console_errors)}`);
  report.status = report.failures.length === 0 ? 'PASS' : 'FAIL';
} catch (error) {
  fail(String(error?.stack || error));
  report.status = 'FAIL';
} finally {
  fs.writeFileSync(`${evidence}/P04_PRIMARY_ROUTE_ERROR_RECOVERY_AUDIT.json`, JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}

console.log(`P04_PRIMARY_ROUTE_ERROR_RECOVERY_GATE=${report.status}`);
if (report.failures.length) console.error(`FAILURES\n${report.failures.join('\n')}`);
if (report.status !== 'PASS') process.exit(1);
