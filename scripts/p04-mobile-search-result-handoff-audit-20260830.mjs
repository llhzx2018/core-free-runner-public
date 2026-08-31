import { chromium } from 'playwright';
import fs from 'node:fs';

const base = process.env.VF_E2E_BASE_URL || 'http://127.0.0.1:19067';
const evidence = process.env.EVIDENCE;
const candidate = process.env.CANDIDATE;
if (!evidence || !candidate) throw new Error('domain search handoff audit environment missing');
fs.mkdirSync(evidence, { recursive: true });

const password = 'Vf' + crypto.randomUUID().replaceAll('-', '') + 'Aa1';
const query = 'daily-search-return.example';
const expectedHash = `#search/${encodeURIComponent(query)}`;
const report = {
  schema: 'p04-mobile-domain-search-handoff-audit/v1',
  source_sha: candidate,
  status: 'FAIL',
  domain_create: {},
  result: {},
  browser_back: {},
  context_back: {},
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
  await page.waitForTimeout(70);
  const box = await locator.boundingBox();
  if (!box || box.width <= 0 || box.height <= 0) throw new Error('domain pointer target has no box');
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.waitForTimeout(35);
  await page.mouse.up();
}

async function createSyntheticDomain() {
  return await page.evaluate(async (domain) => {
    const bootstrapRes = await fetch('api.php?action=bootstrap', {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    });
    const bootstrap = await bootstrapRes.json();
    if (!bootstrapRes.ok || bootstrap.ok === false || !bootstrap.csrf) {
      throw new Error(bootstrap.message || 'bootstrap csrf unavailable');
    }
    const body = new URLSearchParams({
      domain,
      registrar: 'Namecheap',
      currency: 'USD',
      renewal_price: '18.50',
      renewal_policy: 'manual',
      manual_expiry_date: '2026-09-18',
      project_name: 'Synthetic Search Return Audit',
      notes: 'Fresh isolated synthetic test data only',
    });
    const saveRes = await fetch('api.php?action=domain_save', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
        'X-CSRF-Token': bootstrap.csrf,
      },
      body: body.toString(),
    });
    const saved = await saveRes.json();
    if (!saveRes.ok || saved.ok === false) throw new Error(saved.message || 'domain_save failed');
    return {
      ok: true,
      id: Number(saved.domain?.id || 0),
      domain: String(saved.domain?.domain || ''),
    };
  }, query);
}

async function searchFromOverview() {
  await page.goto(`${base}/index.php?audit=${Date.now()}#overview`, { waitUntil: 'domcontentloaded' });
  const input = page.locator('#v270-search-input');
  const submit = page.locator('#v270-search-form button').first();
  await input.waitFor({ state: 'visible', timeout: 12000 });
  await input.fill(query);
  await pointerClick(submit);
  await page.waitForFunction((hash) => location.hash === hash, expectedHash, { timeout: 12000 });
  const result = page.locator('.v270-search-result').filter({ hasText: query }).first();
  await result.waitFor({ state: 'visible', timeout: 15000 });
  const action = result.locator('button:visible').first();
  await action.waitFor({ state: 'visible', timeout: 10000 });
  return { result, action };
}

async function inspectResult(result, action) {
  const box = await action.boundingBox();
  const meta = await action.evaluate((node) => ({
    text: (node.textContent || '').replace(/\s+/g, ' ').trim(),
    action: node.getAttribute('data-v270-action') || '',
    id: node.getAttribute('data-id') || '',
    aria: node.getAttribute('aria-label') || '',
  }));
  return {
    ...meta,
    input_value: await page.locator('#v270-search-input').inputValue(),
    result_text: clean(await result.innerText()),
    action_width: box?.width || 0,
    action_height: box?.height || 0,
    overflow: await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth),
  };
}

