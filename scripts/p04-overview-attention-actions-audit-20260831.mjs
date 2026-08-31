import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';

const base = process.env.VF_E2E_BASE_URL || 'http://127.0.0.1:19080';
const evidence = process.env.EVIDENCE || '';
const source = process.env.SOURCE || '';
const web = process.env.WEB || '';
const seedHelper = process.env.SEED_HELPER || '';
if (!evidence || !source || !web || !seedHelper) throw new Error('overview attention gate environment missing');
fs.mkdirSync(evidence, { recursive: true });

const password = 'Vf' + crypto.randomUUID().replaceAll('-', '') + 'Aa1';
const report = {
  schema: 'p04-overview-attention-actions-gate/v1',
  source_sha: source,
  status: 'FAIL',
  synthetic_test_data_only: true,
  external_provider_api_called: false,
  production_actions_executed: false,
  seed: null,
  views: {},
  failures: [],
  page_errors: [],
  console_errors: [],
};
const viewports = { desktop: { width: 1440, height: 900 }, mobile: { width: 390, height: 844 } };

function fail(message) { report.failures.push(message); }

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: viewports.desktop });
const page = await context.newPage();
page.on('pageerror', (e) => report.page_errors.push(String(e?.stack || e)));
page.on('console', (m) => { if (m.type() === 'error') report.console_errors.push(m.text()); });

async function pointerClick(locator) {
  await locator.waitFor({ state: 'visible', timeout: 15000 });
  await locator.scrollIntoViewIfNeeded();
  await page.waitForTimeout(80);
  const box = await locator.boundingBox();
  if (!box || box.width <= 0 || box.height <= 0) throw new Error('pointer target has no visible box');
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.waitForTimeout(35);
  await page.mouse.up();
  return box;
}

async function installAndLogin() {
  await page.goto(`${base}/setup.php`, { waitUntil: 'domcontentloaded' });
  await page.locator('#site_name').fill('VF Infra Overview Attention Gate');
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

async function go(hash) {
  await page.evaluate((target) => { location.hash = target; }, hash);
  await page.waitForFunction((target) => location.hash === target, hash, { timeout: 10000 });
  await page.waitForTimeout(500);
}

async function overflowX() {
  return page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth);
}

function seedSyntheticData() {
  const output = execFileSync('php', [seedHelper, web], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).trim();
  const seed = JSON.parse(output);
  report.seed = seed;
  if (seed.status !== 'PASS' || seed.synthetic_only !== true || seed.external_provider_api_called !== false) throw new Error(`seed contract failed: ${output}`);
  return seed;
}

