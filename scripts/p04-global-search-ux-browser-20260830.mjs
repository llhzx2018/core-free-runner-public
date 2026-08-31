import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const base = process.env.VF_E2E_BASE_URL || 'http://127.0.0.1:19051';
const evidence = process.env.EVIDENCE;
const candidate = process.env.CANDIDATE;
const webRoot = process.env.WEB_ROOT;
const productRoot = process.env.PRODUCT_ROOT || path.join(process.cwd(), 'product');
if (!evidence || !candidate || !webRoot) throw new Error('P04 global search UX browser environment missing');

const password = 'Vf' + crypto.randomUUID().replaceAll('-', '') + 'Aa1';
const report = {
  status: 'FAIL', source_sha: candidate,
  server: {}, provider: {}, unsupported: {}, empty: {}, mobile: {},
  page_errors: [], console_errors: [],
  production_actions_executed: false,
  synthetic_test_data_only: true,
};

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1365, height: 900 } });
const page = await context.newPage();
page.on('pageerror', (e) => report.page_errors.push(String(e?.stack || e)));
page.on('console', (m) => { if (m.type() === 'error') report.console_errors.push(m.text()); });
const assert = (value, message) => { if (!value) throw new Error(message); };

async function search(query) {
  await page.goto(`${base}/index.php#overview`, { waitUntil: 'domcontentloaded' });
  await page.locator('#v270-search-input').waitFor({ state: 'visible', timeout: 15000 });
  await page.locator('#v270-search-input').fill(query);
  await page.locator('#v270-search-form').evaluate((form) => form.requestSubmit());
  await page.waitForFunction((q) => location.hash === `#search/${encodeURIComponent(q)}`, query, { timeout: 10000 });
  await page.locator('#v270-app h1').waitFor({ state: 'visible', timeout: 15000 });
  await page.waitForTimeout(350);
}

async function resultCards() {
  return page.locator('.v270-search-results .v270-search-result');
}

