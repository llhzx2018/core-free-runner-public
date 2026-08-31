import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';

const base = process.env.VF_E2E_BASE_URL || 'http://127.0.0.1:19071';
const webRoot = process.env.VF_E2E_WEB_ROOT || '';
const evidence = process.env.EVIDENCE || '';
const source = process.env.SOURCE || '';
if (!webRoot || !evidence || !source) throw new Error('server/provider return audit environment missing');
fs.mkdirSync(evidence, { recursive: true });

const password = 'Vf' + crypto.randomUUID().replaceAll('-', '') + 'Aa1';
const report = {
  schema: 'p04-server-provider-detail-return-context-audit/v1',
  source_sha: source,
  status: 'FAIL',
  seed: {},
  server: {},
  provider: {},
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

async function cold(hash) {
  await page.goto('about:blank');
  await page.goto(`${base}/index.php?audit=${Date.now()}#${hash}`, { waitUntil: 'domcontentloaded' });
  await page.locator('[data-v275-query]').first().waitFor({ state: 'visible', timeout: 15000 });
  await page.waitForTimeout(180);
}

async function timeline(listKey, bucket, label) {
  const snap = await page.evaluate(({ listKey, label }) => ({
    label,
    hash: location.hash,
    scroll_y: window.scrollY,
    scroll_height: Math.max(document.documentElement.scrollHeight, document.body.scrollHeight),
    inner_height: innerHeight,
    stored_scroll: sessionStorage.getItem(`vf-infra-v275:scroll:${listKey}`),
  }), { listKey, label });
  bucket.timeline.push(snap);
}

async function auditList(config) {
  const bucket = report[config.reportKey];
  bucket.timeline = [];
  await cold(config.listKey);

  const query = page.locator('[data-v275-query]').first();
  await query.fill(config.query);
  await page.waitForTimeout(180);
  bucket.query_before = await query.inputValue();
  bucket.visible_before = await page.locator(config.visibleSelector).count();
  assert(bucket.query_before === config.query, `${config.listKey}: query not applied ${bucket.query_before}`);
  assert(bucket.visible_before === 14, `${config.listKey}: expected 14 visible synthetic rows/cards, got ${bucket.visible_before}`);

  const target = page.locator(config.targetSelector).filter({ hasText: config.targetName }).first();
  await target.waitFor({ state: 'visible', timeout: 15000 });
  await target.scrollIntoViewIfNeeded();
  await page.evaluate(() => window.scrollBy(0, -120));
  await page.waitForTimeout(100);
  bucket.scroll_before = await page.evaluate(() => window.scrollY);
  assert(bucket.scroll_before > 0, `${config.listKey}: target did not reach deep scroll position ${bucket.scroll_before}`);

  const action = target.locator(config.actionSelector).first();
  bucket.action_id = await action.getAttribute('data-id');
  assert(Boolean(bucket.action_id), `${config.listKey}: detail action id missing`);
  await pointerClick(action);
  await page.waitForFunction(({ detailKey, id }) => location.hash === `#${detailKey}/${id}`, { detailKey: config.detailKey, id: bucket.action_id }, { timeout: 10000 });
  bucket.detail_hash = await page.evaluate(() => location.hash);
  bucket.detail_name_visible = (await page.getByText(config.targetName, { exact: false }).count()) > 0;
  bucket.stored_on_detail = await page.evaluate((key) => sessionStorage.getItem(`vf-infra-v275:scroll:${key}`), config.listKey);
  assert(bucket.detail_name_visible, `${config.listKey}: target name not visible in detail`);
  assert(Number(bucket.stored_on_detail || 0) > 0, `${config.listKey}: V2.75 did not save list scroll`);

  const bar = page.locator('[data-v275-context-backbar]').first();
  await bar.waitFor({ state: 'visible', timeout: 10000 });
  const back = bar.locator(`[data-v275-go="#${config.listKey}"]`).first();
  await back.waitFor({ state: 'visible', timeout: 10000 });
  const box = await back.boundingBox();
  bucket.back_label = (await back.textContent() || '').trim();
  bucket.back_size = { width: box?.width || 0, height: box?.height || 0 };
  bucket.previous_count = await bar.getByText('上一条', { exact: false }).count();
  bucket.next_count = await bar.getByText('下一条', { exact: false }).count();
  bucket.detail_overflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth);
  assert(bucket.back_size.height >= 40 && bucket.back_size.width >= 52, `${config.listKey}: return button too small ${JSON.stringify(bucket.back_size)}`);
  assert(bucket.previous_count === 1, `${config.listKey}: previous detail control missing ${bucket.previous_count}`);
  assert(bucket.next_count === 1, `${config.listKey}: next detail control missing ${bucket.next_count}`);
  assert(bucket.detail_overflow <= 1, `${config.listKey}: detail overflow ${bucket.detail_overflow}`);

  await pointerClick(back);
  await page.waitForFunction((listKey) => location.hash === `#${listKey}`, config.listKey, { timeout: 10000 });
  await timeline(config.listKey, bucket, 'hash-list');
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(resolve)));
  await timeline(config.listKey, bucket, 'raf-1');
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(resolve)));
  await timeline(config.listKey, bucket, 'raf-2');
  await page.waitForTimeout(120);
  await timeline(config.listKey, bucket, 'plus-120ms');
  await page.waitForTimeout(230);
  await timeline(config.listKey, bucket, 'plus-350ms');

  const queryAfter = page.locator('[data-v275-query]').first();
  await queryAfter.waitFor({ state: 'visible', timeout: 10000 });
  bucket.query_after = await queryAfter.inputValue();
  bucket.visible_after = await page.locator(config.visibleSelector).count();
  bucket.scroll_after = await page.evaluate(() => window.scrollY);
  bucket.scroll_delta = Math.abs(bucket.scroll_after - bucket.scroll_before);
  bucket.list_overflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth);
  bucket.target_visible_after = await page.locator(config.targetSelector).filter({ hasText: config.targetName }).first().isVisible();

  assert(bucket.query_after === config.query, `${config.listKey}: query lost after return ${bucket.query_after}`);
  assert(bucket.visible_after === 14, `${config.listKey}: visible count changed after return ${bucket.visible_after}`);
  assert(bucket.target_visible_after, `${config.listKey}: target not visible after return`);
  assert(bucket.scroll_delta <= 140, `${config.listKey}: scroll not restored delta=${bucket.scroll_delta} before=${bucket.scroll_before} after=${bucket.scroll_after}`);
  assert(bucket.list_overflow <= 1, `${config.listKey}: list overflow ${bucket.list_overflow}`);

  await page.screenshot({ path: `${evidence}/mobile-${config.listKey}-after-detail-return.png`, fullPage: true, animations: 'disabled' });
}

