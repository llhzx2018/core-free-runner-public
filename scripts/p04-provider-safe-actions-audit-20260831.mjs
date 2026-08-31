import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';

const base = process.env.VF_E2E_BASE_URL || 'http://127.0.0.1:19080';
const evidence = process.env.EVIDENCE || '';
const source = process.env.SOURCE || '';
const web = process.env.WEB || '';
const seedHelper = process.env.SEED_HELPER || '';
if (!evidence || !source || !web || !seedHelper) throw new Error('provider safe actions gate environment missing');
fs.mkdirSync(evidence, { recursive: true });

const password = 'Vf' + crypto.randomUUID().replaceAll('-', '') + 'Aa1';
const report = {
  schema: 'p04-provider-safe-actions-gate/v1',
  source_sha: source,
  status: 'FAIL',
  synthetic_test_data_only: true,
  browser_intercept_only_for_provider_posts: true,
  external_provider_api_called: false,
  production_actions_executed: false,
  seed: null,
  intercepted_posts: {},
  views: {},
  failures: [],
  page_errors: [],
  console_errors: [],
};
const viewports = { desktop: { width: 1440, height: 900 }, mobile: { width: 390, height: 844 } };
const intercepted = new Set([
  'provider_accounts_sync_all',
  'provider_billings_sync_all',
  'provider_account_sync',
  'provider_account_probe',
  'provider_account_save',
]);

function fail(message) { report.failures.push(message); }
function delay(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: viewports.desktop });
const page = await context.newPage();
page.on('pageerror', (e) => report.page_errors.push(String(e?.stack || e)));
page.on('console', (m) => { if (m.type() === 'error') report.console_errors.push(m.text()); });

await page.route('**/api.php?*', async (route) => {
  const request = route.request();
  const url = new URL(request.url());
  const action = url.searchParams.get('action') || '';
  if (request.method() !== 'POST' || !intercepted.has(action)) return route.continue();
  report.intercepted_posts[action] = Number(report.intercepted_posts[action] || 0) + 1;
  if (['provider_accounts_sync_all', 'provider_billings_sync_all', 'provider_account_sync'].includes(action)) await delay(900);
  let payload = { ok: true, message: 'Synthetic intercepted provider action complete.' };
  if (action === 'provider_accounts_sync_all' || action === 'provider_billings_sync_all') payload.summary = { failed: 0 };
  if (action === 'provider_account_sync') payload.sync = { status: 'success' };
  if (action === 'provider_account_probe') payload.probe = { accounts: [{ external_account_id: 'synthetic-external-account', display_name: 'Synthetic account' }] };
  if (action === 'provider_account_save') payload.sync = { status: 'success' };
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payload) });
});

async function pointerClick(locator) {
  await locator.waitFor({ state: 'visible', timeout: 15000 });
  await locator.scrollIntoViewIfNeeded();
  await page.waitForTimeout(60);
  const box = await locator.boundingBox();
  if (!box || box.width <= 0 || box.height <= 0) throw new Error('pointer target has no visible box');
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.waitForTimeout(30);
  await page.mouse.up();
  return box;
}

async function installAndLogin() {
  await page.goto(`${base}/setup.php`, { waitUntil: 'domcontentloaded' });
  await page.locator('#site_name').fill('VF Infra Provider Safe Actions Gate');
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

function seedSyntheticData() {
  const output = execFileSync('php', [seedHelper, web], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).trim();
  const seed = JSON.parse(output);
  report.seed = seed;
  if (seed.status !== 'PASS' || seed.synthetic_only !== true || seed.external_provider_api_called !== false) throw new Error(`seed contract failed: ${output}`);
  return seed;
}

async function go(hash) {
  await page.evaluate((target) => { location.hash = target; }, hash);
  await page.waitForFunction((target) => location.hash === target, hash, { timeout: 10000 });
  await page.waitForTimeout(500);
}

async function overflowX() {
  return page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth);
}

