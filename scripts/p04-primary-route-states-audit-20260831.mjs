import { chromium } from 'playwright';
import fs from 'node:fs';

const base = process.env.VF_E2E_BASE_URL || 'http://127.0.0.1:19080';
const evidence = process.env.EVIDENCE || '';
const source = process.env.SOURCE || '';
if (!evidence || !source) throw new Error('primary route state audit environment missing');
fs.mkdirSync(evidence, { recursive: true });

const password = 'Vf' + crypto.randomUUID().replaceAll('-', '') + 'Aa1';
const faultMessage = 'Synthetic route state fault';
const viewports = { desktop: { width: 1440, height: 900 }, mobile: { width: 390, height: 844 } };
const routes = {
  overview: { owned: 'v270', heading: '个人基础设施概览', emptySelector: '[data-v2813-zero-onboarding="overview"]' },
  domains: { owned: 'v270', heading: '域名', emptySelector: '[data-v2813-zero-onboarding="domains"]' },
  servers: { owned: 'v270', heading: '服务器', emptySelector: '[data-v2813-zero-onboarding="servers"]' },
  providers: { owned: 'v271', heading: '服务商', emptySelector: '.v271-empty' },
  settings: { owned: 'v271', heading: '设置', emptySelector: '.v271-settings-layout' },
};
const report = {
  schema: 'p04-primary-route-states-audit/v1',
  source_sha: source,
  status: 'FAIL',
  synthetic_faults_only: true,
  synthetic_delays_only: true,
  real_user_data_used: false,
  external_provider_api_called: false,
  production_actions_executed: false,
  findings: [],
  failures: [],
  page_errors: [],
  console_errors: [],
  views: {},
};
const finding = (message) => { if (!report.findings.includes(message)) report.findings.push(message); };
const failure = (message) => report.failures.push(message);
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();

function targetRequest(urlString, routeName) {
  const url = new URL(urlString);
  if (['overview', 'domains', 'servers'].includes(routeName)) {
    return url.pathname.endsWith('/experience.php') && url.searchParams.get('view') === 'snapshot';
  }
  if (routeName === 'providers') {
    return url.pathname.endsWith('/api.php') && ['provider_workspace', 'provider_accounts'].includes(url.searchParams.get('action') || '');
  }
  if (routeName === 'settings') {
    return url.pathname.endsWith('/api.php') && (url.searchParams.get('action') || '') === 'settings';
  }
  return false;
}

const browser = await chromium.launch({ headless: true });
let storageState = null;

async function installAndLogin() {
  const context = await browser.newContext({ viewport: viewports.desktop });
  const page = await context.newPage();
  await page.goto(`${base}/setup.php`, { waitUntil: 'domcontentloaded' });
  await page.locator('#site_name').fill('VF Infra Primary Route State Audit');
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
  storageState = await context.storageState();
  await context.close();
}

async function openCase(viewName, routeName, mode) {
  const context = await browser.newContext({ viewport: viewports[viewName], storageState });
  const page = await context.newPage();
  const pageErrors = [];
  const consoleErrors = [];
  page.on('pageerror', (e) => pageErrors.push(String(e?.stack || e)));
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  if (mode !== 'empty') {
    await page.route('**/*', async (route) => {
      const request = route.request();
      if (request.method() !== 'GET' || !targetRequest(request.url(), routeName)) return route.continue();
      if (mode === 'loading') {
        await delay(1800);
        return route.continue();
      }
      return route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ ok: false, message: faultMessage }) });
    });
  }
  await page.goto(`${base}/index.php#${routeName}`, { waitUntil: 'domcontentloaded' });
  return { context, page, pageErrors, consoleErrors };
}

async function overflowX(page) {
  return page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth);
}
async function visibleText(page, selector) {
  const node = page.locator(selector).first();
  if (!await node.count()) return '';
  if (!await node.isVisible().catch(() => false)) return '';
  return clean(await node.textContent());
}
async function screenshot(page, name) {
  await page.screenshot({ path: `${evidence}/${name}.png`, fullPage: true, animations: 'disabled' });
}

