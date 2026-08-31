import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';

const base = process.env.VF_E2E_BASE_URL || 'http://127.0.0.1:19079';
const evidence = process.env.EVIDENCE || '';
const source = process.env.SOURCE || '';
const web = process.env.WEB || '';
const seedHelper = process.env.SEED_HELPER || '';
if (!evidence || !source || !web || !seedHelper) throw new Error('connected-data transition gate environment missing');
fs.mkdirSync(evidence, { recursive: true });

const password = 'Vf' + crypto.randomUUID().replaceAll('-', '') + 'Aa1';
const report = {
  schema: 'p04-connected-data-transition-gate/v1',
  source_sha: source,
  status: 'FAIL',
  synthetic_test_data_only: true,
  external_provider_api_called: false,
  production_actions_executed: false,
  initial_zero_data: {},
  connected_data: {},
  transition: {},
  seed: null,
  failures: [],
  page_errors: [],
  console_errors: [],
};

const routes = {
  overview: '#overview',
  domains: '#domains',
  servers: '#servers',
};
const viewports = {
  desktop: { width: 1440, height: 900 },
  mobile: { width: 390, height: 844 },
};

function fail(message) { report.failures.push(message); }

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: viewports.desktop });
const page = await context.newPage();
page.on('pageerror', (e) => report.page_errors.push(String(e?.stack || e)));
page.on('console', (m) => { if (m.type() === 'error') report.console_errors.push(m.text()); });

async function installAndLogin() {
  await page.goto(`${base}/setup.php`, { waitUntil: 'domcontentloaded' });
  await page.locator('#site_name').fill('VF Infra Connected Data Transition Gate');
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
  await page.waitForTimeout(500);
}

async function overflowX() {
  return page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth);
}

async function inspectInitialZero(viewportName) {
  for (const [routeName, hash] of Object.entries(routes)) {
    await go(hash);
    const count = await page.locator('[data-v2813-zero-onboarding]').count();
    const routeCard = await page.locator(`[data-v2813-zero-onboarding="${routeName}"]`).count();
    const overflow = await overflowX();
    report.initial_zero_data[`${viewportName}:${routeName}`] = { onboarding_count: count, route_card_count: routeCard, overflow_x: overflow };
    if (count !== 1 || routeCard !== 1) fail(`${viewportName}:${routeName}: initial zero-data onboarding must be exactly one`);
    if (overflow > 1) fail(`${viewportName}:${routeName}: initial horizontal overflow ${overflow}`);
  }
  await go('#providers');
  const providerInjected = await page.locator('[data-v2813-zero-onboarding]').count();
  const connect = page.locator('[data-v271-action="provider-connect"]').first();
  await connect.waitFor({ state: 'visible', timeout: 15000 });
  const connectBox = await connect.boundingBox();
  const providerOverflow = await overflowX();
  report.initial_zero_data[`${viewportName}:providers`] = {
    injected_onboarding_count: providerInjected,
    connect_label: (await connect.textContent() || '').trim(),
    connect_height: connectBox?.height || 0,
    overflow_x: providerOverflow,
  };
  if (providerInjected !== 0) fail(`${viewportName}:providers: Current owner received duplicate initial onboarding`);
  if ((await connect.textContent() || '').trim() !== '连接新账号') fail(`${viewportName}:providers: Current connect owner missing before transition`);
  if (viewportName === 'mobile' && (!connectBox || connectBox.height < 40)) fail(`${viewportName}:providers: connect action under 40px before transition`);
  if (providerOverflow > 1) fail(`${viewportName}:providers: initial horizontal overflow ${providerOverflow}`);
}

function seedSyntheticData() {
  const output = execFileSync('php', [seedHelper, web], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).trim();
  const seed = JSON.parse(output);
  report.seed = seed;
  if (seed.status !== 'PASS' || seed.synthetic_only !== true || seed.external_provider_api_called !== false) {
    throw new Error(`synthetic seed contract failed: ${output}`);
  }
}

async function assertNoOnboarding(routeName, viewportName) {
  const count = await page.locator('[data-v2813-zero-onboarding]').count();
  if (count !== 0) fail(`${viewportName}:${routeName}: stale/duplicate onboarding remains after connected data (${count})`);
  return count;
}