async function inspectConnectBoundary(viewportName, result) {
  const trigger = page.locator('[data-v271-action="provider-connect"]').first();
  const triggerBox = await trigger.boundingBox();
  result.connect = { trigger_height: triggerBox?.height || 0 };
  if (viewportName === 'mobile' && (!triggerBox || triggerBox.height < 40)) fail(`${viewportName}: connect trigger under 40px`);
  await pointerClick(trigger);
  const modal = page.locator('#v271-modal[role="dialog"]');
  await modal.waitFor({ state: 'visible', timeout: 15000 });
  const title = (await modal.getByRole('heading', { name: '连接基础设施账号', exact: true }).textContent() || '').trim();
  const help = (await modal.locator('.v271-help').textContent() || '').replace(/\s+/g, ' ').trim();
  const secret = modal.locator('input[name="secret"]');
  const probe = modal.locator('[data-v271-action="provider-probe"]');
  const submit = modal.locator('button[type="submit"][form="v271-provider-connect"]');
  const probeBox = await probe.boundingBox();
  const submitBox = await submit.boundingBox();
  result.connect = {
    ...result.connect,
    title,
    readonly_copy: /Read-only First/i.test(help),
    secret_type: await secret.getAttribute('type'),
    probe_label: (await probe.textContent() || '').trim(),
    submit_label: (await submit.textContent() || '').trim(),
    probe_height: probeBox?.height || 0,
    submit_height: submitBox?.height || 0,
    modal_overflow_x: await overflowX(),
  };
  if (!result.connect.readonly_copy) fail(`${viewportName}: provider connect modal missing Read-only First boundary copy`);
  if (result.connect.secret_type !== 'password') fail(`${viewportName}: provider credential input is not password type`);
  if (result.connect.probe_label !== '验证连接') fail(`${viewportName}: probe label mismatch`);
  if (result.connect.submit_label !== '连接并首次同步') fail(`${viewportName}: connection submit label mismatch`);
  if (result.connect.modal_overflow_x > 1) fail(`${viewportName}: connect modal horizontal overflow ${result.connect.modal_overflow_x}`);
  if (viewportName === 'mobile' && ((!probeBox || probeBox.height < 40) || (!submitBox || submitBox.height < 40))) fail(`${viewportName}: connect modal action under 40px`);

  const close = modal.locator('[data-v271-action="close-modal"]').first();
  await pointerClick(close);
  await modal.waitFor({ state: 'hidden', timeout: 10000 });
  const focused = await trigger.evaluate((node) => document.activeElement === node);
  result.connect.focus_returned = focused;
  if (!focused) fail(`${viewportName}: closing provider connect modal did not restore trigger focus`);
}

async function inspectLongAction(viewportName, actionName, apiAction, expectedFeedback, result) {
  const button = page.locator(`[data-v271-action="${actionName}"]`).first();
  await button.waitFor({ state: 'visible', timeout: 15000 });
  const box = await button.boundingBox();
  if (viewportName === 'mobile' && (!box || box.height < 40)) fail(`${viewportName}:${actionName}: action under 40px`);
  const before = Number(report.intercepted_posts[apiAction] || 0);
  await pointerClick(button);
  await page.waitForTimeout(150);
  const during = {
    disabled: await button.isDisabled(),
    aria_busy: await button.getAttribute('aria-busy'),
    feedback_visible: await page.locator('.v284-operation-feedback:not([hidden])').count() > 0,
    feedback_title: (await page.locator('.v284-operation-feedback [data-v284-title]').textContent().catch(() => '') || '').trim(),
  };
  if (!during.disabled) fail(`${viewportName}:${actionName}: trigger not disabled while request is pending`);
  if (during.aria_busy !== 'true') fail(`${viewportName}:${actionName}: trigger missing aria-busy while request is pending`);
  if (!during.feedback_visible) fail(`${viewportName}:${actionName}: long-action feedback not visible`);
  if (during.feedback_title !== expectedFeedback) fail(`${viewportName}:${actionName}: feedback title mismatch: ${during.feedback_title}`);

  // A second real pointer attempt must not create another provider request.
  if (!(await button.isDisabled())) await pointerClick(button);
  else await button.click({ force: true }).catch(() => {});
  await page.waitForTimeout(1050);
  const after = Number(report.intercepted_posts[apiAction] || 0);
  const requestDelta = after - before;
  const enabledAfter = !(await button.isDisabled());
  result[actionName] = { height: box?.height || 0, during, request_delta: requestDelta, enabled_after: enabledAfter };
  if (requestDelta !== 1) fail(`${viewportName}:${actionName}: expected one intercepted POST, got ${requestDelta}`);
  if (!enabledAfter) fail(`${viewportName}:${actionName}: trigger did not re-enable after completion`);
}

