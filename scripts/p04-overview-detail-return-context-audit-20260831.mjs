import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';

const base = process.env.VF_E2E_BASE_URL || 'http://127.0.0.1:19074';
const webRoot = process.env.VF_E2E_WEB_ROOT || '';
const productRoot = process.env.VF_PRODUCT_ROOT || '';
const evidence = process.env.EVIDENCE || '';
const source = process.env.SOURCE || '';
if (!webRoot || !productRoot || !evidence || !source) throw new Error('overview return audit environment missing');
fs.mkdirSync(evidence, { recursive: true });

const password = 'Vf' + crypto.randomUUID().replaceAll('-', '') + 'Aa1';
const report = {
  schema: 'p04-overview-detail-return-context-audit/v1',
  source_sha: source,
  status: 'FAIL',
  domain: {},
  server: {},
  provider: {},
  findings: [],
  failures: [],
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
const assert = (value, message) => { if (!value) report.failures.push(message); };

async function pointerClick(locator) {
  await locator.waitFor({ state: 'visible', timeout: 15000 });
  const box = await locator.boundingBox();
  if (!box || box.width <= 0 || box.height <= 0) throw new Error('pointer target has no box');
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.waitForTimeout(35);
  await page.mouse.up();
}

async function csrf() {
  return await page.evaluate(async () => {
    const response = await fetch('api.php?action=bootstrap', { credentials: 'same-origin', headers: { Accept: 'application/json' } });
    const result = await response.json();
    if (!response.ok || result.ok === false || !result.csrf) throw new Error('bootstrap csrf unavailable');
    return result.csrf;
  });
}

async function createDomain() {
  const token = await csrf();
  return await page.evaluate(async ({ token }) => {
    const body = new URLSearchParams({
      domain: 'overview-return.example',
      registrar: 'Cloudflare',
      currency: 'USD',
      renewal_price: '12.00',
      renewal_policy: 'manual',
      manual_expiry_date: '2026-10-18',
      project_name: 'Synthetic Overview Return Audit',
      notes: 'Fresh isolated synthetic test data only',
    });
    const response = await fetch('api.php?action=domain_save', {
      method: 'POST', credentials: 'same-origin',
      headers: { Accept: 'application/json', 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8', 'X-CSRF-Token': token },
      body: body.toString(),
    });
    const result = await response.json();
    if (!response.ok || result.ok === false) throw new Error(result.message || 'domain_save failed');
    return result.domain;
  }, { token });
}

async function coldOverview() {
  await page.goto('about:blank');
  await page.goto(`${base}/index.php?audit=${Date.now()}#overview`, { waitUntil: 'domcontentloaded' });
  await page.getByRole('heading', { name: '个人基础设施概览' }).waitFor({ state: 'visible', timeout: 15000 });
  await page.waitForTimeout(350);
}

async function returnTimeline() {
  return await page.evaluate(async () => {
    const values = [{ phase: 'immediate', y: Math.round(scrollY) }];
    await new Promise((resolve) => requestAnimationFrame(() => { values.push({ phase: 'raf1', y: Math.round(scrollY) }); resolve(); }));
    await new Promise((resolve) => requestAnimationFrame(() => { values.push({ phase: 'raf2', y: Math.round(scrollY) }); resolve(); }));
    for (const [name, delay] of [['+100',100],['+300',200],['+600',300]]) {
      await new Promise((resolve) => setTimeout(resolve, delay));
      values.push({ phase: name, y: Math.round(scrollY) });
    }
    return values;
  });
}

async function auditOverviewEntry(config) {
  const bucket = report[config.key];
  await coldOverview();

  let button;
  if (config.lowerResource) {
    const section = page.locator('section.v270-section').filter({ hasText: '我最常看的资源' }).first();
    await section.waitFor({ state: 'visible', timeout: 15000 });
    button = section.locator(`.v270-mobile-cards [data-v270-action="${config.action}"]`).first();
  } else {
    button = page.locator(`[data-v270-action="${config.action}"]`).filter({ hasText: config.buttonText || '' }).first();
    if (!(await button.count())) button = page.locator(`[data-v270-action="${config.action}"]`).first();
  }
  await button.waitFor({ state: 'visible', timeout: 15000 });
  await button.evaluate((node) => node.scrollIntoView({ block: 'center', behavior: 'auto' }));
  await page.waitForTimeout(120);

  bucket.entry_hash = await page.evaluate(() => location.hash);
  bucket.scroll_before = await page.evaluate(() => Math.round(scrollY));
  bucket.document_height = await page.evaluate(() => Math.max(document.documentElement.scrollHeight, document.body.scrollHeight));
  bucket.button_label = (await button.textContent() || '').trim();
  bucket.entry_action = await button.getAttribute('data-v270-action');
  bucket.entry_id = await button.getAttribute('data-id');
  const entryBox = await button.boundingBox();
  bucket.entry_button_size = { width: entryBox?.width || 0, height: entryBox?.height || 0 };
  bucket.entry_overflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth);

  assert(bucket.entry_hash === '#overview', `${config.key}: not on overview before entry`);
  assert(bucket.entry_button_size.height >= 40, `${config.key}: overview action target under 40px ${JSON.stringify(bucket.entry_button_size)}`);
  assert(bucket.entry_overflow <= 1, `${config.key}: overview overflow ${bucket.entry_overflow}`);
  if (config.lowerResource) assert(bucket.scroll_before >= 300, `${config.key}: overview lower-resource probe not deep enough ${bucket.scroll_before}`);

  await pointerClick(button);
  await page.waitForFunction((route) => location.hash.startsWith(`#${route}/`), config.detailRoute, { timeout: 10000 });
  bucket.detail_hash = await page.evaluate(() => location.hash);

  const bar = page.locator('[data-v275-context-backbar]').first();
  await bar.waitFor({ state: 'visible', timeout: 10000 });
  const back = bar.locator('[data-v275-go]').first();
  await back.waitFor({ state: 'visible', timeout: 10000 });
  bucket.back_target = await back.getAttribute('data-v275-go');
  bucket.back_label = (await back.textContent() || '').trim();
  const backBox = await back.boundingBox();
  bucket.back_button_size = { width: backBox?.width || 0, height: backBox?.height || 0 };
  bucket.detail_overflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth);
  assert(bucket.back_target === '#overview', `${config.key}: detail does not return to overview ${bucket.back_target}`);
  assert(bucket.back_button_size.height >= 40, `${config.key}: detail return target under 40px ${JSON.stringify(bucket.back_button_size)}`);
  assert(bucket.detail_overflow <= 1, `${config.key}: detail overflow ${bucket.detail_overflow}`);

  if (!/概览/.test(bucket.back_label)) report.findings.push({ severity: 'copy', key: config.key, issue: 'generic_overview_return_label', observed: bucket.back_label });

  await pointerClick(back);
  await page.waitForFunction(() => location.hash === '#overview', null, { timeout: 10000 });
  await page.getByRole('heading', { name: '个人基础设施概览' }).waitFor({ state: 'visible', timeout: 15000 });
  bucket.return_timeline = await returnTimeline();
  bucket.scroll_after = bucket.return_timeline.at(-1)?.y ?? 0;
  bucket.scroll_delta = bucket.scroll_after - bucket.scroll_before;
  bucket.return_overflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth);
  assert(bucket.return_overflow <= 1, `${config.key}: returned overview overflow ${bucket.return_overflow}`);

  bucket.context_position_preserved = bucket.scroll_before < 300 || Math.abs(bucket.scroll_delta) <= 120;
  if (!bucket.context_position_preserved) {
    report.findings.push({
      severity: 'ux', key: config.key, issue: 'overview_scroll_context_lost',
      scroll_before: bucket.scroll_before, scroll_after: bucket.scroll_after, delta: bucket.scroll_delta,
    });
  }

  await page.screenshot({ path: `${evidence}/mobile-overview-${config.key}-after-detail-return.png`, fullPage: true, animations: 'disabled' });
}