try {
  await page.goto(`${base}/setup.php`, { waitUntil: 'domcontentloaded' });
  await page.locator('#site_name').fill('VF Infra Server Provider Return Audit');
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

  const seedOutput = execFileSync('php', ['scripts/p04-server-provider-return-seed-20260831.php', webRoot], { encoding: 'utf8' });
  if (!seedOutput.includes('P04_SERVER_PROVIDER_RETURN_FIXTURE_PASS')) throw new Error('synthetic seeder marker missing');
  const seedJson = seedOutput.split(/\r?\n/).find((line) => line.trim().startsWith('{'));
  report.seed = JSON.parse(seedJson || '{}');
  assert(report.seed.providers?.length === 14, `provider seed count ${report.seed.providers?.length}`);
  assert(report.seed.servers?.length === 14, `server seed count ${report.seed.servers?.length}`);

  await auditList({
    reportKey: 'server', listKey: 'servers', detailKey: 'server', query: 'return-server',
    targetName: 'return-server-10', targetSelector: '.server-card', visibleSelector: '.server-card:visible',
    actionSelector: '[data-v270-action="server"]',
  });

  await auditList({
    reportKey: 'provider', listKey: 'providers', detailKey: 'provider', query: 'Return Audit Provider',
    targetName: 'Return Audit Provider 10', targetSelector: '.v271-provider-account', visibleSelector: '.v271-provider-account:visible',
    actionSelector: '[data-v271-action="provider-open"]',
  });

  assert(report.page_errors.length === 0, `page errors ${JSON.stringify(report.page_errors)}`);
  assert(report.console_errors.length === 0, `console errors ${JSON.stringify(report.console_errors)}`);
  report.status = report.failures.length === 0 ? 'PASS' : 'FAIL';
} finally {
  fs.writeFileSync(`${evidence}/P04_SERVER_PROVIDER_DETAIL_RETURN_CONTEXT_AUDIT.json`, JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}

console.log(`P04_SERVER_PROVIDER_DETAIL_RETURN_CONTEXT_AUDIT=${report.status}`);
if (report.status !== 'PASS') {
  console.error(report.failures.join('\n'));
  process.exit(1);
}