async function inspectAccountSync(viewportName, seed, result) {
  const button = page.locator(`[data-v271-action="provider-sync"][data-id="${seed.provider_account_id}"]`).first();
  await button.waitFor({ state: 'visible', timeout: 15000 });
  const box = await button.boundingBox();
  if (viewportName === 'mobile' && (!box || box.height < 40)) fail(`${viewportName}: account sync under 40px`);
  const before = Number(report.intercepted_posts.provider_account_sync || 0);
  await pointerClick(button);
  await page.waitForTimeout(150);
  const during = { disabled: await button.isDisabled(), label: (await button.textContent() || '').trim() };
  if (!during.disabled) fail(`${viewportName}: account sync trigger not disabled while pending`);
  if (during.label !== '同步中…') fail(`${viewportName}: account sync pending label mismatch: ${during.label}`);
  await page.waitForTimeout(1050);
  const after = Number(report.intercepted_posts.provider_account_sync || 0);
  result.account_sync = { height: box?.height || 0, during, request_delta: after - before };
  if (after - before !== 1) fail(`${viewportName}: account sync expected one intercepted POST, got ${after - before}`);
}

async function inspectProviders(viewportName, seed) {
  await go('#providers');
  await page.getByRole('heading', { name: '服务商', exact: true }).waitFor({ state: 'visible', timeout: 15000 });
  const result = { overflow_x: await overflowX() };
  report.views[viewportName] = result;
  if (result.overflow_x > 1) fail(`${viewportName}: providers horizontal overflow ${result.overflow_x}`);
  const labels = await page.locator('.v271-page-actions button').allTextContents();
  result.page_action_labels = labels.map((x) => x.trim());
  for (const expected of ['连接新账号', '全部资产同步', '全部费用同步']) if (!result.page_action_labels.includes(expected)) fail(`${viewportName}: missing provider page action ${expected}`);

  await inspectConnectBoundary(viewportName, result);
  await inspectLongAction(viewportName, 'provider-sync-all', 'provider_accounts_sync_all', '正在同步全部资产', result);
  await inspectLongAction(viewportName, 'billing-sync-all', 'provider_billings_sync_all', '正在同步全部费用', result);
  await inspectAccountSync(viewportName, seed, result);
  result.post_actions_overflow_x = await overflowX();
  if (result.post_actions_overflow_x > 1) fail(`${viewportName}: providers post-action horizontal overflow ${result.post_actions_overflow_x}`);
  await page.screenshot({ path: `${evidence}/${viewportName}-provider-safe-actions.png`, fullPage: true, animations: 'disabled' });
}

try {
  await installAndLogin();
  const seed = seedSyntheticData();
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(600);
  for (const [viewportName, viewport] of Object.entries(viewports)) {
    await page.setViewportSize(viewport);
    await inspectProviders(viewportName, seed);
  }
  if (report.page_errors.length) fail(`page errors: ${JSON.stringify(report.page_errors)}`);
  if (report.console_errors.length) fail(`console errors: ${JSON.stringify(report.console_errors)}`);
  report.status = report.failures.length === 0 ? 'PASS' : 'FAIL';
} catch (error) {
  fail(String(error?.stack || error));
  report.status = 'FAIL';
} finally {
  fs.writeFileSync(`${evidence}/P04_PROVIDER_SAFE_ACTIONS_AUDIT.json`, JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}

console.log(`P04_PROVIDER_SAFE_ACTIONS_GATE=${report.status}`);
if (report.failures.length) console.error(report.failures.join('\n'));
if (report.status !== 'PASS') process.exit(1);