async function inspectOverview(viewportName, seed) {
  await go('#overview');
  await page.getByRole('heading', { name: '个人基础设施概览', exact: true }).waitFor({ state: 'visible', timeout: 15000 });
  const panel = page.locator('.v270-ref-panel').filter({ has: page.getByRole('heading', { name: '需要我处理', exact: true }) }).first();
  await panel.waitFor({ state: 'visible', timeout: 15000 });
  const cards = panel.locator('.v270-ref-action');
  const cardCount = await cards.count();
  const sub = (await panel.locator('.v270-section-sub').textContent() || '').trim();
  const overflow = await overflowX();

  const expected = [
    { key: `domain:${seed.domain_id}`, hash: `#domain/${seed.domain_id}`, kind: 'domain', title: 'attention.example 即将到期' },
    { key: `provider:${seed.provider_account_id}`, hash: `#provider/${seed.provider_account_id}`, kind: 'provider', title: 'Vultr 资产同步异常' },
    { key: `vps:${seed.server_id}`, hash: `#server/${seed.server_id}`, kind: 'vps', title: 'attention-server VPS 状态异常' },
  ];

  const result = { card_count: cardCount, summary: sub, overflow_x: overflow, actions: {} };
  report.views[viewportName] = result;
  if (cardCount !== 3) fail(`${viewportName}: expected exactly 3 attention cards, got ${cardCount}`);
  if (sub !== '3 项需要确认或处理') fail(`${viewportName}: attention summary not polished: ${sub}`);
  if (overflow > 1) fail(`${viewportName}: overview horizontal overflow ${overflow}`);

  for (const item of expected) {
    const titleCount = await panel.getByRole('heading', { name: item.title, exact: true }).count();
    if (titleCount !== 1) fail(`${viewportName}:${item.kind}: expected attention title missing/duplicated (${titleCount})`);
    const button = panel.locator(`[data-v270-action="open"][data-id="${item.key}"]`).first();
    await button.waitFor({ state: 'visible', timeout: 15000 });
    const label = (await button.textContent() || '').trim();
    const box = await button.boundingBox();
    result.actions[item.kind] = { data_id: item.key, label, height: box?.height || 0, detail_hash: '', return_label: '', returned_hash: '' };
    if (!label) fail(`${viewportName}:${item.kind}: owner action label empty`);
    if (viewportName === 'mobile' && (!box || box.height < 40)) fail(`${viewportName}:${item.kind}: owner action under 40px`);

    await pointerClick(button);
    await page.waitForFunction((target) => location.hash === target, item.hash, { timeout: 10000 });
    await page.waitForTimeout(500);
    result.actions[item.kind].detail_hash = await page.evaluate(() => location.hash);
    const errorVisible = await page.locator('.v270-error').count();
    if (errorVisible !== 0) fail(`${viewportName}:${item.kind}: detail route rendered error`);
    const detailOverflow = await overflowX();
    if (detailOverflow > 1) fail(`${viewportName}:${item.kind}: detail horizontal overflow ${detailOverflow}`);

    const back = page.locator('[data-v275-context-backbar] [data-v275-go="#overview"]').first();
    await back.waitFor({ state: 'visible', timeout: 15000 });
    const backLabel = (await back.textContent() || '').trim();
    result.actions[item.kind].return_label = backLabel;
    if (backLabel !== '← 返回概览') fail(`${viewportName}:${item.kind}: Overview return owner label mismatch: ${backLabel}`);
    if (viewportName === 'mobile') {
      const backBox = await back.boundingBox();
      if (!backBox || backBox.height < 40) fail(`${viewportName}:${item.kind}: Overview return action under 40px`);
    }
    await page.screenshot({ path: `${evidence}/${viewportName}-${item.kind}-attention-detail.png`, fullPage: true, animations: 'disabled' });
    await pointerClick(back);
    await page.waitForFunction(() => location.hash === '#overview', null, { timeout: 10000 });
    await page.waitForTimeout(500);
    result.actions[item.kind].returned_hash = await page.evaluate(() => location.hash);
    await panel.waitFor({ state: 'visible', timeout: 15000 });
  }

  const postReturnCount = await panel.locator('.v270-ref-action').count();
  result.post_return_card_count = postReturnCount;
  result.post_return_onboarding_count = await page.locator('[data-v2813-zero-onboarding]').count();
  if (postReturnCount !== 3) fail(`${viewportName}: attention cards changed after owner round-trips (${postReturnCount})`);
  if (result.post_return_onboarding_count !== 0) fail(`${viewportName}: stale zero-data onboarding appeared on populated Overview`);
  await page.screenshot({ path: `${evidence}/${viewportName}-overview-attention.png`, fullPage: true, animations: 'disabled' });
}

try {
  await installAndLogin();
  const seed = seedSyntheticData();
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(700);

  for (const [viewportName, viewport] of Object.entries(viewports)) {
    await page.setViewportSize(viewport);
    await inspectOverview(viewportName, seed);
  }

  if (report.page_errors.length) fail(`page errors: ${JSON.stringify(report.page_errors)}`);
  if (report.console_errors.length) fail(`console errors: ${JSON.stringify(report.console_errors)}`);
  report.status = report.failures.length === 0 ? 'PASS' : 'FAIL';
} catch (error) {
  fail(String(error?.stack || error));
  report.status = 'FAIL';
} finally {
  fs.writeFileSync(`${evidence}/P04_OVERVIEW_ATTENTION_ACTIONS_AUDIT.json`, JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}

console.log(`P04_OVERVIEW_ATTENTION_ACTIONS_GATE=${report.status}`);
if (report.failures.length) console.error(report.failures.join('\n'));
if (report.status !== 'PASS') process.exit(1);
