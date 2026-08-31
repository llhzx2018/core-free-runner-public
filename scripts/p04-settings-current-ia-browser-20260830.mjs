import { chromium } from 'playwright';
import fs from 'node:fs';

const base = process.env.VF_E2E_BASE_URL || 'http://127.0.0.1:19049';
const evidence = process.env.EVIDENCE;
const candidate = process.env.CANDIDATE;
if (!evidence || !candidate) throw new Error('P04 Settings Current IA browser environment missing');

const password = 'Vf' + crypto.randomUUID().replaceAll('-', '') + 'Aa1';
const report = {
  status: 'FAIL',
  source_sha: candidate,
  desktop: {},
  navigation: {},
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

async function waitSettings(section) {
  await page.goto(`${base}/index.php#settings/${section}`, { waitUntil: 'domcontentloaded' });
  await page.locator('.v271-settings-layout').waitFor({ state: 'visible', timeout: 15000 });
  await page.waitForFunction((expected) => {
    const active = document.querySelector('.v271-settings-nav button[aria-current="page"]');
    return active && active.dataset.section === expected;
  }, section, { timeout: 10000 });
  await page.waitForTimeout(250);
}

async function groupSnapshot() {
  return page.locator('.v271-settings-nav .v271-settings-group').evaluateAll((nodes) => nodes.map((node) => ({
    text: (node.textContent || '').trim(),
    display: getComputedStyle(node).display,
  })));
}

try {
  await page.goto(`${base}/setup.php`, { waitUntil: 'domcontentloaded' });
  await page.locator('#site_name').fill('VF Infra Settings Current IA Gate');
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

  // Desktop Current IA: V2811 groups must survive V280 enhancement.
  await waitSettings('basic');
  let groups = await groupSnapshot();
  assert(groups.length === 4, `desktop settings group count ${JSON.stringify(groups)}`);
  assert(JSON.stringify(groups.map((g) => g.text)) === JSON.stringify(['基础', '数据与安全', '系统维护', '技术能力']), `desktop settings group labels ${JSON.stringify(groups)}`);
  assert(groups.every((g) => g.display !== 'none'), `desktop settings groups hidden ${JSON.stringify(groups)}`);
  report.desktop.groups = 'PASS';
  report.desktop.labels = 'PASS';
  await page.screenshot({ path: `${evidence}/01-settings-desktop-basic.png`, fullPage: true, animations: 'disabled' });

  // Real Current navigation must preserve the groups after rerender/mutation cycles.
  const baseline = page.locator('.v271-settings-nav button[data-v2811-action="baseline"]');
  await baseline.click();
  await page.waitForFunction(() => location.hash === '#settings/baseline', null, { timeout: 10000 });
  await page.locator('.v2811-baseline-hero').waitFor({ state: 'visible', timeout: 15000 });
  groups = await groupSnapshot();
  assert(groups.length === 4 && groups.every((g) => g.display !== 'none'), `groups lost after baseline navigation ${JSON.stringify(groups)}`);
  assert((await baseline.getAttribute('aria-current')) === 'page', 'baseline aria-current missing');
  report.navigation.baseline = 'PASS';

  const update = page.locator('.v271-settings-nav button[data-section="update"]');
  await update.click();
  await page.waitForFunction(() => location.hash === '#settings/update', null, { timeout: 10000 });
  await page.locator('.v271-settings-layout').waitFor({ state: 'visible', timeout: 10000 });
  await page.waitForTimeout(250);
  groups = await groupSnapshot();
  assert(groups.length === 4 && groups.every((g) => g.display !== 'none'), `groups lost after update navigation ${JSON.stringify(groups)}`);
  assert((await page.locator('.v271-settings-nav button[data-section="update"]').getAttribute('aria-current')) === 'page', 'update aria-current missing');
  report.navigation.update = 'PASS';
  await page.screenshot({ path: `${evidence}/02-settings-desktop-update.png`, fullPage: true, animations: 'disabled' });

  const diagnostics = page.locator('.v271-settings-nav button[data-section="diagnostics"]');
  await diagnostics.click();
  await page.waitForFunction(() => location.hash === '#settings/diagnostics', null, { timeout: 10000 });
  await page.locator('.v271-settings-layout').waitFor({ state: 'visible', timeout: 10000 });
  await page.waitForTimeout(250);
  groups = await groupSnapshot();
  assert(groups.length === 4 && groups.every((g) => g.display !== 'none'), `groups lost after diagnostics navigation ${JSON.stringify(groups)}`);
  assert((await page.locator('.v271-settings-nav button[data-section="diagnostics"]').getAttribute('aria-current')) === 'page', 'diagnostics aria-current missing');
  report.navigation.diagnostics = 'PASS';

  // Mobile keeps the existing compact horizontal nav: group semantics remain in DOM but headings are hidden.
  await page.setViewportSize({ width: 390, height: 844 });
  await waitSettings('basic');
  groups = await groupSnapshot();
  assert(groups.length === 4, `mobile group DOM count ${JSON.stringify(groups)}`);
  assert(groups.every((g) => g.display === 'none'), `mobile group headings should be hidden ${JSON.stringify(groups)}`);
  const nav = page.locator('.v271-settings-nav');
  const navStyle = await nav.evaluate((node) => ({ overflowX: getComputedStyle(node).overflowX, display: getComputedStyle(node).display }));
  assert(navStyle.display === 'flex', `mobile settings nav display ${JSON.stringify(navStyle)}`);
  assert(['auto', 'scroll'].includes(navStyle.overflowX), `mobile settings nav overflow ${JSON.stringify(navStyle)}`);
  const pageOverflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - window.innerWidth);
  assert(pageOverflow <= 1, `mobile page horizontal overflow ${pageOverflow}`);
  const active = page.locator('.v271-settings-nav button[data-section="basic"]');
  assert((await active.getAttribute('aria-current')) === 'page', 'mobile basic aria-current missing');
  report.mobile.groups_hidden = 'PASS';
  report.mobile.horizontal_nav = 'PASS';
  report.mobile.no_page_overflow = 'PASS';
  await page.screenshot({ path: `${evidence}/03-settings-mobile-390.png`, fullPage: true, animations: 'disabled' });

  assert(report.page_errors.length === 0, `page errors ${JSON.stringify(report.page_errors)}`);
  assert(report.console_errors.length === 0, `console errors ${JSON.stringify(report.console_errors)}`);
  report.status = 'PASS';
} finally {
  fs.mkdirSync(evidence, { recursive: true });
  fs.writeFileSync(`${evidence}/P04_SETTINGS_CURRENT_IA_REPORT.json`, JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}

if (report.status !== 'PASS') process.exit(1);
console.log('P04_SETTINGS_CURRENT_IA_BROWSER=PASS');
