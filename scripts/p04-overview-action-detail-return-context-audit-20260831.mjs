import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';

const base = process.env.VF_E2E_BASE_URL || 'http://127.0.0.1:19076';
const webRoot = process.env.VF_E2E_WEB_ROOT || '';
const productRoot = process.env.VF_PRODUCT_ROOT || '';
const evidence = process.env.EVIDENCE || '';
const source = process.env.SOURCE || '';
if (!webRoot || !productRoot || !evidence || !source) throw new Error('overview action return audit environment missing');
fs.mkdirSync(evidence, { recursive: true });

const password = 'Vf' + crypto.randomUUID().replaceAll('-', '') + 'Aa1';
const report = {
  schema: 'p04-overview-action-detail-return-context-audit/v1',
  source_sha: source,
  status: 'FAIL',
  action_inventory: [],
  selected: {},
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
const assert = (ok, message) => { if (!ok) report.failures.push(message); };

async function stableBox(locator) {
  for (let i = 0; i < 8; i += 1) {
    try {
      await locator.waitFor({ state: 'visible', timeout: i === 0 ? 15000 : 2000 });
      await locator.scrollIntoViewIfNeeded();
      await page.waitForTimeout(50);
      const box = await locator.boundingBox();
      if (box && box.width > 0 && box.height > 0) return box;
    } catch (error) {
      if (i === 7) throw error;
      await page.waitForTimeout(75);
    }
  }
  return null;
}

async function pointerClick(locator) {
  const box = await stableBox(locator);
  if (!box) throw new Error('pointer target has no stable box');
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.waitForTimeout(35);
  await page.mouse.up();
}

async function visibleBackbar() {
  await page.waitForFunction(() => [...document.querySelectorAll('[data-v275-context-backbar] [data-v275-go]')]
    .some((node) => node.getClientRects().length > 0), null, { timeout: 15000 });
  const inventory = await page.evaluate(() => [...document.querySelectorAll('[data-v275-context-backbar] [data-v275-go]')].map((node, index) => {
    const rect = node.getBoundingClientRect();
    return {
      index,
      target: node.getAttribute('data-v275-go') || '',
      label: (node.textContent || '').trim(),
      visible: node.getClientRects().length > 0,
      width: rect.width,
      height: rect.height,
    };
  }));
  report.selected.backbar_inventory = inventory;
  const visible = inventory.filter((item) => item.visible).at(-1);
  if (!visible) throw new Error(`no visible backbar ${JSON.stringify(inventory)}`);
  return {
    locator: page.locator('[data-v275-context-backbar] [data-v275-go]:visible').last(),
    snapshot: visible,
  };
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

try {
  await page.goto(`${base}/setup.php`, { waitUntil: 'domcontentloaded' });
  await page.locator('#site_name').fill('VF Infra Overview Action Return Audit');
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

  const fixtureOutput = execFileSync('php', [`${productRoot}/tests/fixtures/v260-user-task-fixture.php`, webRoot], { encoding: 'utf8' });
  if (!fixtureOutput.includes('P04_V260_USER_TASK_FIXTURE_PASS')) throw new Error('V260 fixture marker missing');

  await page.goto('about:blank');
  await page.goto(`${base}/index.php?audit=${Date.now()}#overview`, { waitUntil: 'domcontentloaded' });
  await page.getByRole('heading', { name: '个人基础设施概览' }).waitFor({ state: 'visible', timeout: 15000 });
  await page.waitForTimeout(500);

  report.action_inventory = await page.locator('[data-v270-action="open"][data-id]').evaluateAll((nodes) => nodes.map((node, index) => ({
    index,
    text: (node.textContent || '').trim(),
    id: node.getAttribute('data-id') || '',
    visible: Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length),
  })));

  const recognized = report.action_inventory.find((item) => item.visible && /^(domain|provider|vps|server|dns):/.test(item.id));
  assert(Boolean(recognized), `no recognized visible overview open action: ${JSON.stringify(report.action_inventory)}`);
  if (!recognized) throw new Error('no recognized overview open action');

  const [kind] = recognized.id.split(':');
  const detailRoute = kind === 'vps' ? 'server' : kind;
  const action = page.locator('[data-v270-action="open"][data-id]').nth(recognized.index);
  await action.scrollIntoViewIfNeeded();
  await page.waitForTimeout(100);
  report.selected.open_spec = recognized.id;
  report.selected.action_text = recognized.text;
  report.selected.scroll_before = await page.evaluate(() => Math.round(scrollY));
  const actionBox = await stableBox(action);
  report.selected.action_button_size = { width: actionBox?.width || 0, height: actionBox?.height || 0 };
  report.selected.entry_overflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth);

  await page.evaluate(() => {
    for (const key of Object.keys(sessionStorage)) {
      if (key.startsWith('vf-infra-v275:return:')) sessionStorage.removeItem(key);
    }
  });
  await pointerClick(action);
  await page.waitForFunction((route) => location.hash.startsWith(`#${route}/`), detailRoute, { timeout: 10000 });
  report.selected.detail_hash = await page.evaluate(() => location.hash);
  report.selected.return_storage = await page.evaluate(() => Object.fromEntries(Object.entries(sessionStorage).filter(([key]) => key.startsWith('vf-infra-v275:return:') || key === 'vf-infra-v275:scroll:overview')));

  const back = await visibleBackbar();
  const backBox = await stableBox(back.locator);
  report.selected.back_target = back.snapshot.target;
  report.selected.back_label = back.snapshot.label;
  report.selected.back_button_size = { width: backBox?.width || back.snapshot.width || 0, height: backBox?.height || back.snapshot.height || 0 };
  report.selected.detail_overflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth);

  if (report.selected.back_target !== '#overview') report.findings.push({ severity: 'ux', issue: 'overview_action_returns_to_default_route', open_spec: recognized.id, observed: report.selected.back_target });
  if (!/概览/.test(report.selected.back_label)) report.findings.push({ severity: 'copy', issue: 'overview_action_return_label_not_overview', observed: report.selected.back_label });
  if (report.selected.scroll_before >= 300 && !('vf-infra-v275:scroll:overview' in report.selected.return_storage)) report.findings.push({ severity: 'ux', issue: 'overview_action_scroll_not_recorded', scroll_before: report.selected.scroll_before });

  await pointerClick(back.locator);
  await page.waitForTimeout(250);
  report.selected.hash_after_return = await page.evaluate(() => location.hash);
  report.selected.return_timeline = await returnTimeline();
  report.selected.scroll_after = report.selected.return_timeline.at(-1)?.y ?? 0;
  report.selected.scroll_delta = report.selected.scroll_after - report.selected.scroll_before;
  report.selected.context_position_preserved = report.selected.hash_after_return === '#overview' && (report.selected.scroll_before < 300 || Math.abs(report.selected.scroll_delta) <= 120);
  if (!report.selected.context_position_preserved) report.findings.push({ severity: 'ux', issue: 'overview_action_return_context_lost', hash_after_return: report.selected.hash_after_return, scroll_before: report.selected.scroll_before, scroll_after: report.selected.scroll_after });

  assert(report.selected.action_button_size.height >= 40, `overview open action target under 40px ${JSON.stringify(report.selected.action_button_size)}`);
  assert(report.selected.back_button_size.height >= 40, `detail back target under 40px ${JSON.stringify(report.selected.back_button_size)}`);
  assert(report.selected.entry_overflow <= 1 && report.selected.detail_overflow <= 1, 'overflow detected');
  assert(report.page_errors.length === 0, `page errors ${JSON.stringify(report.page_errors)}`);
  assert(report.console_errors.length === 0, `console errors ${JSON.stringify(report.console_errors)}`);
  report.status = report.failures.length === 0 ? 'PASS' : 'FAIL';

  await page.screenshot({ path: `${evidence}/mobile-overview-open-action-after-return.png`, fullPage: true, animations: 'disabled' });
} finally {
  fs.writeFileSync(`${evidence}/P04_OVERVIEW_ACTION_DETAIL_RETURN_CONTEXT_AUDIT.json`, JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}

console.log(`P04_OVERVIEW_ACTION_DETAIL_RETURN_CONTEXT_AUDIT=${report.status}`);
if (report.findings.length) console.log(`P04_OVERVIEW_ACTION_RETURN_FINDINGS=${JSON.stringify(report.findings)}`);
if (report.status !== 'PASS') {
  console.error(report.failures.join('\n'));
  process.exit(1);
}
