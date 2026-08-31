import { chromium } from 'playwright';
import fs from 'node:fs';

const base = process.env.VF_E2E_BASE_URL || 'http://127.0.0.1:19068';
const evidence = process.env.EVIDENCE;
const candidate = process.env.CANDIDATE;
if (!evidence || !candidate) throw new Error('mobile group dialog audit environment missing');
fs.mkdirSync(evidence, { recursive: true });

const password = 'Vf' + crypto.randomUUID().replaceAll('-', '') + 'Aa1';
const syntheticDomain = 'dialog-audit.example';
const report = {
  schema: 'p04-mobile-group-dialog-audit/v1',
  source_sha: candidate,
  status: 'FAIL',
  domain_create: {},
  trigger: {},
  dialog: {},
  controls: {},
  keyboard: {},
  focus: {},
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
  await locator.waitFor({ state: 'visible', timeout: 12000 });
  await locator.scrollIntoViewIfNeeded();
  await page.waitForTimeout(70);
  const box = await locator.boundingBox();
  if (!box || box.width <= 0 || box.height <= 0) throw new Error('dialog pointer target has no box');
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.waitForTimeout(35);
  await page.mouse.up();
}

const size = async (locator) => {
  const box = await locator.boundingBox();
  return { width: box?.width || 0, height: box?.height || 0 };
};

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
      project_name: 'Synthetic Dialog Audit',
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
      id: Number(saved.domain?.id || 0),
      domain: String(saved.domain?.domain || ''),
    };
  }, syntheticDomain);
}

async function openManager(trigger) {
  await pointerClick(trigger);
  const dialog = page.locator('.v275-dialog.v275-group-manager[role="dialog"]').first();
  await dialog.waitFor({ state: 'visible', timeout: 12000 });
  return dialog;
}

try {
  await page.goto(`${base}/setup.php`, { waitUntil: 'domcontentloaded' });
  await page.locator('#site_name').fill('VF Infra Mobile Dialog Audit');
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
  if ((await page.locator('meta[name="app-version"]').getAttribute('content')) !== '2.8.11') {
    throw new Error('version mismatch');
  }

  report.domain_create = await createSyntheticDomain();
  if (report.domain_create.id <= 0 || report.domain_create.domain !== syntheticDomain) {
    throw new Error(`synthetic domain create mismatch ${JSON.stringify(report.domain_create)}`);
  }

  await page.goto(`${base}/index.php?audit=${Date.now()}#domains`, { waitUntil: 'domcontentloaded' });
  const trigger = page.locator('[data-v275-manage-groups]').first();
  await trigger.waitFor({ state: 'visible', timeout: 15000 });
  report.trigger = { ...(await size(trigger)), text: (await trigger.innerText()).trim() };
  assert(report.trigger.height >= 40, `manage groups trigger too short ${report.trigger.height}`);
  assert(report.trigger.width >= 44, `manage groups trigger too narrow ${report.trigger.width}`);

  let dialog = await openManager(trigger);
  const dialogBox = await dialog.boundingBox();
  report.dialog = await dialog.evaluate((node) => ({
    role: node.getAttribute('role') || '',
    aria_modal: node.getAttribute('aria-modal') || '',
    labelledby: node.getAttribute('aria-labelledby') || '',
    client_height: node.clientHeight,
    scroll_height: node.scrollHeight,
  }));
  report.dialog.box = dialogBox;
  report.dialog.viewport_overflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth);
  report.focus.initial_inside = await dialog.evaluate((node) => node.contains(document.activeElement));

  const close = dialog.locator('[data-v275-dialog-close][aria-label="关闭"]').first();
  const createInput = dialog.locator('.v275-group-create input[name="name"]').first();
  const createButton = dialog.locator('.v275-group-create button[type="submit"]').first();
  const doneButton = dialog.locator('.v275-dialog-actions [data-v275-dialog-close]').last();
  report.controls.close = await size(close);
  report.controls.create_input = await size(createInput);
  report.controls.create_button = await size(createButton);
  report.controls.done_button = await size(doneButton);

  assert(report.dialog.role === 'dialog', `dialog role mismatch ${report.dialog.role}`);
  assert(report.dialog.aria_modal === 'true', `dialog aria-modal mismatch ${report.dialog.aria_modal}`);
  assert(Boolean(report.dialog.labelledby), 'dialog missing aria-labelledby');
  assert((dialogBox?.left || 0) >= -1, `dialog clips left ${dialogBox?.left}`);
  assert((dialogBox?.right || 0) <= 391, `dialog clips right ${dialogBox?.right}`);
  assert((dialogBox?.top || 0) >= -1, `dialog clips top ${dialogBox?.top}`);
  assert((dialogBox?.bottom || 0) <= 845, `dialog clips bottom ${dialogBox?.bottom}`);
  assert(report.dialog.viewport_overflow <= 1, `dialog page overflow ${report.dialog.viewport_overflow}`);
  assert(report.controls.close.height >= 40 && report.controls.close.width >= 40, `dialog close target too small ${JSON.stringify(report.controls.close)}`);
  assert(report.controls.create_input.height >= 40, `group create input too short ${report.controls.create_input.height}`);
  assert(report.controls.create_button.height >= 40 && report.controls.create_button.width >= 44, `group create button too small ${JSON.stringify(report.controls.create_button)}`);
  assert(report.controls.done_button.height >= 40 && report.controls.done_button.width >= 44, `dialog done button too small ${JSON.stringify(report.controls.done_button)}`);
  assert(report.focus.initial_inside, 'focus does not enter dialog after opening');

  await page.keyboard.press('Escape');
  await page.waitForTimeout(180);
  report.keyboard.escape_closed = (await page.locator('.v275-dialog.v275-group-manager').count()) === 0;
  assert(report.keyboard.escape_closed, 'Escape does not close group manager dialog');
  if (!report.keyboard.escape_closed) {
    await pointerClick(close);
    await page.locator('.v275-dialog.v275-group-manager').waitFor({ state: 'detached', timeout: 5000 });
  }

  report.focus.after_escape_or_close_on_trigger = await trigger.evaluate((node) => document.activeElement === node);

  dialog = await openManager(trigger);
  const closeAgain = dialog.locator('[data-v275-dialog-close][aria-label="关闭"]').first();
  await pointerClick(closeAgain);
  await page.locator('.v275-dialog.v275-group-manager').waitFor({ state: 'detached', timeout: 5000 });
  report.focus.after_close_button_on_trigger = await trigger.evaluate((node) => document.activeElement === node);
  assert(report.focus.after_close_button_on_trigger, 'focus does not return to Manage Groups trigger after closing dialog');

  await page.screenshot({ path: `${evidence}/mobile-domains-after-dialog-close.png`, fullPage: true, animations: 'disabled' });
  assert(report.page_errors.length === 0, `page errors ${JSON.stringify(report.page_errors)}`);
  assert(report.console_errors.length === 0, `console errors ${JSON.stringify(report.console_errors)}`);
  report.status = report.failures.length === 0 ? 'PASS' : 'FAIL';
} finally {
  fs.writeFileSync(`${evidence}/P04_MOBILE_GROUP_DIALOG_AUDIT.json`, JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}

console.log(`P04_MOBILE_GROUP_DIALOG_AUDIT=${report.status}`);
if (report.status !== 'PASS') {
  console.error(report.failures.join('\n'));
  process.exit(1);
}