try {
  await page.goto(`${base}/setup.php`, { waitUntil: 'domcontentloaded' });
  await page.locator('#site_name').fill('VF Infra Domain Search Handoff Audit');
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

  report.domain_create = await createSyntheticDomain();
  assert(report.domain_create.id > 0, `synthetic domain id missing ${JSON.stringify(report.domain_create)}`);
  assert(report.domain_create.domain === query, `synthetic domain mismatch ${report.domain_create.domain}`);

  let current = await searchFromOverview();
  report.result = await inspectResult(current.result, current.action);
  assert(report.result.input_value === query, `search input lost query: ${report.result.input_value}`);
  assert(report.result.result_text.includes(query), `matching domain result missing: ${report.result.result_text}`);
  assert(report.result.action === 'open', `domain search result action mismatch ${report.result.action}`);
  assert(report.result.id.startsWith('domain:'), `domain search result id mismatch ${report.result.id}`);
  assert(report.result.action_height >= 40, `domain result action too short ${report.result.action_height}`);
  assert(report.result.action_width >= 44, `domain result action too narrow ${report.result.action_width}`);
  assert(report.result.overflow <= 1, `domain search result overflow ${report.result.overflow}`);

  await pointerClick(current.action);
  await page.waitForFunction(() => location.hash.startsWith('#domain/'), null, { timeout: 12000 });
  const heading = page.locator('#v270-app h1').first();
  await heading.waitFor({ state: 'visible', timeout: 15000 });
  report.result.detail_hash = await page.evaluate(() => location.hash);
  report.result.detail_h1 = clean(await heading.innerText());
  assert(report.result.detail_h1.includes(query), `domain detail h1 mismatch ${report.result.detail_h1}`);

  await page.goBack();
  await page.waitForFunction((hash) => location.hash === hash, expectedHash, { timeout: 12000 });
  const backResult = page.locator('.v270-search-result').filter({ hasText: query }).first();
  await backResult.waitFor({ state: 'visible', timeout: 15000 });
  report.browser_back = {
    hash: await page.evaluate(() => location.hash),
    input_value: await page.locator('#v270-search-input').inputValue(),
    result_text: clean(await backResult.innerText()),
    overflow: await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth),
  };
  assert(report.browser_back.input_value === query, `browser Back lost domain search input: ${report.browser_back.input_value}`);
  assert(report.browser_back.result_text.includes(query), 'browser Back lost domain result');
  assert(report.browser_back.overflow <= 1, `domain browser Back overflow ${report.browser_back.overflow}`);

  const actionAgain = backResult.locator('button:visible').first();
  await pointerClick(actionAgain);
  await page.waitForFunction(() => location.hash.startsWith('#domain/'), null, { timeout: 12000 });
  const backbar = page.locator('[data-v275-context-backbar]');
  await backbar.waitFor({ state: 'visible', timeout: 12000 });
  const contextButton = backbar.locator('[data-v275-go]').first();
  const target = await contextButton.getAttribute('data-v275-go');
  report.context_back.target = target || '';
  assert(target === expectedHash, `domain detail context return target mismatch ${target}`);
  const contextBox = await contextButton.boundingBox();
  report.context_back.action_width = contextBox?.width || 0;
  report.context_back.action_height = contextBox?.height || 0;
  assert(report.context_back.action_height >= 40, `domain context back too short ${report.context_back.action_height}`);
  assert(report.context_back.action_width >= 44, `domain context back too narrow ${report.context_back.action_width}`);
  await pointerClick(contextButton);
  await page.waitForFunction((hash) => location.hash === hash, expectedHash, { timeout: 12000 });
  const contextResult = page.locator('.v270-search-result').filter({ hasText: query }).first();
  await contextResult.waitFor({ state: 'visible', timeout: 15000 });
  report.context_back.hash = await page.evaluate(() => location.hash);
  report.context_back.input_value = await page.locator('#v270-search-input').inputValue();
  report.context_back.result_text = clean(await contextResult.innerText());
  report.context_back.overflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth);
  assert(report.context_back.input_value === query, `domain context Back lost search input: ${report.context_back.input_value}`);
  assert(report.context_back.result_text.includes(query), 'domain context Back lost matching result');
  assert(report.context_back.overflow <= 1, `domain context Back overflow ${report.context_back.overflow}`);
  await page.screenshot({ path: `${evidence}/domain-search-after-context-back.png`, fullPage: true, animations: 'disabled' });

  assert(report.page_errors.length === 0, `page errors ${JSON.stringify(report.page_errors)}`);
  assert(report.console_errors.length === 0, `console errors ${JSON.stringify(report.console_errors)}`);
  report.status = 'PASS';
} finally {
  fs.writeFileSync(`${evidence}/P04_MOBILE_DOMAIN_SEARCH_HANDOFF_AUDIT.json`, JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}

console.log(`P04_MOBILE_DOMAIN_SEARCH_HANDOFF_AUDIT=${report.status}`);
if (report.status !== 'PASS') process.exit(1);