try {
  await page.goto(`${base}/setup.php`, { waitUntil: 'domcontentloaded' });
  await page.locator('#site_name').fill('VF Infra Overview Return Audit');
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

  const domain = await createDomain();
  report.domain.synthetic_id = Number(domain?.id || 0);
  const fixtureOutput = execFileSync('php', [`${productRoot}/tests/fixtures/v260-user-task-fixture.php`, webRoot], { encoding: 'utf8' });
  if (!fixtureOutput.includes('P04_V260_USER_TASK_FIXTURE_PASS')) throw new Error('V260 fixture marker missing');

  await auditOverviewEntry({ key: 'server', action: 'server', detailRoute: 'server', lowerResource: true });
  await auditOverviewEntry({ key: 'domain', action: 'domain', detailRoute: 'domain', lowerResource: true });
  await auditOverviewEntry({ key: 'provider', action: 'provider', detailRoute: 'provider', lowerResource: false, buttonText: '处理' });

  assert(report.page_errors.length === 0, `page errors ${JSON.stringify(report.page_errors)}`);
  assert(report.console_errors.length === 0, `console errors ${JSON.stringify(report.console_errors)}`);
  report.status = report.failures.length === 0 ? 'PASS' : 'FAIL';
} finally {
  fs.writeFileSync(`${evidence}/P04_OVERVIEW_DETAIL_RETURN_CONTEXT_AUDIT.json`, JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}

console.log(`P04_OVERVIEW_DETAIL_RETURN_CONTEXT_AUDIT=${report.status}`);
if (report.findings.length) console.log(`P04_OVERVIEW_RETURN_FINDINGS=${JSON.stringify(report.findings)}`);
if (report.status !== 'PASS') {
  console.error(report.failures.join('\n'));
  process.exit(1);
}
