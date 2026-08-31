import { chromium } from 'playwright';
import fs from 'node:fs';

const base = process.env.VF_E2E_BASE_URL || 'http://127.0.0.1:19042';
const evidence = process.env.EVIDENCE;
const candidate = process.env.CANDIDATE;
if (!evidence || !candidate) throw new Error('P04 daily UX browser environment missing');

const password = 'Vf' + crypto.randomUUID().replaceAll('-', '') + 'Aa1';
const report = { status: 'FAIL', source_sha: candidate, overview: {}, domains: {}, mobile: {}, page_errors: [], console_errors: [] };
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1365, height: 900 } });
const page = await context.newPage();
page.on('pageerror', (e) => report.page_errors.push(String(e?.stack || e)));
page.on('console', (m) => { if (m.type() === 'error') report.console_errors.push(m.text()); });
const assert = (value, message) => { if (!value) throw new Error(message); };
const isoDay = (offset) => { const d = new Date(); d.setUTCDate(d.getUTCDate() + offset); return d.toISOString().slice(0, 10); };

async function cold(hash) {
  await page.goto('about:blank');
  await page.goto(`${base}/index.php#${hash}`, { waitUntil: 'domcontentloaded' });
  await page.locator('#v270-app h1').waitFor({ state: 'visible', timeout: 15000 });
  await page.waitForTimeout(600);
}

async function apiPost(action, data = {}) {
  return page.evaluate(async ({ action, data }) => {
    const token = document.querySelector('meta[name="csrf-token"]')?.content || '';
    const response = await fetch(`api.php?action=${encodeURIComponent(action)}`, {
      method: 'POST', credentials: 'same-origin',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-CSRF-Token': token },
      body: JSON.stringify(data),
    });
    const payload = await response.json();
    if (!response.ok || payload.ok === false) throw new Error(payload.message || action);
    return payload;
  }, { action, data });
}

try {
  await page.goto(`${base}/setup.php`, { waitUntil: 'domcontentloaded' });
  await page.locator('#site_name').fill('VF Infra Daily UX Gate');
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

  await apiPost('domain_save', { domain: 'expired-daily-ux.example', manual_expiry_date: isoDay(-2), renewal_price: '12.00', currency: 'USD', renewal_policy: 'manual', auto_renew: 0, registrar: 'Dynadot', notes: 'synthetic daily UX gate' });
  await apiPost('domain_save', { domain: 'due-daily-ux.example', manual_expiry_date: isoDay(20), renewal_price: '15.00', currency: 'USD', renewal_policy: 'manual', auto_renew: 0, registrar: 'Namecheap', notes: 'synthetic daily UX gate' });
  await apiPost('domain_save', { domain: 'safe-daily-ux.example', manual_expiry_date: isoDay(180), renewal_price: '10.00', currency: 'USD', renewal_policy: 'auto', auto_renew: 1, registrar: 'Cloudflare', notes: 'synthetic daily UX gate' });

  await cold('overview');
  assert(await page.locator('body.v2812-daily-ux').count() === 1, 'daily UX body class missing');
  const priorityMetrics = page.locator('.v270-ref-metric[data-v2812-priority]');
  assert(await priorityMetrics.count() >= 1, 'overview attention hierarchy missing');
  const todoHead = page.locator('.v270-section-head').filter({ has: page.locator('h2', { hasText: '需要我处理' }) }).first();
  if (await todoHead.count()) {
    const sub = (await todoHead.locator('.v270-section-sub').innerText()).trim();
    assert(sub === '当前没有待办' || sub.includes('需要确认或处理'), `todo summary not owner-friendly: ${sub}`);
  }
  report.overview.attention_hierarchy = 'PASS';
  report.overview.owner_copy = 'PASS';

  await cold('domains');
  const table = page.locator('table.domain-table');
  await table.waitFor({ state: 'visible', timeout: 15000 });
  const toolbar = page.locator('[data-v275-toolbar="domains"]');
  await toolbar.waitFor({ state: 'visible', timeout: 10000 });
  const brief = page.locator('.v2812-domain-brief');
  await brief.waitFor({ state: 'visible', timeout: 10000 });
  const initial = (await brief.innerText()).replace(/\s+/g, ' ').trim();
  assert(initial.includes('本页 3 个域名'), `initial domain brief: ${initial}`);
  assert(initial.includes('需要优先处理') || initial.includes('建议近期关注'), `domain priority summary: ${initial}`);
  const expired = table.locator('tbody tr').filter({ hasText: 'expired-daily-ux.example' }).first();
  await expired.waitFor({ state: 'visible' });
  assert((await expired.getAttribute('data-v2812-risk')) === 'attention', 'expired domain risk affordance missing');
  assert((await expired.locator('[data-v270-action="domain"]').getAttribute('aria-label')) === '查看 expired-daily-ux.example 详情', 'domain primary action aria missing');
  assert((await toolbar.locator('input[type="search"]').getAttribute('placeholder')) === '搜索域名、注册商、分组或风险', 'domain search placeholder missing');
  report.domains.summary = 'PASS';
  report.domains.risk_affordance = 'PASS';
  report.domains.primary_action = 'PASS';

  const search = toolbar.locator('input[type="search"]');
  await search.fill('safe-daily-ux.example');
  await page.waitForTimeout(180);
  const filtered = (await brief.innerText()).replace(/\s+/g, ' ').trim();
  assert(filtered.includes('当前显示 1 / 3 个域名'), `filter-aware summary missing: ${filtered}`);
  assert(filtered.includes('没有明显风险'), `filtered risk summary wrong: ${filtered}`);
  await search.fill('');
  await expired.waitFor({ state: 'visible' });
  report.domains.filter_aware_summary = 'PASS';
  await page.screenshot({ path: `${evidence}/01-domains-desktop.png`, fullPage: true, animations: 'disabled' });

  await page.setViewportSize({ width: 390, height: 844 });
  await cold('domains');
  const cards = page.locator('.domain-card');
  const riskyCard = cards.filter({ hasText: 'expired-daily-ux.example' }).first();
  await riskyCard.waitFor({ state: 'visible', timeout: 10000 });
  assert((await riskyCard.getAttribute('data-v2812-risk')) === 'attention', 'mobile domain risk missing');
  const overflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - window.innerWidth);
  assert(overflow <= 1, `mobile horizontal overflow ${overflow}`);
  assert(await page.locator('.v2812-domain-brief').isVisible(), 'domain summary hidden on mobile');
  const more = riskyCard.locator('.v275-more-button');
  if (await more.count()) {
    const box = await more.boundingBox();
    assert(box && box.width >= 38 && box.height >= 38, `mobile more target ${JSON.stringify(box)}`);
  }
  report.mobile.risk = 'PASS';
  report.mobile.no_overflow = 'PASS';
  report.mobile.summary_visible = 'PASS';
  report.mobile.action_target = 'PASS';
  await page.screenshot({ path: `${evidence}/02-domains-mobile-390.png`, fullPage: true, animations: 'disabled' });

  assert(report.page_errors.length === 0, `page errors ${JSON.stringify(report.page_errors)}`);
  assert(report.console_errors.length === 0, `console errors ${JSON.stringify(report.console_errors)}`);
  report.status = 'PASS';
} finally {
  fs.writeFileSync(`${evidence}/P04_DAILY_UX_REPORT.json`, JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}

if (report.status !== 'PASS') process.exit(1);
console.log('P04_DAILY_UX_BROWSER=PASS');