async function emptyCase(viewName, routeName, spec) {
  const { context, page, pageErrors, consoleErrors } = await openCase(viewName, routeName, 'empty');
  const result = {};
  try {
    if (spec.owned === 'v271') {
      await page.locator(`[data-v271-route="${routeName}"]`).waitFor({ state: 'visible', timeout: 15000 });
    } else {
      await page.getByRole('heading', { name: spec.heading, exact: true }).waitFor({ state: 'visible', timeout: 15000 });
    }
    await page.waitForTimeout(450);
    result.heading = clean(await page.locator('#v270-app h1').first().textContent().catch(() => ''));
    result.overflow_x = await overflowX(page);
    result.empty_visible = await page.locator(spec.emptySelector).first().isVisible().catch(() => false);
    result.current_owner_marker = await page.locator(`[data-v271-route="${routeName}"]`).count() > 0;
    result.onboarding_count = await page.locator('[data-v2813-zero-onboarding]').count();
    result.recovery_or_start_actions = (await page.locator('#v270-app button, #v270-app a').allTextContents()).map(clean).filter(Boolean);
    if (routeName === 'providers') result.empty_copy = await visibleText(page, '.v271-empty');
    if (routeName === 'settings') result.settings_sections = await page.locator('.v271-settings-nav button').allTextContents();
    if (!result.empty_visible) finding(`${viewName}/${routeName}: empty/default state is missing its expected usable content`);
    if (result.overflow_x > 1) finding(`${viewName}/${routeName}: empty/default state horizontal overflow ${result.overflow_x}`);
    if (['overview','domains','servers'].includes(routeName)) {
      if (result.onboarding_count !== 1) finding(`${viewName}/${routeName}: expected exactly one first-step onboarding card, got ${result.onboarding_count}`);
      const cta = page.locator('[data-v2813-onboarding-go="providers"]').first();
      if (!await cta.isVisible().catch(() => false)) finding(`${viewName}/${routeName}: missing Provider onboarding CTA`);
      if (viewName === 'mobile' && await cta.count()) {
        const box = await cta.boundingBox();
        result.cta_height = box?.height || 0;
        if ((box?.height || 0) < 40) finding(`${viewName}/${routeName}: onboarding CTA below 40px`);
      }
    }
    if (routeName === 'providers') {
      if (!/还没有连接账号/.test(result.empty_copy || '')) finding(`${viewName}/providers: empty state does not explain that no account is connected`);
      const connect = page.locator('[data-v271-action="provider-connect"]').first();
      if (!await connect.isVisible().catch(() => false)) finding(`${viewName}/providers: empty state missing connect action`);
    }
    if (routeName === 'settings' && !result.current_owner_marker) finding(`${viewName}/settings: Current v271 settings owner did not take control`);
    await screenshot(page, `${viewName}-${routeName}-empty`);
  } finally {
    report.page_errors.push(...pageErrors.map((x) => `${viewName}/${routeName}/empty: ${x}`));
    report.console_errors.push(...consoleErrors.map((x) => `${viewName}/${routeName}/empty: ${x}`));
    await context.close();
  }
  return result;
}

async function loadingCase(viewName, routeName, spec) {
  const { context, page, pageErrors, consoleErrors } = await openCase(viewName, routeName, 'loading');
  const result = {};
  try {
    await page.waitForTimeout(300);
    const app = page.locator('#v270-app');
    const appText = clean(await app.textContent().catch(() => ''));
    const loadingText = await visibleText(page, '.v270-loading');
    result.early_app_text = appText.slice(0, 240);
    result.loading_visible = Boolean(loadingText) || /正在读取|加载|读取中/.test(appText);
    result.loading_text = loadingText;
    result.shell_nav_count = await page.locator('[data-v270-nav]').count();
    result.current_owner_marker_early = await page.locator(`[data-v271-route="${routeName}"]`).count() > 0;
    result.legacy_content_early = spec.owned === 'v271'
      && !result.current_owner_marker_early
      && !result.loading_visible
      && await page.locator('#v270-app .v270-section, #v270-app .v270-settings').count() > 0;
    result.overflow_x_early = await overflowX(page);
    if (!result.loading_visible && !result.legacy_content_early) finding(`${viewName}/${routeName}: loading state is blank or has no clear progress feedback`);
    if (result.shell_nav_count < 5) finding(`${viewName}/${routeName}: primary shell/nav disappeared during loading`);
    if (result.legacy_content_early) finding(`${viewName}/${routeName}: Current v271-owned route exposes retired v270 content while its data is loading`);
    if (result.overflow_x_early > 1) finding(`${viewName}/${routeName}: loading state horizontal overflow ${result.overflow_x_early}`);
    await screenshot(page, `${viewName}-${routeName}-loading`);
    if (spec.owned === 'v271') {
      await page.locator(`[data-v271-route="${routeName}"]`).waitFor({ state: 'visible', timeout: 10000 });
    } else {
      await page.getByRole('heading', { name: spec.heading, exact: true }).waitFor({ state: 'visible', timeout: 10000 });
    }
    result.resolved = true;
  } finally {
    report.page_errors.push(...pageErrors.map((x) => `${viewName}/${routeName}/loading: ${x}`));
    report.console_errors.push(...consoleErrors.map((x) => `${viewName}/${routeName}/loading: ${x}`));
    await context.close();
  }
  return result;
}

