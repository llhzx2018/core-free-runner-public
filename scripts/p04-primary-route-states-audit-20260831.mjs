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
  schema: 'p04-primary-route-states-audit/v2',
  source_sha: source,
  status: 'FAIL',
  synthetic_faults_only: true,
  synthetic_delays_only: true,
  real_user_data_used: false,
  external_provider_api_called: false,
  production_actions_executed: false,
  findings: [],
  harness_failures: [],
  page_errors: [],
  console_errors: [],
  expected_synthetic_console_errors: [],
  views: {},
};
const finding = (message) => { if (!report.findings.includes(message)) report.findings.push(message); };
const harnessFailure = (message) => report.harness_failures.push(message);
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

function recordDiagnostics(viewName, routeName, mode, pageErrors, consoleErrors) {
  report.page_errors.push(...pageErrors.map((x) => `${viewName}/${routeName}/${mode}: ${x}`));
  for (const x of consoleErrors) {
    const tagged = `${viewName}/${routeName}/${mode}: ${x}`;
    if (mode === 'error' && /503|Service Unavailable|Failed to load resource/i.test(x)) report.expected_synthetic_console_errors.push(tagged);
    else report.console_errors.push(tagged);
  }
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
    if (spec.owned === 'v271') await page.locator(`[data-v271-route="${routeName}"]`).waitFor({ state: 'visible', timeout: 15000 });
    else await page.getByRole('heading', { name: spec.heading, exact: true }).waitFor({ state: 'visible', timeout: 15000 });
    await page.waitForTimeout(450);
    result.heading = clean(await page.locator('#v270-app h1').first().textContent().catch(() => ''));
    result.overflow_x = await overflowX(page);
    result.empty_visible = await page.locator(spec.emptySelector).first().isVisible().catch(() => false);
    result.current_owner_marker = await page.locator(`[data-v271-route="${routeName}"]`).count() > 0;
    result.onboarding_count = await page.locator('[data-v2813-zero-onboarding]').count();
    result.recovery_or_start_actions = (await page.locator('#v270-app button, #v270-app a').allTextContents()).map(clean).filter(Boolean);
    if (routeName === 'providers') result.empty_copy = await visibleText(page, '.v271-empty');
    if (routeName === 'settings') result.settings_sections = (await page.locator('.v271-settings-nav button').allTextContents()).map(clean);
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
    recordDiagnostics(viewName, routeName, 'empty', pageErrors, consoleErrors);
    await context.close();
  }
  return result;
}

async function loadingSample(page, routeName, spec, atMs) {
  const app = page.locator('#v270-app');
  const appText = clean(await app.textContent().catch(() => ''));
  const loadingText = await visibleText(page, '.v270-loading');
  const marker = await page.locator(`[data-v271-route="${routeName}"]`).count() > 0;
  const legacyCount = spec.owned === 'v271' ? await page.locator('#v270-app .v270-section, #v270-app .v270-settings').count() : 0;
  return { at_ms: atMs, app_text: appText.slice(0, 300), loading_visible: Boolean(loadingText) || /正在读取|加载|读取中/.test(appText), current_owner_marker: marker, legacy_content_count: legacyCount, overflow_x: await overflowX(page) };
}

async function loadingCase(viewName, routeName, spec) {
  const { context, page, pageErrors, consoleErrors } = await openCase(viewName, routeName, 'loading');
  const result = { samples: [] };
  try {
    let elapsed = 0;
    for (const target of [120, 350, 800]) {
      await page.waitForTimeout(target - elapsed);
      elapsed = target;
      result.samples.push(await loadingSample(page, routeName, spec, target));
    }
    const probe = result.samples.find((x) => x.at_ms === 350) || result.samples[0];
    result.shell_nav_count = await page.locator('[data-v270-nav]').count();
    result.loading_visible_at_350 = Boolean(probe?.loading_visible);
    result.current_owner_marker_at_350 = Boolean(probe?.current_owner_marker);
    result.legacy_content_at_350 = spec.owned === 'v271' && !probe?.current_owner_marker && !probe?.loading_visible && Number(probe?.legacy_content_count || 0) > 0;
    result.blank_at_350 = !probe?.loading_visible && !probe?.current_owner_marker && Number(probe?.legacy_content_count || 0) === 0 && !clean(probe?.app_text);
    if (!probe?.loading_visible && !probe?.current_owner_marker) finding(`${viewName}/${routeName}: 350ms loading state has no Current owner/progress feedback`);
    if (result.legacy_content_at_350) finding(`${viewName}/${routeName}: Current v271-owned route exposes retired v270 content while its data is loading`);
    if (result.blank_at_350) finding(`${viewName}/${routeName}: loading state is blank at 350ms`);
    if (result.shell_nav_count < 5) finding(`${viewName}/${routeName}: primary shell/nav disappeared during loading`);
    if (result.samples.some((x) => x.overflow_x > 1)) finding(`${viewName}/${routeName}: loading state has horizontal overflow`);
    await screenshot(page, `${viewName}-${routeName}-loading`);
    if (spec.owned === 'v271') await page.locator(`[data-v271-route="${routeName}"]`).waitFor({ state: 'visible', timeout: 12000 });
    else await page.getByRole('heading', { name: spec.heading, exact: true }).waitFor({ state: 'visible', timeout: 12000 });
    result.resolved = true;
  } finally {
    recordDiagnostics(viewName, routeName, 'loading', pageErrors, consoleErrors);
    await context.close();
  }
  return result;
}

