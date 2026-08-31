import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const base = process.env.VF_E2E_BASE_URL || 'http://127.0.0.1:19064';
const evidence = process.env.EVIDENCE;
const candidate = process.env.CANDIDATE;
const webRoot = process.env.WEB_ROOT;
const productRoot = process.env.PRODUCT_ROOT || path.join(process.cwd(), 'product');
if (!evidence || !candidate || !webRoot) throw new Error('mobile shell audit environment missing');
fs.mkdirSync(evidence, { recursive: true });

const password = 'Vf' + crypto.randomUUID().replaceAll('-', '') + 'Aa1';
const query = 'v260-edge-01';
const report = {
  schema: 'p04-mobile-topbar-bottom-safe-audit/v1',
  source_sha: candidate,
  status: 'FAIL',
  routes: {},
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
const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();
const assert = (value, message) => { if (!value) throw new Error(message); };

async function pointerClick(locator) {
  await locator.waitFor({ state: 'visible', timeout: 12000 });
  await locator.scrollIntoViewIfNeeded();
  await page.waitForTimeout(60);
  const box = await locator.boundingBox();
  if (!box || box.width <= 0 || box.height <= 0) throw new Error('pointer target has no box');
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.waitForTimeout(35);
  await page.mouse.up();
}

const specs = [
  ['overview', '个人基础设施概览'],
  ['domains', '域名'],
  ['servers', '服务器'],
  ['providers', '服务商'],
  ['settings', '设置'],
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

async function inspectBottomSafety(route) {
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
  await page.waitForTimeout(180);
  const geometry = await page.evaluate(() => {
    const nav = document.querySelector('.v270-mobile-nav');
    const footer = document.querySelector('#v270-app .v270-footer');
    const app = document.querySelector('#v270-app');
    if (!nav || !footer || !app) return null;
    const nr = nav.getBoundingClientRect();
    const fr = footer.getBoundingClientRect();
    const ar = app.getBoundingClientRect();
    const bodyStyle = getComputedStyle(document.body);
    const appStyle = getComputedStyle(app);
    return {
      nav_top: nr.top,
      nav_height: nr.height,
      footer_bottom: fr.bottom,
      footer_top: fr.top,
      footer_to_nav_gap: nr.top - fr.bottom,
      app_bottom: ar.bottom,
      body_padding_bottom: bodyStyle.paddingBottom,
      app_padding_bottom: appStyle.paddingBottom,
      scroll_y: window.scrollY,
      max_scroll: Math.max(0, document.documentElement.scrollHeight - innerHeight),
      viewport_overflow: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth,
    };
  });
  assert(geometry, `${route} bottom geometry missing`);
  assert(geometry.viewport_overflow <= 1, `${route} viewport overflow ${geometry.viewport_overflow}`);
  assert(geometry.nav_height >= 44, `${route} mobile nav total height ${geometry.nav_height}`);
  assert(geometry.footer_to_nav_gap >= 8, `${route} footer is obscured by fixed nav: gap ${geometry.footer_to_nav_gap}`);
  assert(Math.abs(geometry.scroll_y - geometry.max_scroll) <= 2, `${route} did not reach document bottom`);
  return geometry;
}

async function inspectAndUseGlobalSearch(route) {
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(120);
  const form = page.locator('#v270-search-form');
  const input = page.locator('#v270-search-input');
  const submit = form.locator('button[type="submit"], button').first();
  await form.waitFor({ state: 'visible', timeout: 12000 });
  await input.waitFor({ state: 'visible', timeout: 12000 });
  await submit.waitFor({ state: 'visible', timeout: 12000 });
  const dims = await page.evaluate(() => {
    const form = document.querySelector('#v270-search-form');
    const input = document.querySelector('#v270-search-input');
    const button = form?.querySelector('button');
    if (!form || !input || !button) return null;
    const f = form.getBoundingClientRect();
    const i = input.getBoundingClientRect();
    const b = button.getBoundingClientRect();
    return {
      form_left: f.left, form_right: f.right, form_width: f.width,
      input_height: i.height, input_width: i.width,
      button_height: b.height, button_width: b.width,
      viewport_width: innerWidth,
    };
  });
  assert(dims, `${route} search geometry missing`);
  assert(dims.form_left >= -1 && dims.form_right <= dims.viewport_width + 1, `${route} search form exceeds viewport ${JSON.stringify(dims)}`);
  assert(dims.input_height >= 40, `${route} search input too short ${dims.input_height}`);
  assert(dims.button_height >= 40, `${route} search button too short ${dims.button_height}`);
  assert(dims.button_width >= 44, `${route} search button too narrow ${dims.button_width}`);

  await input.fill(query);
  await page.waitForTimeout(80);
  await pointerClick(submit);
  await page.waitForFunction((q) => location.hash === `#search/${encodeURIComponent(q)}`, query, { timeout: 12000 });
  const heading = page.locator('#v270-app h1').first();
  await heading.waitFor({ state: 'visible', timeout: 15000 });
  const result = page.locator('.v270-search-result').filter({ hasText: query }).first();
  await result.waitFor({ state: 'visible', timeout: 15000 });
  const searchOverflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth);
  assert(searchOverflow <= 1, `${route} search results overflow ${searchOverflow}`);
  return {
    ...dims,
    result_text: clean(await result.innerText()),
    search_hash: await page.evaluate(() => location.hash),
    search_overflow: searchOverflow,
  };
}

try {
  await page.goto(`${base}/setup.php`, { waitUntil: 'domcontentloaded' });
  await page.locator('#site_name').fill('VF Infra Mobile Shell Audit');
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
  await page.goto(`${base}/index.php?audit=${Date.now()}#overview`, { waitUntil: 'domcontentloaded' });
  await waitRoute('overview', '个人基础设施概览');

  for (const [route, expectedH1] of specs) {
    if ((await page.evaluate(() => (location.hash || '#overview').slice(1))) !== route) {
      await pointerClick(page.locator(`.v270-mobile-nav [data-v270-nav="${route}"]`));
      await waitRoute(route, expectedH1);
    }
    const bottom = await inspectBottomSafety(route);
    const search = await inspectAndUseGlobalSearch(route);
    report.routes[route] = { bottom, search };
    await page.screenshot({ path: `${evidence}/${route}-search.png`, fullPage: true, animations: 'disabled' });
  }

  assert(report.page_errors.length === 0, `page errors ${JSON.stringify(report.page_errors)}`);
  assert(report.console_errors.length === 0, `console errors ${JSON.stringify(report.console_errors)}`);
  report.status = 'PASS';
} finally {
  fs.writeFileSync(`${evidence}/P04_MOBILE_TOPBAR_BOTTOM_SAFE_AUDIT.json`, JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}

console.log(`P04_MOBILE_TOPBAR_BOTTOM_SAFE_AUDIT=${report.status}`);
if (report.status !== 'PASS') process.exit(1);