try {
  await page.goto(`${base}/setup.php`, { waitUntil: 'domcontentloaded' });
  await page.locator('#site_name').fill('VF Infra Global Search UX Gate');
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
  assert(fixture.includes('P04_V260_USER_TASK_FIXTURE_PASS'), 'synthetic fixture failed');

  // 1) Server-name search: one Current resource, human context, real pointer navigation.
  await search('v260-edge-01');
  let cards = await resultCards();
  assert(await cards.count() === 1, `server search should dedupe to one Current target, got ${await cards.count()}`);
  let card = cards.first();
  let text = (await card.innerText()).replace(/\s+/g, ' ').trim();
  assert(!text.includes('[object Object]'), `server search leaked object: ${text}`);
  assert(text.includes('状态') && text.includes('区域 us-east'), `server context not human enough: ${text}`);
  let open = card.locator('[data-v270-action="open"]');
  assert(await open.count() === 1, 'server Current target missing open action');
  assert((await open.getAttribute('aria-label')) === '打开 v260-edge-01', `server aria label ${await open.getAttribute('aria-label')}`);
  const serverSpec = await open.getAttribute('data-id');
  assert(/^vps:\d+$/.test(serverSpec || ''), `server target spec ${serverSpec}`);
  const serverId = String(serverSpec).split(':')[1];
  await open.click();
  await page.waitForFunction((id) => location.hash === `#server/${encodeURIComponent(id)}`, serverId, { timeout: 10000 });
  await page.locator('.v270-context-head').waitFor({ state: 'visible', timeout: 10000 });
  report.server.name_search = 'PASS';
  report.server.dedupe = 'PASS';
  report.server.context = 'PASS';
  report.server.pointer_navigation = 'PASS';
  await page.screenshot({ path: `${evidence}/01-search-server.png`, fullPage: true, animations: 'disabled' });

  // 2) IP search must resolve the same resource without object leakage.
  await search('203.0.113.26');
  cards = await resultCards();
  assert(await cards.count() === 1, `IP search should dedupe to one Current target, got ${await cards.count()}`);
  text = (await cards.first().innerText()).replace(/\s+/g, ' ').trim();
  assert(!text.includes('[object Object]'), `IP search leaked object: ${text}`);
  assert(text.includes('v260-edge-01'), `IP search lost server identity: ${text}`);
  report.server.ip_search = 'PASS';
  await page.screenshot({ path: `${evidence}/02-search-ip.png`, fullPage: true, animations: 'disabled' });

  // 3) Provider search: human risk context, account-specific aria, real pointer navigation.
  await search('V260 Linode');
  cards = await resultCards();
  assert(await cards.count() === 1, `provider search count ${await cards.count()}`);
  card = cards.first();
  text = (await card.innerText()).replace(/\s+/g, ' ').trim();
  assert(!text.includes('[object Object]'), `provider search leaked object: ${text}`);
  assert(text.includes('账户') && text.includes('同步') && text.includes('最近错误'), `provider context missing owner signals: ${text}`);
  open = card.locator('[data-v270-action="open"]');
  assert(await open.count() === 1, 'provider Current target missing open action');
  const providerTitle = (await card.locator('h3').innerText()).trim();
  assert((await open.getAttribute('aria-label')) === `打开 ${providerTitle}`, `provider aria label ${await open.getAttribute('aria-label')}`);
  const providerSpec = await open.getAttribute('data-id');
  assert(/^provider:\d+$/.test(providerSpec || ''), `provider target spec ${providerSpec}`);
  const providerId = String(providerSpec).split(':')[1];
  await open.click();
  await page.waitForFunction((id) => location.hash === `#provider/${encodeURIComponent(id)}`, providerId, { timeout: 10000 });
  await page.locator('.v271-provider-summary, .v270-context-head').first().waitFor({ state: 'visible', timeout: 10000 });
  report.provider.context = 'PASS';
  report.provider.aria = 'PASS';
  report.provider.pointer_navigation = 'PASS';
  await page.screenshot({ path: `${evidence}/03-search-provider.png`, fullPage: true, animations: 'disabled' });

  // 4) Controlled renderer-only proof: unsupported backend targets must never expose false Current open actions.
  await page.route('**/experience.php?*', async (route) => {
    const url = new URL(route.request().url());
    if (url.searchParams.get('view') === 'search' && url.searchParams.get('q') === 'unsupported-mock') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, data: { results: [
          { kind: 'billing', id: 71, title: 'Synthetic invoice', subtitle: '费用记录', target: 'money', context: { status: 'pending', occurred_at: '2026-08-30T08:00:00Z', provider: 'Synthetic Provider' } },
          { kind: 'project', id: 81, title: 'Synthetic project', subtitle: '项目', target: 'infrastructure', context: { status: 'active' } },
        ] } }),
      });
      return;
    }
    await route.continue();
  });
  await search('unsupported-mock');
  cards = await resultCards();
  assert(await cards.count() === 2, `unsupported mock result count ${await cards.count()}`);
  assert(await page.locator('.v270-search-result [data-v270-action="open"]').count() === 0, 'unsupported targets exposed false open actions');
  text = (await page.locator('.v270-search-results').innerText()).replace(/\s+/g, ' ').trim();
  assert(!text.includes('[object Object]'), `unsupported mock leaked object: ${text}`);
  assert(text.includes('状态 待处理') && text.includes('时间 2026-08-30'), `billing mock context missing: ${text}`);
  report.unsupported.no_false_open = 'PASS';
  report.unsupported.human_context = 'PASS';
  await page.screenshot({ path: `${evidence}/04-search-unsupported.png`, fullPage: true, animations: 'disabled' });
  await page.unroute('**/experience.php?*');

  // 5) Empty search tells the owner what to try next.
  await search('definitely-no-such-resource-20260830');
  const empty = page.locator('.v270-search-results .v270-empty');
  await empty.waitFor({ state: 'visible', timeout: 10000 });
  text = (await empty.innerText()).replace(/\s+/g, ' ').trim();
  assert(text.includes('没有找到相关基础设施') && text.includes('域名') && text.includes('IP') && text.includes('服务器名') && text.includes('服务商'), `empty guidance ${text}`);
  report.empty.guidance = 'PASS';

  // 6) Mobile search keeps the same clean result and no page overflow.
  await page.setViewportSize({ width: 390, height: 844 });
  await search('v260-edge-01');
  cards = await resultCards();
  assert(await cards.count() === 1, `mobile server result count ${await cards.count()}`);
  text = (await cards.first().innerText()).replace(/\s+/g, ' ').trim();
  assert(!text.includes('[object Object]'), `mobile search leaked object: ${text}`);
  const mobileOpen = cards.first().locator('[data-v270-action="open"]');
  const box = await mobileOpen.boundingBox();
  assert(box && box.height >= 36, `mobile search action target ${JSON.stringify(box)}`);
  const overflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - window.innerWidth);
  assert(overflow <= 1, `mobile page horizontal overflow ${overflow}`);
  report.mobile.clean_result = 'PASS';
  report.mobile.action_target = 'PASS';
  report.mobile.no_page_overflow = 'PASS';
  await page.screenshot({ path: `${evidence}/05-search-mobile-390.png`, fullPage: true, animations: 'disabled' });

  assert(report.page_errors.length === 0, `page errors ${JSON.stringify(report.page_errors)}`);
  assert(report.console_errors.length === 0, `console errors ${JSON.stringify(report.console_errors)}`);
  report.status = 'PASS';
} finally {
  fs.mkdirSync(evidence, { recursive: true });
  fs.writeFileSync(`${evidence}/P04_GLOBAL_SEARCH_UX_REPORT.json`, JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}

if (report.status !== 'PASS') process.exit(1);
console.log('P04_GLOBAL_SEARCH_UX_BROWSER=PASS');