async function errorCase(viewName, routeName, spec) {
  const { context, page, pageErrors, consoleErrors } = await openCase(viewName, routeName, 'error');
  const result = {};
  try {
    if (spec.owned === 'v271') {
      await page.getByRole('heading', { name: '暂时无法读取', exact: true }).waitFor({ state: 'visible', timeout: 15000 });
    } else {
      await page.locator('.v270-error').waitFor({ state: 'visible', timeout: 15000 });
    }
    await page.waitForTimeout(150);
    result.app_text = clean(await page.locator('#v270-app').textContent());
    result.h1 = clean(await page.locator('#v270-app h1').first().textContent().catch(() => ''));
    result.error_visible = spec.owned === 'v271'
      ? await page.locator('.v271-help.danger').first().isVisible().catch(() => false)
      : await page.locator('.v270-error').first().isVisible().catch(() => false);
    const actionTexts = (await page.locator('#v270-app button, #v270-app a').allTextContents()).map(clean).filter(Boolean);
    result.actions = actionTexts;
    result.has_recovery_action = actionTexts.some((x) => /重新|重试|刷新|再试/.test(x));
    result.route_context_preserved = Boolean(result.h1);
    result.shell_nav_count = await page.locator('[data-v270-nav]').count();
    result.overflow_x = await overflowX(page);
    if (!result.error_visible || !result.app_text.includes(faultMessage)) failure(`${viewName}/${routeName}: synthetic error did not reach visible error state`);
    if (!result.route_context_preserved) finding(`${viewName}/${routeName}: error state drops the page/route heading context`);
    if (!result.has_recovery_action) finding(`${viewName}/${routeName}: error state has no visible retry/reload recovery action`);
    if (result.shell_nav_count < 5) finding(`${viewName}/${routeName}: shell/nav disappeared in error state`);
    if (result.overflow_x > 1) finding(`${viewName}/${routeName}: error state horizontal overflow ${result.overflow_x}`);
    await screenshot(page, `${viewName}-${routeName}-error`);
  } finally {
    report.page_errors.push(...pageErrors.map((x) => `${viewName}/${routeName}/error: ${x}`));
    report.console_errors.push(...consoleErrors.map((x) => `${viewName}/${routeName}/error: ${x}`));
    await context.close();
  }
  return result;
}

try {
  await installAndLogin();
  for (const [viewName] of Object.entries(viewports)) {
    report.views[viewName] = {};
    for (const [routeName, spec] of Object.entries(routes)) {
      report.views[viewName][routeName] = {
        empty: await emptyCase(viewName, routeName, spec),
        loading: await loadingCase(viewName, routeName, spec),
        error: await errorCase(viewName, routeName, spec),
      };
    }
  }
  if (report.page_errors.length) failure(`page errors: ${JSON.stringify(report.page_errors)}`);
  if (report.console_errors.length) failure(`console errors: ${JSON.stringify(report.console_errors)}`);
  report.status = report.failures.length === 0 && report.findings.length === 0 ? 'PASS' : 'FAIL';
} catch (error) {
  failure(String(error?.stack || error));
  report.status = 'FAIL';
} finally {
  fs.writeFileSync(`${evidence}/P04_PRIMARY_ROUTE_STATES_AUDIT.json`, JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}

console.log(`P04_PRIMARY_ROUTE_STATES_GATE=${report.status}`);
if (report.findings.length) console.error(`FINDINGS\n${report.findings.join('\n')}`);
if (report.failures.length) console.error(`FAILURES\n${report.failures.join('\n')}`);
if (report.status !== 'PASS') process.exit(1);
