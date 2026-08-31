import { chromium } from 'playwright';
import fs from 'node:fs';

const base = process.env.VF_E2E_BASE_URL || 'http://127.0.0.1:19069';
const evidence = process.env.EVIDENCE;
const candidate = process.env.CANDIDATE;
if (!evidence || !candidate) throw new Error('domain group assignment audit environment missing');
fs.mkdirSync(evidence, { recursive: true });

const password = 'Vf' + crypto.randomUUID().replaceAll('-', '') + 'Aa1';
const syntheticDomain = 'assignment-dialog-audit.example';
const report = {
  schema: 'p04-mobile-domain-group-assignment-audit/v1',
  source_sha: candidate,
  status: 'FAIL',
  domain_create: {},
  more_trigger: {},
  quick_menu: {},
  dialog: {},
  controls: {},
  focus: {},
  keyboard: {},
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
const size = async (locator) => {
  const box = await locator.boundingBox();
  return { width: box?.width || 0, height: box?.height || 0 };
};

async function pointerClick(locator) {
  await locator.waitFor({ state: 'visible', timeout: 12000 });
  await locator.scrollIntoViewIfNeeded();
  await page.waitForTimeout(70);
  const box = await locator.boundingBox();
  if (!box || box.width <= 0 || box.height <= 0) throw new Error('pointer target has no box');
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.waitForTimeout(35);
  await page.mouse.up();
}

async function createSyntheticDomain() {
  return await page.evaluate(async (domain) => {
    const bootstrapRes = await fetch('api.php?action=bootstrap', {
      credentials: 'same-origin', headers: { Accept: 'application/json' },
    });
    const bootstrap = await bootstrapRes.json();
    if (!bootstrapRes.ok || bootstrap.ok === false || !bootstrap.csrf) throw new Error('bootstrap csrf unavailable');
    const body = new URLSearchParams({
      domain,
      registrar: 'Namecheap',
      currency: 'USD',
      renewal_price: '18.50',
      renewal_policy: 'manual',
      manual_expiry_date: '2026-09-18',
      project_name: 'Synthetic Assignment Dialog Audit',
      notes: 'Fresh isolated synthetic test data only',
    });
    const saveRes = await fetch('api.php?action=domain_save', {
      method: 'POST', credentials: 'same-origin',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
        'X-CSRF-Token': bootstrap.csrf,
      },
      body: body.toString(),
    });
    const saved = await saveRes.json();
    if (!saveRes.ok || saved.ok === false) throw new Error(saved.message || 'domain_save failed');
    return { id: Number(saved.domain?.id || 0), domain: String(saved.domain?.domain || '') };
  }, syntheticDomain);
}

async function domainCardAndMore() {
  const card = page.locator('.domain-card').filter({ hasText: syntheticDomain }).first();
  await card.waitFor({ state: 'visible', timeout: 15000 });
  const more = card.locator('[data-v275-domain-actions]').first();
  await more.waitFor({ state: 'visible', timeout: 10000 });
  return { card, more };
}

async function openQuickMenu(more) {
  await pointerClick(more);
  const menu = page.locator('.v275-quick-menu[role="menu"]').first();
  await menu.waitFor({ state: 'visible', timeout: 10000 });
  const group = menu.locator('[role="menuitem"][data-action="group"]').first();
  await group.waitFor({ state: 'visible', timeout: 10000 });
  return { menu, group };
}

async function openAssignmentDialog(more) {
  const { group } = await openQuickMenu(more);
  await pointerClick(group);
  const dialog = page.locator('.v275-dialog[role="dialog"]:not(.v275-group-manager)').filter({ hasText: '加入分组' }).first();
  await dialog.waitFor({ state: 'visible', timeout: 10000 });
  return dialog;
}

