import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const base = process.env.VF_E2E_BASE_URL || 'http://127.0.0.1:19047';
const evidence = process.env.EVIDENCE;
const candidate = process.env.CANDIDATE;
const webRoot = process.env.WEB_ROOT;
const productRoot = process.env.PRODUCT_ROOT || path.join(process.cwd(), 'product');
if (!evidence || !candidate || !webRoot) throw new Error('P04 server UX browser environment missing');

const password = 'Vf' + crypto.randomUUID().replaceAll('-', '') + 'Aa1';
const report = {
  status: 'FAIL',
  source_sha: candidate,
  list: {},
  detail: {},
  accessibility: {},
  mobile: {},
  page_errors: [],
  console_errors: [],
};
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1365, height: 900 } });
const page = await context.newPage();
page.on('pageerror', (e) => report.page_errors.push(String(e?.stack || e)));
page.on('console', (m) => { if (m.type() === 'error') report.console_errors.push(m.text()); });
const assert = (value, message) => { if (!value) throw new Error(message); };

async function cold(hash) {
  await page.goto('about:blank');
  await page.goto(`${base}/index.php#${hash}`, { waitUntil: 'domcontentloaded' });
  await page.locator('#v270-app h1').waitFor({ state: 'visible', timeout: 15000 });
  await page.waitForTimeout(600);
}

async function waitServerListReady() {
  const toolbar = page.locator('[data-v275-toolbar="servers"]');
  await toolbar.waitFor({ state: 'visible', timeout: 10000 });
  const brief = page.locator('.v2812-server-brief');
  await brief.waitFor({ state: 'visible', timeout: 10000 });
  const row = page.locator('table.server-table tbody tr').filter({ hasText: 'v260-edge-01' }).first();
  await row.waitFor({ state: 'visible', timeout: 10000 });
  return { toolbar, brief, row, action: row.locator('[data-v270-action="server"]') };
}

async function waitServerDetail(serverId) {
  await page.waitForFunction((id) => location.hash === `#server/${encodeURIComponent(id)}`, serverId, { timeout: 10000 });
  await page.locator('.v270-ref-summary[data-ref-lock="server-summary"]').waitFor({ state: 'visible', timeout: 10000 });
}

