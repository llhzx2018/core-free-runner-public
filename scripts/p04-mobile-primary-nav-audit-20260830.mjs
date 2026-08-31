import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const base = process.env.VF_E2E_BASE_URL || 'http://127.0.0.1:19063';
const evidence = process.env.EVIDENCE;
const candidate = process.env.CANDIDATE;
const webRoot = process.env.WEB_ROOT;
const productRoot = process.env.PRODUCT_ROOT || path.join(process.cwd(), 'product');
if (!evidence || !candidate || !webRoot) throw new Error('mobile primary nav audit environment missing');
fs.mkdirSync(evidence, { recursive: true });

const password = 'Vf' + crypto.randomUUID().replaceAll('-', '') + 'Aa1';
const report = {
  schema: 'p04-mobile-primary-nav-audit/v1',
  source_sha: candidate,
  status: 'FAIL',
  routes: {},
  nav: {},
  page_errors: [],
  console_errors: [],
  synthetic_test_data_only: true,
  production_actions_executed: false,
};

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
const page = await context.newPage();
page.on('pageerror', (e) => report.page_errors.push(String(e?.stack || e)));
page.on('console', (m) => { if (m.type() === 'error') report.console_errors.push(m.text()); });
const clean = (v) => String(v || '').replace(/\s+/g, ' ').trim();
const assert = (v, m) => { if (!v) throw new Error(m); };

async function pointerClick(locator) {
  await locator.waitFor({ state: 'visible', timeout: 12000 });
  await locator.scrollIntoViewIfNeeded();
  await page.waitForTimeout(60);
  const box = await locator.boundingBox();
  if (!box || box.width <= 0 || box.height <= 0) throw new Error('nav target has no box');
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.waitForTimeout(35);
  await page.mouse.up();
}

const specs = [
  ['overview', '概览', '个人基础设施概览'],
  ['domains', '域名', '域名'],
  ['servers', '服务器', '服务器'],
  ['providers', '服务商', '服务商'],
  ['settings', '设置', '设置'],
];

async function waitRoute(route, expectedH1) {
  await page.waitForFunction((r) => (location.hash || '#overview') === `#${r}`, route, { timeout: 12000 });
  const h1 = page.locator('#v270-app h1').first();
  await h1.waitFor({ state: 'visible', timeout: 15000 });
  await page.waitForFunction(([selector, text]) => {
    const node = document.querySelector(selector);
    return Boolean(node && (node.textContent || '').trim().includes(text));
  }, ['#v270-app h1', expectedH1], { timeout: 15000 });
  await page.waitForTimeout(180);
}

async function inspect(route, expectedH1) {
  const mobile = page.locator(`.v270-mobile-nav [data-v270-nav="${route}"]`);
  const box = await mobile.boundingBox();
  const active = await mobile.getAttribute('aria-current');
  const activeCount = await page.locator('.v270-mobile-nav [data-v270-nav][aria-current="page"]').count();
  const h1 = clean(await page.locator('#v270-app h1').first().innerText());
  const overflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth);
  const navOverflow = await page.locator('.v270-mobile-nav').evaluate((node) => node.scrollWidth - node.clientWidth);
  const navRect = await page.locator('.v270-mobile-nav').boundingBox();
  report.routes[route] = {
    h1,
    active,
    active_count: activeCount,
    action_width: box?.width || 0,
    action_height: box?.height || 0,
    viewport_overflow: overflow,
    nav_overflow: navOverflow,
    nav_visible: Boolean(navRect && navRect.y < 844 && navRect.y + navRect.height > 0),
  };
  assert(h1.includes(expectedH1), `${route} h1 mismatch: ${h1}`);
  assert(active === 'page', `${route} mobile nav not active`);
  assert(activeCount === 1, `${route} mobile active count ${activeCount}`);
  assert((box?.height || 0) >= 40, `${route} nav target too short: ${box?.height || 0}`);
  assert((box?.width || 0) >= 44, `${route} nav target too narrow: ${box?.width || 0}`);
  assert(overflow <= 1, `${route} viewport overflow ${overflow}`);
  assert(navOverflow <= 1, `${route} mobile nav overflow ${navOverflow}`);
  assert(report.routes[route].nav_visible, `${route} mobile nav not visible`);
}

try {
  await page.goto(`${base}/setup.php`, { waitUntil: 'domcontentloaded' });
  await page.locator('#site_name').fill('VF Infra Mobile Navigation Audit');
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

  // Force a new document after fixture injection so V2.70 refreshes its in-memory snapshot.
  await page.goto(`${base}/index.php?audit=${Date.now()}#overview`, { waitUntil: 'domcontentloaded' });
  await waitRoute('overview', '个人基础设施概览');

  const nav = page.locator('.v270-mobile-nav');
  await nav.waitFor({ state: 'visible', timeout: 12000 });
  const labels = await nav.locator('[data-v270-nav]').allTextContents();
  report.nav.labels = labels.map(clean);
  report.nav.count = labels.length;
  assert(report.nav.count === 5, `mobile primary nav count ${report.nav.count}`);
  assert(JSON.stringify(report.nav.labels) === JSON.stringify(specs.map(([, label]) => label)), `mobile labels ${JSON.stringify(report.nav.labels)}`);

  await inspect('overview', '个人基础设施概览');
  for (const [route, , expectedH1] of specs.slice(1)) {
    await pointerClick(page.locator(`.v270-mobile-nav [data-v270-nav="${route}"]`));
    await waitRoute(route, expectedH1);
    await inspect(route, expectedH1);
  }

  // Return to overview to prove the nav remains usable after crossing V2.70/V2.71-owned routes.
  await pointerClick(page.locator('.v270-mobile-nav [data-v270-nav="overview"]'));
  await waitRoute('overview', '个人基础设施概览');
  await inspect('overview', '个人基础设施概览');

  await page.screenshot({ path: `${evidence}/01-mobile-overview-after-roundtrip.png`, fullPage: true, animations: 'disabled' });
  assert(report.page_errors.length === 0, `page errors ${JSON.stringify(report.page_errors)}`);
  assert(report.console_errors.length === 0, `console errors ${JSON.stringify(report.console_errors)}`);
  report.status = 'PASS';
} finally {
  fs.writeFileSync(`${evidence}/P04_MOBILE_PRIMARY_NAV_AUDIT.json`, JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}

console.log(`P04_MOBILE_PRIMARY_NAV_AUDIT=${report.status}`);
if (report.status !== 'PASS') process.exit(1);