try {
  await page.goto(`${base}/setup.php`, { waitUntil: 'domcontentloaded' });
  await page.locator('#site_name').fill('VF Infra Assignment Dialog Audit');
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
  if ((await page.locator('meta[name="app-version"]').getAttribute('content')) !== '2.8.11') throw new Error('version mismatch');

  report.domain_create = await createSyntheticDomain();
  if (report.domain_create.id <= 0 || report.domain_create.domain !== syntheticDomain) throw new Error('synthetic domain create mismatch');

  await page.goto(`${base}/index.php?audit=${Date.now()}#domains`, { waitUntil: 'domcontentloaded' });
  let { more } = await domainCardAndMore();
  report.more_trigger = await size(more);
  assert(report.more_trigger.height >= 40, `domain more trigger too short ${report.more_trigger.height}`);
  assert(report.more_trigger.width >= 44, `domain more trigger too narrow ${report.more_trigger.width}`);

  let quick = await openQuickMenu(more);
  report.quick_menu.group_item = await size(quick.group);
  report.quick_menu.initial_focus_on_first_item = await quick.group.evaluate((node) => document.activeElement === node);
  report.quick_menu.overflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth);
  assert(report.quick_menu.group_item.height >= 40, `quick-menu group item too short ${report.quick_menu.group_item.height}`);
  assert(report.quick_menu.group_item.width >= 44, `quick-menu group item too narrow ${report.quick_menu.group_item.width}`);
  assert(report.quick_menu.initial_focus_on_first_item, 'quick menu does not focus first item');
  assert(report.quick_menu.overflow <= 1, `quick menu viewport overflow ${report.quick_menu.overflow}`);

  await page.keyboard.press('Escape');
  await page.waitForTimeout(100);
  report.keyboard.quick_menu_escape_closed = (await page.locator('.v275-quick-menu').count()) === 0;
  report.focus.after_quick_menu_escape_on_more = await more.evaluate((node) => document.activeElement === node);
  assert(report.keyboard.quick_menu_escape_closed, 'Escape does not close quick menu');
  assert(report.focus.after_quick_menu_escape_on_more, 'focus does not return to domain more trigger after quick-menu Escape');

  let dialog = await openAssignmentDialog(more);
  const dialogBox = await dialog.boundingBox();
  report.dialog = await dialog.evaluate((node) => ({
    role: node.getAttribute('role') || '',
    aria_modal: node.getAttribute('aria-modal') || '',
    labelledby: node.getAttribute('aria-labelledby') || '',
    client_height: node.clientHeight,
    scroll_height: node.scrollHeight,
    initial_focus_inside: node.contains(document.activeElement),
  }));
  report.dialog.box = dialogBox;
  report.dialog.overflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth);

  const close = dialog.locator('[data-v275-dialog-close][aria-label="关闭"]').first();
  const select = dialog.locator('select[name="group_id"]').first();
  const input = dialog.locator('input[name="new_group"]').first();
  const cancel = dialog.locator('.v275-dialog-actions [data-v275-dialog-close]').first();
  const save = dialog.locator('.v275-dialog-actions button[type="submit"]').first();
  report.controls.close = await size(close);
  report.controls.select = await size(select);
  report.controls.input = await size(input);
  report.controls.cancel = await size(cancel);
  report.controls.save = await size(save);

  assert(report.dialog.role === 'dialog', `assignment dialog role mismatch ${report.dialog.role}`);
  assert(report.dialog.aria_modal === 'true', `assignment dialog aria-modal mismatch ${report.dialog.aria_modal}`);
  assert(Boolean(report.dialog.labelledby), 'assignment dialog missing aria-labelledby');
  assert((dialogBox?.left || 0) >= -1 && (dialogBox?.right || 0) <= 391, 'assignment dialog horizontal clipping');
  assert((dialogBox?.top || 0) >= -1 && (dialogBox?.bottom || 0) <= 845, 'assignment dialog vertical clipping');
  assert(report.dialog.overflow <= 1, `assignment dialog viewport overflow ${report.dialog.overflow}`);
  assert(report.dialog.initial_focus_inside, 'focus does not enter assignment dialog');
  assert(report.controls.close.height >= 40 && report.controls.close.width >= 40, `assignment close too small ${JSON.stringify(report.controls.close)}`);
  assert(report.controls.select.height >= 40, `assignment select too short ${report.controls.select.height}`);
  assert(report.controls.input.height >= 40, `assignment input too short ${report.controls.input.height}`);
  assert(report.controls.cancel.height >= 40 && report.controls.cancel.width >= 44, `assignment cancel too small ${JSON.stringify(report.controls.cancel)}`);
  assert(report.controls.save.height >= 40 && report.controls.save.width >= 44, `assignment save too small ${JSON.stringify(report.controls.save)}`);

  await page.keyboard.press('Escape');
  await page.waitForTimeout(100);
  report.keyboard.dialog_escape_closed = (await page.locator('.v275-dialog[role="dialog"]:not(.v275-group-manager)').count()) === 0;
  assert(report.keyboard.dialog_escape_closed, 'Escape does not close assignment dialog');
  if (!report.keyboard.dialog_escape_closed) {
    await pointerClick(close);
    await page.locator('.v275-dialog[role="dialog"]:not(.v275-group-manager)').waitFor({ state: 'detached', timeout: 5000 });
  }
  more = (await domainCardAndMore()).more;
  report.focus.after_dialog_escape_or_close_on_more = await more.evaluate((node) => document.activeElement === node);
  assert(report.focus.after_dialog_escape_or_close_on_more, 'focus does not return to domain more trigger after dialog Escape/close');

  dialog = await openAssignmentDialog(more);
  const closeAgain = dialog.locator('[data-v275-dialog-close][aria-label="关闭"]').first();
  await pointerClick(closeAgain);
  await page.locator('.v275-dialog[role="dialog"]:not(.v275-group-manager)').waitFor({ state: 'detached', timeout: 5000 });
  more = (await domainCardAndMore()).more;
  report.focus.after_explicit_close_on_more = await more.evaluate((node) => document.activeElement === node);
  assert(report.focus.after_explicit_close_on_more, 'focus does not return to domain more trigger after explicit assignment-dialog close');

  await page.screenshot({ path: `${evidence}/mobile-domain-after-assignment-dialog-close.png`, fullPage: true, animations: 'disabled' });
  assert(report.page_errors.length === 0, `page errors ${JSON.stringify(report.page_errors)}`);
  assert(report.console_errors.length === 0, `console errors ${JSON.stringify(report.console_errors)}`);
  report.status = report.failures.length === 0 ? 'PASS' : 'FAIL';
} finally {
  fs.writeFileSync(`${evidence}/P04_MOBILE_DOMAIN_GROUP_ASSIGNMENT_AUDIT.json`, JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}

console.log(`P04_MOBILE_DOMAIN_GROUP_ASSIGNMENT_AUDIT=${report.status}`);
if (report.status !== 'PASS') {
  console.error(report.failures.join('\n'));
  process.exit(1);
}
