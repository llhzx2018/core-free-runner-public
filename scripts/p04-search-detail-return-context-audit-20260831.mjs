import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';

const base = process.env.VF_E2E_BASE_URL || 'http://127.0.0.1:19072';
const webRoot = process.env.VF_E2E_WEB_ROOT || '';
const productRoot = process.env.VF_PRODUCT_ROOT || '';
const evidence = process.env.EVIDENCE || '';
const source = process.env.SOURCE || '';
if (!webRoot || !productRoot || !evidence || !source) throw new Error('search return audit environment missing');
fs.mkdirSync(evidence, { recursive: true });

const password = 'Vf' + crypto.randomUUID().replaceAll('-', '') + 'Aa1';
const report = {
  schema: 'p04-search-detail-return-context-audit/v1',
  source_sha: source,
  status: 'FAIL',
  domain: {},
  server: {},
  provider: {},
  copy_debt: [],
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
  await locator.scrollIntoViewIfNeeded();
  await page.waitForTimeout(70);
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
      domain: 'search-return.example',
      registrar: 'Cloudflare',
      currency: 'USD',
      renewal_price: '12.00',
      renewal_policy: 'manual',
      manual_expiry_date: '2026-10-18',
      project_name: 'Synthetic Search Return Audit',
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

async function searchAndReturn(config) {
  const bucket = report[config.key];
  await page.goto(`${base}/index.php?audit=${Date.now()}#overview`, { waitUntil: 'domcontentloaded' });
  const input = page.locator('#v270-search-input');
  const form = page.locator('#v270-search-form');
  await input.waitFor({ state: 'visible', timeout: 15000 });
  await input.fill(config.query);
  await form.evaluate((node) => node.requestSubmit());
  await page.waitForFunction((q) => decodeURIComponent(location.hash).includes(`#search/${q}`), config.query, { timeout: 10000 });
  await page.locator('.v270-search-result').first().waitFor({ state: 'visible', timeout: 15000 });
  bucket.search_hash = await page.evaluate(() => location.hash);
  bucket.input_before = await input.inputValue();
  bucket.result_count_before = await page.locator('.v270-search-result').count();

  const card = page.locator('.v270-search-result').filter({ hasText: config.name }).first();
  await card.waitFor({ state: 'visible', timeout: 15000 });
  const open = card.locator('[data-v270-action="open"][data-id]').first();
  const spec = await open.getAttribute('data-id');
  bucket.open_spec = spec;
  assert(Boolean(spec), `${config.key}: search result open spec missing`);
  const [target = '', id = ''] = String(spec || '').split(':');
  const detailRoute = target === 'domain' ? 'domain' : target === 'provider' ? 'provider' : ['vps', 'server'].includes(target) ? 'server' : target === 'dns' ? 'dns' : '';
  assert(detailRoute === config.detailRoute, `${config.key}: search target route mismatch ${target} -> ${detailRoute}`);
  await pointerClick(open);
  await page.waitForFunction(({ detailRoute, id }) => location.hash === `#${detailRoute}/${id}`, { detailRoute, id }, { timeout: 10000 });
  bucket.detail_hash = await page.evaluate(() => location.hash);
  bucket.detail_name_visible = (await page.getByText(config.name, { exact: false }).count()) > 0;
  assert(bucket.detail_name_visible, `${config.key}: target name not visible in detail`);

  const bar = page.locator('[data-v275-context-backbar]').first();
  await bar.waitFor({ state: 'visible', timeout: 10000 });
  const back = bar.locator('[data-v275-go^="#search/"]').first();
  await back.waitFor({ state: 'visible', timeout: 10000 });
  bucket.back_target = await back.getAttribute('data-v275-go');
  bucket.back_label = (await back.textContent() || '').trim();
  const box = await back.boundingBox();
  bucket.back_size = { width: box?.width || 0, height: box?.height || 0 };
  bucket.detail_overflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth);
  bucket.specific_search_label = /搜索/.test(bucket.back_label);
  if (!bucket.specific_search_label) report.copy_debt.push(`${config.key}: ${bucket.back_label}`);
  assert(bucket.back_target === bucket.search_hash, `${config.key}: return target lost search hash ${bucket.back_target} != ${bucket.search_hash}`);
  assert(bucket.back_size.height >= 40 && bucket.back_size.width >= 52, `${config.key}: return button too small ${JSON.stringify(bucket.back_size)}`);
  assert(bucket.detail_overflow <= 1, `${config.key}: detail overflow ${bucket.detail_overflow}`);

  await pointerClick(back);
  await page.waitForFunction((hash) => location.hash === hash, bucket.search_hash, { timeout: 10000 });
  await page.locator('.v270-search-result').first().waitFor({ state: 'visible', timeout: 15000 });
  await page.waitForTimeout(250);
  bucket.return_hash = await page.evaluate(() => location.hash);
  bucket.input_after = await input.inputValue();
  bucket.result_count_after = await page.locator('.v270-search-result').count();
  bucket.target_result_after = await page.locator('.v270-search-result').filter({ hasText: config.name }).first().isVisible();
  bucket.return_overflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth);
  assert(bucket.return_hash === bucket.search_hash, `${config.key}: search hash changed after return`);
  assert(bucket.input_after === config.query, `${config.key}: shell search input lost query ${bucket.input_after}`);
  assert(bucket.result_count_after === bucket.result_count_before, `${config.key}: result count changed ${bucket.result_count_before} -> ${bucket.result_count_after}`);
  assert(bucket.target_result_after, `${config.key}: target result missing after return`);
  assert(bucket.return_overflow <= 1, `${config.key}: search results overflow ${bucket.return_overflow}`);

  await page.screenshot({ path: `${evidence}/mobile-search-${config.key}-after-detail-return.png`, fullPage: true, animations: 'disabled' });
}

try {
  await page.goto(`${base}/setup.php`, { waitUntil: 'domcontentloaded' });
  await page.locator('#site_name').fill('VF Infra Search Return Audit');
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

  await searchAndReturn({ key: 'domain', query: 'search-return.example', name: 'search-return.example', detailRoute: 'domain' });
  await searchAndReturn({ key: 'server', query: 'v260-edge-01', name: 'v260-edge-01', detailRoute: 'server' });
  await searchAndReturn({ key: 'provider', query: 'V260 Linode 异常账号', name: 'V260 Linode 异常账号', detailRoute: 'provider' });

  assert(report.page_errors.length === 0, `page errors ${JSON.stringify(report.page_errors)}`);
  assert(report.console_errors.length === 0, `console errors ${JSON.stringify(report.console_errors)}`);
  report.status = report.failures.length === 0 ? 'PASS' : 'FAIL';
} finally {
  fs.writeFileSync(`${evidence}/P04_SEARCH_DETAIL_RETURN_CONTEXT_AUDIT.json`, JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}

console.log(`P04_SEARCH_DETAIL_RETURN_CONTEXT_AUDIT=${report.status}`);
if (report.copy_debt.length) console.log(`P04_SEARCH_RETURN_COPY_DEBT=${JSON.stringify(report.copy_debt)}`);
if (report.status !== 'PASS') {
  console.error(report.failures.join('\n'));
  process.exit(1);
}