async function inspectConnected(viewportName) {
  await go('#overview');
  const overviewOnboarding = await assertNoOnboarding('overview', viewportName);
  const overviewDomain = await page.getByText('transition.example', { exact: true }).count();
  const overviewServer = await page.getByText('vf-transition-server', { exact: true }).count();
  const overviewOverflow = await overflowX();
  report.connected_data[`${viewportName}:overview`] = { onboarding_count: overviewOnboarding, domain_mentions: overviewDomain, server_mentions: overviewServer, overflow_x: overviewOverflow };
  if (overviewDomain + overviewServer < 1) fail(`${viewportName}:overview: connected resource not rendered`);
  if (overviewOverflow > 1) fail(`${viewportName}:overview: horizontal overflow ${overviewOverflow}`);
  await page.screenshot({ path: `${evidence}/${viewportName}-overview-connected.png`, fullPage: true, animations: 'disabled' });

  await go('#domains');
  const domainsOnboarding = await assertNoOnboarding('domains', viewportName);
  const domainRow = page.locator('table.domain-table [data-v270-action="domain"]').first();
  await domainRow.waitFor({ state: 'attached', timeout: 15000 });
  const domainVisible = await page.getByText('transition.example', { exact: true }).count();
  const domainsOverflow = await overflowX();
  report.connected_data[`${viewportName}:domains`] = { onboarding_count: domainsOnboarding, domain_mentions: domainVisible, owner_action_count: await page.locator('[data-v270-action="domain"]').count(), overflow_x: domainsOverflow };
  if (domainVisible < 1) fail(`${viewportName}:domains: synthetic domain not rendered`);
  if (domainsOverflow > 1) fail(`${viewportName}:domains: horizontal overflow ${domainsOverflow}`);
  await page.screenshot({ path: `${evidence}/${viewportName}-domains-connected.png`, fullPage: true, animations: 'disabled' });

  await go('#servers');
  const serversOnboarding = await assertNoOnboarding('servers', viewportName);
  const serverAction = page.locator('table.server-table [data-v270-action="server"]').first();
  await serverAction.waitFor({ state: 'attached', timeout: 15000 });
  const serverVisible = await page.getByText('vf-transition-server', { exact: true }).count();
  const serversOverflow = await overflowX();
  report.connected_data[`${viewportName}:servers`] = { onboarding_count: serversOnboarding, server_mentions: serverVisible, owner_action_count: await page.locator('[data-v270-action="server"]').count(), overflow_x: serversOverflow };
  if (serverVisible < 1) fail(`${viewportName}:servers: synthetic server not rendered`);
  if (serversOverflow > 1) fail(`${viewportName}:servers: horizontal overflow ${serversOverflow}`);
  await page.screenshot({ path: `${evidence}/${viewportName}-servers-connected.png`, fullPage: true, animations: 'disabled' });

  await go('#providers');
  const providerOnboarding = await assertNoOnboarding('providers', viewportName);
  const connect = page.locator('[data-v271-action="provider-connect"]').first();
  await connect.waitFor({ state: 'visible', timeout: 15000 });
  const connectBox = await connect.boundingBox();
  const accountVisible = await page.getByText('Fresh Synthetic Account', { exact: true }).count();
  const providersOverflow = await overflowX();
  report.connected_data[`${viewportName}:providers`] = {
    onboarding_count: providerOnboarding,
    account_mentions: accountVisible,
    connect_label: (await connect.textContent() || '').trim(),
    connect_height: connectBox?.height || 0,
    overflow_x: providersOverflow,
  };
  if (accountVisible < 1) fail(`${viewportName}:providers: synthetic connected account not rendered`);
  if ((await connect.textContent() || '').trim() !== '连接新账号') fail(`${viewportName}:providers: Current connect owner broken after transition`);
  if (viewportName === 'mobile' && (!connectBox || connectBox.height < 40)) fail(`${viewportName}:providers: connect action under 40px after transition`);
  if (providersOverflow > 1) fail(`${viewportName}:providers: horizontal overflow ${providersOverflow}`);
  await page.screenshot({ path: `${evidence}/${viewportName}-providers-connected.png`, fullPage: true, animations: 'disabled' });

  const sequence = ['#overview', '#domains', '#servers', '#providers', '#overview', '#domains', '#servers'];
  let staleCount = 0;
  for (const hash of sequence) {
    await go(hash);
    staleCount += await page.locator('[data-v2813-zero-onboarding]').count();
  }
  report.transition[viewportName] = { repeated_route_stale_onboarding_total: staleCount };
  if (staleCount !== 0) fail(`${viewportName}: repeated connected-route navigation recreated stale onboarding (${staleCount})`);
}

try {
  await installAndLogin();

  for (const [viewportName, viewport] of Object.entries(viewports)) {
    await page.setViewportSize(viewport);
    await inspectInitialZero(viewportName);
  }

  seedSyntheticData();
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(700);

  for (const [viewportName, viewport] of Object.entries(viewports)) {
    await page.setViewportSize(viewport);
    await inspectConnected(viewportName);
  }

  if (report.page_errors.length) fail(`page errors: ${JSON.stringify(report.page_errors)}`);
  if (report.console_errors.length) fail(`console errors: ${JSON.stringify(report.console_errors)}`);
  report.status = report.failures.length === 0 ? 'PASS' : 'FAIL';
} catch (error) {
  fail(String(error?.stack || error));
  report.status = 'FAIL';
} finally {
  fs.writeFileSync(`${evidence}/P04_CONNECTED_DATA_TRANSITION_AUDIT.json`, JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}

console.log(`P04_CONNECTED_DATA_TRANSITION_GATE=${report.status}`);
if (report.failures.length) console.error(report.failures.join('\n'));
if (report.status !== 'PASS') process.exit(1);