async function errorCase(viewName, routeName, spec) {
  const { context, page, pageErrors, consoleErrors } = await openCase(viewName, routeName, 'error');
  const result = {};
  try {
    await page.waitForFunction((fault) => (document.querySelector('#v270-app')?.textContent || '').includes(fault), faultMessage, { timeout: 15000 });
    await page.waitForTimeout(150);
    result.app_text = clean(await page.locator('#v270-app').textContent());
    result.h1 = clean(await page.locator('#v270-app h1').first().textContent().catch(() => ''));
    const v271Visible = await page.locator('.v271-help.danger').first().isVisible().catch(() => false);
    const v270Visible = await page.locator('.v270-error').first().isVisible().catch(() => false);
    result.error_owner = v271Visible ? 'v271' : (v270Visible ? 'v270' : 'unknown');
    result.error_visible = v271Visible || v270Visible;
    const actionTexts = (await page.locator('#v270-app button, #v270-app a').allTextContents()).map(clean).filter(Boolean);
    result.actions = actionTexts;
    result.has_recovery_action = actionTexts.some((x) => /重新|重试|刷新|再试/.test(x));
    result.route_context_preserved = Boolean(result.h1);
    result.shell_nav_count = await page.locator('[data-v270-nav]').count();
    result.overflow_x = await overflowX(page);
    if (!result.error_visible || !result.app_text.includes(faultMessage)) harnessFailure(`${viewName}/${routeName}: synthetic error did not reach an observable error owner`);
    if (spec.owned === 'v271' && result.error_owner !== 'v271') finding(`${viewName}/${routeName}: Current v271 route error fell back to ${result.error_owner} owner`);
    if (!result.route_context_preserved) finding(`${viewName}/${routeName}: error state drops the page/route heading context`);
    if (!result.has_recovery_action) finding(`${viewName}/${routeName}: error state has no visible retry/reload recovery action`);
    if (result.shell_nav_count < 5) finding(`${viewName}/${routeName}: shell/nav disappeared in error state`);
    if (result.overflow_x > 1) finding(`${viewName}/${routeName}: error state horizontal overflow ${result.overflow_x}`);
    await screenshot(page, `${viewName}-${routeName}-error`);
  } finally {
    recordDiagnostics(viewName, routeName, 'error', pageErrors, consoleErrors);
    await context.close();
  }
  return result;
}

async function runCase(viewName, routeName, mode, fn) {
  try { return await fn(); }
  catch (error) { harnessFailure(`${viewName}/${routeName}/${mode}: ${String(error?.stack || error)}`); return { harness_error: String(error?.message || error) }; }
}

try {
  await installAndLogin();
  for (const [viewName] of Object.entries(viewports)) {
    report.views[viewName] = {};
    for (const [routeName, spec] of Object.entries(routes)) {
      report.views[viewName][routeName] = {};
      report.views[viewName][routeName].empty = await runCase(viewName, routeName, 'empty', () => emptyCase(viewName, routeName, spec));
      report.views[viewName][routeName].loading = await runCase(viewName, routeName, 'loading', () => loadingCase(viewName, routeName, spec));
      report.views[viewName][routeName].error = await runCase(viewName, routeName, 'error', () => errorCase(viewName, routeName, spec));
    }
  }
  if (report.page_errors.length) harnessFailure(`page errors: ${JSON.stringify(report.page_errors)}`);
  if (report.console_errors.length) harnessFailure(`unexpected console errors: ${JSON.stringify(report.console_errors)}`);
  report.status = report.harness_failures.length === 0 && report.findings.length === 0 ? 'PASS' : 'FAIL';
} catch (error) {
  harnessFailure(String(error?.stack || error));
  report.status = 'FAIL';
} finally {
  fs.writeFileSync(`${evidence}/P04_PRIMARY_ROUTE_STATES_AUDIT.json`, JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}

console.log(`P04_PRIMARY_ROUTE_STATES_GATE=${report.status}`);
if (report.findings.length) console.error(`FINDINGS\n${report.findings.join('\n')}`);
if (report.harness_failures.length) console.error(`HARNESS_FAILURES\n${report.harness_failures.join('\n')}`);
if (report.status !== 'PASS') process.exit(1);