try {
  await page.goto(`${base}/setup.php`, { waitUntil: 'domcontentloaded' });
  await page.locator('#site_name').fill('VF Infra Server Daily UX Gate R4');
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
  assert(fixture.includes('P04_V260_USER_TASK_FIXTURE_PASS'), 'server fixture failed');
  execFileSync('php', ['-r', 'require getenv("WEB_ROOT")."/bootstrap.php"; Database::connection()->exec("UPDATE compute_instances SET power_status=\'stopped\', external_status=\'stopped\' WHERE external_instance_id=\'v260-edge-01\'");'], {
    cwd: productRoot,
    env: { ...process.env, WEB_ROOT: webRoot },
    encoding: 'utf8',
  });

  // 1) Cold list: the ordinary pointer path must still enter Current server detail.
  await cold('servers');
  assert(await page.locator('body.v2812-server-ux').count() === 1, 'server UX body class missing');
  let { toolbar, brief, row, action } = await waitServerListReady();
  assert((await row.getAttribute('data-v2812-server-risk')) === 'attention', 'stopped server attention missing');
  assert((await action.getAttribute('aria-label')) === '管理 v260-edge-01', 'server action aria missing');
  const serverId = await action.getAttribute('data-id');
  assert(Boolean(serverId), 'server data-id missing');
  report.detail.server_id = serverId;
  assert((await toolbar.locator('input[type="search"]').getAttribute('placeholder')) === '搜索服务器、服务商、区域或状态', 'server search placeholder missing');
  const initial = (await brief.innerText()).replace(/\s+/g, ' ').trim();
  assert(initial.includes('本页 1 台服务器'), `initial brief ${initial}`);
  assert(initial.includes('需要优先处理'), `attention brief ${initial}`);
  report.list.attention = 'PASS';
  report.list.summary = 'PASS';
  await page.screenshot({ path: `${evidence}/01-servers-desktop.png`, fullPage: true, animations: 'disabled' });

  await action.click();
  await waitServerDetail(serverId);
  report.detail.cold_pointer_navigation = 'PASS';
  assert(await page.locator('.v270-ref-summary[data-ref-lock="server-summary"] .v270-ref-metric[data-v2812-server-priority]').count() >= 1, 'detail priority missing');
  assert((await page.locator('.v270-next h2').innerText()).trim() === '下一步', 'owner next copy not simplified');
  assert(await page.locator('.v270-side h2').filter({ hasText: '高风险操作边界' }).count() === 1, 'risk boundary copy missing');
  report.detail.priority = 'PASS';
  report.detail.next_action = 'PASS';
  report.detail.risk_boundary = 'PASS';
  await page.screenshot({ path: `${evidence}/02-server-detail-desktop.png`, fullPage: true, animations: 'disabled' });

  // 2) Filter lifecycle: validate visible/total summary independently from the known baseline headless pointer quirk.
  await cold('servers');
  ({ toolbar, brief, row, action } = await waitServerListReady());
  const search = toolbar.locator('input[type="search"]');
  const count = toolbar.locator('[data-v275-count]');
  await search.fill('no-such-server');
  await page.waitForFunction(() => document.querySelector('[data-v275-toolbar="servers"] [data-v275-count]')?.textContent?.trim().startsWith('0 / 1'));
  await page.waitForFunction(() => document.querySelector('.v2812-server-brief')?.textContent?.replace(/\s+/g, ' ').includes('当前显示 0 / 1 台服务器'));
  const filtered = (await brief.innerText()).replace(/\s+/g, ' ').trim();
  assert(filtered.includes('当前显示 0 / 1 台服务器'), `filtered brief ${filtered}`);

  await search.fill('v260-edge-01');
  await page.waitForFunction(() => {
    const count = document.querySelector('[data-v275-toolbar="servers"] [data-v275-count]')?.textContent?.trim() || '';
    const brief = document.querySelector('.v2812-server-brief')?.textContent?.replace(/\s+/g, ' ').trim() || '';
    const row = [...document.querySelectorAll('table.server-table tbody tr')].find((node) => node.textContent?.includes('v260-edge-01'));
    return count.startsWith('1 / 1') && brief.includes('本页 1 台服务器') && row && !row.hidden;
  }, null, { timeout: 10000 });
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  assert((await count.innerText()).trim().startsWith('1 / 1'), 'restored toolbar count mismatch');
  assert((await brief.innerText()).replace(/\s+/g, ' ').includes('本页 1 台服务器'), 'restored brief mismatch');
  assert(await row.isVisible(), 'restored server row not visible');
  assert(await action.isEnabled(), 'restored server action not enabled');
  report.list.filter_hide = 'PASS';
  report.list.filter_restore = 'PASS';

  // Keyboard activation is a real browser/user path and must remain usable after the V2.75 hide/show lifecycle.
  await action.focus();
  assert(await action.evaluate((node) => document.activeElement === node), 'server action did not receive focus after filter restore');
  await action.press('Enter');
  await waitServerDetail(serverId);
  report.accessibility.post_filter_keyboard_navigation = 'PASS';

  // 3) Mobile list affordance.
  await page.setViewportSize({ width: 390, height: 844 });
  await cold('servers');
  const card = page.locator('.server-card').filter({ hasText: 'v260-edge-01' }).first();
  await card.waitFor({ state: 'visible', timeout: 10000 });
  assert((await card.getAttribute('data-v2812-server-risk')) === 'attention', 'mobile server risk missing');
  const overflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - window.innerWidth);
  assert(overflow <= 1, `mobile horizontal overflow ${overflow}`);
  const mobileAction = card.locator('[data-v270-action="server"]');
  assert((await mobileAction.getAttribute('aria-label')) === '管理 v260-edge-01', 'mobile server aria missing');
  const box = await mobileAction.boundingBox();
  assert(box && box.height >= 40, `mobile action target ${JSON.stringify(box)}`);
  report.mobile.risk = 'PASS';
  report.mobile.no_overflow = 'PASS';
  report.mobile.action_target = 'PASS';
  await page.screenshot({ path: `${evidence}/03-servers-mobile-390.png`, fullPage: true, animations: 'disabled' });

  assert(report.page_errors.length === 0, `page errors ${JSON.stringify(report.page_errors)}`);
  assert(report.console_errors.length === 0, `console errors ${JSON.stringify(report.console_errors)}`);
  report.status = 'PASS';
} finally {
  fs.mkdirSync(evidence, { recursive: true });
  fs.writeFileSync(`${evidence}/P04_SERVER_DAILY_UX_REPORT.json`, JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}

if (report.status !== 'PASS') process.exit(1);
console.log('P04_SERVER_DAILY_UX_BROWSER_R4=PASS');
