import { chromium } from 'playwright';
import fs from 'node:fs';

const base = process.env.VF_E2E_BASE_URL || 'http://127.0.0.1:19070';
const evidence = process.env.EVIDENCE;
const candidate = process.env.CANDIDATE;
if (!evidence || !candidate) throw new Error('domain detail return audit environment missing');
fs.mkdirSync(evidence, { recursive: true });

const password = 'Vf' + crypto.randomUUID().replaceAll('-', '') + 'Aa1';
const domains = Array.from({ length: 14 }, (_, index) => `return-audit-${String(index + 1).padStart(2, '0')}.example`);
const targetName = domains[9];
const report = {
  schema: 'p04-mobile-domain-detail-return-context-audit/v3',
  source_sha: candidate,
  status: 'FAIL',
  synthetic_domains: [],
  runtime: {},
  list_before: {},
  detail: {},
  return_bar: {},
  return_events: [],
  return_timeline: [],
  list_after: {},
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

async function snapshot(label) {
  const value = await page.evaluate((label) => ({
    label,
    hash: location.hash,
    window_scroll_y: window.scrollY,
    document_scroll_top: document.documentElement.scrollTop,
    body_scroll_top: document.body.scrollTop,
    body_scroll_height: document.body.scrollHeight,
    document_scroll_height: document.documentElement.scrollHeight,
    inner_height: innerHeight,
    rendered_route: document.querySelector('[data-v271-route]')?.getAttribute('data-v271-route') || '',
    visible_domain_cards: [...document.querySelectorAll('.domain-card')].filter((node) => {
      const style = getComputedStyle(node);
      return !node.hidden && style.display !== 'none' && style.visibility !== 'hidden';
    }).length,
    stored_scroll: sessionStorage.getItem('vf-infra-v275:scroll:domains'),
  }), label);
  report.return_timeline.push(value);
  return value;
}

async function installReturnEventProbe() {
  report.runtime = await page.evaluate(() => {
    window.__p04ReturnAuditEvents = [];
    const capture = (type, extra = {}) => {
      window.__p04ReturnAuditEvents.push({
        type,
        at: performance.now(),
        hash: location.hash,
        scroll_y: window.scrollY,
        scroll_height: Math.max(document.documentElement.scrollHeight, document.body.scrollHeight),
        stored_scroll: sessionStorage.getItem('vf-infra-v275:scroll:domains'),
        ...extra,
      });
    };
    document.addEventListener('click', (event) => {
      const target = event.target instanceof Element ? event.target.closest('[data-v275-go]') : null;
      if (!target) return;
      capture('click-capture', {
        data_go: target.getAttribute('data-v275-go') || '',
        has_primary_nav: Boolean(target.closest('[data-v270-nav]')),
      });
    }, true);
    window.addEventListener('popstate', () => capture('popstate'));
    window.addEventListener('hashchange', () => capture('hashchange'));
    return {
      v278_script_count: [...document.scripts].filter((script) => String(script.src || '').includes('v278-route-scroll-reset.js')).length,
      v275_script_count: [...document.scripts].filter((script) => String(script.src || '').includes('v275-ua-workflow.js')).length,
      current_hash: location.hash,
    };
  });
}

async function csrf() {
  return await page.evaluate(async () => {
    const response = await fetch('api.php?action=bootstrap', { credentials: 'same-origin', headers: { Accept: 'application/json' } });
    const result = await response.json();
    if (!response.ok || result.ok === false || !result.csrf) throw new Error('bootstrap csrf unavailable');
    return result.csrf;
  });
}

async function createSyntheticDomains() {
  const token = await csrf();
  const created = [];
  for (const domain of domains) {
    const saved = await page.evaluate(async ({ domain, token }) => {
      const body = new URLSearchParams({
        domain,
        registrar: 'Namecheap',
        currency: 'USD',
        renewal_price: '18.50',
        renewal_policy: 'manual',
        manual_expiry_date: '2026-10-18',
        project_name: 'Synthetic Detail Return Audit',
        notes: 'Fresh isolated synthetic test data only',
      });
      const response = await fetch('api.php?action=domain_save', {
        method: 'POST', credentials: 'same-origin',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
          'X-CSRF-Token': token,
        },
        body: body.toString(),
      });
      const result = await response.json();
      if (!response.ok || result.ok === false) throw new Error(result.message || 'domain_save failed');
      return { id: Number(result.domain?.id || 0), domain: String(result.domain?.domain || '') };
    }, { domain, token });
    if (saved.id <= 0 || saved.domain !== domain) throw new Error(`synthetic domain create mismatch ${domain}`);
    created.push(saved);
  }
  return created;
}

async function domainCard(name) {
  const card = page.locator('.domain-card').filter({ hasText: name }).first();
  await card.waitFor({ state: 'visible', timeout: 15000 });
  return card;
}

async function openTargetDetail() {
  const card = await domainCard(targetName);
  const more = card.locator('[data-v275-domain-actions]').first();
  await pointerClick(more);
  const menu = page.locator('.v275-quick-menu[role="menu"]').first();
  await menu.waitFor({ state: 'visible', timeout: 10000 });
  const open = menu.locator('[role="menuitem"][data-action="open"]').first();
  await pointerClick(open);
}

try {
  await page.goto(`${base}/setup.php`, { waitUntil: 'domcontentloaded' });
  await page.locator('#site_name').fill('VF Infra Detail Return Audit');
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

  report.synthetic_domains = await createSyntheticDomains();
  const target = report.synthetic_domains.find((entry) => entry.domain === targetName);
  if (!target) throw new Error('target domain missing');

  await page.goto(`${base}/index.php?audit=${Date.now()}#domains`, { waitUntil: 'domcontentloaded' });
  const query = page.locator('[data-v275-query]').first();
  await query.waitFor({ state: 'visible', timeout: 15000 });
  await query.fill('return-audit');
  await page.waitForTimeout(180);

  const visibleCards = page.locator('.domain-card:visible');
  report.list_before.visible_count = await visibleCards.count();
  report.list_before.query = await query.inputValue();
  assert(report.list_before.visible_count === domains.length, `filtered visible count mismatch ${report.list_before.visible_count}`);
  assert(report.list_before.query === 'return-audit', `query not applied ${report.list_before.query}`);

  const targetCard = await domainCard(targetName);
  await targetCard.scrollIntoViewIfNeeded();
  await page.evaluate(() => window.scrollBy(0, -120));
  await page.waitForTimeout(100);
  report.list_before.scroll_y = await page.evaluate(() => window.scrollY);
  report.list_before.scroll_height = await page.evaluate(() => document.documentElement.scrollHeight);
  report.list_before.stored_scroll_before_open = await page.evaluate(() => sessionStorage.getItem('vf-infra-v275:scroll:domains'));
  assert(report.list_before.scroll_y > 0, `list did not reach scrollable position ${report.list_before.scroll_y}`);

  await openTargetDetail();
  await page.waitForFunction((id) => location.hash === `#domain/${id}`, target.id, { timeout: 10000 });
  report.detail.hash = await page.evaluate(() => location.hash);
  report.detail.target_id = target.id;
  report.detail.target_name_visible = (await page.getByText(targetName, { exact: false }).count()) > 0;
  report.detail.stored_scroll = await page.evaluate(() => sessionStorage.getItem('vf-infra-v275:scroll:domains'));
  report.detail.window_scroll_y = await page.evaluate(() => window.scrollY);
  assert(report.detail.hash === `#domain/${target.id}`, `detail hash mismatch ${report.detail.hash}`);
  assert(report.detail.target_name_visible, 'target domain name not visible in detail');

  const bar = page.locator('[data-v275-context-backbar]').first();
  await bar.waitFor({ state: 'visible', timeout: 10000 });
  const back = bar.locator('[data-v275-go="#domains"]').first();
  await back.waitFor({ state: 'visible', timeout: 10000 });
  report.return_bar.text = (await back.textContent() || '').trim();
  report.return_bar.data_go = await back.getAttribute('data-v275-go');
  report.return_bar.back_size = await size(back);
  report.return_bar.previous_count = await bar.locator('[data-v275-go^="#domain/"]').filter({ hasText: '上一条' }).count();
  report.return_bar.next_count = await bar.locator('[data-v275-go^="#domain/"]').filter({ hasText: '下一条' }).count();
  report.return_bar.page_overflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth);
  report.return_bar.scroll_before_click = await page.evaluate(() => window.scrollY);
  report.return_bar.stored_scroll_before_click = await page.evaluate(() => sessionStorage.getItem('vf-infra-v275:scroll:domains'));
  assert(report.return_bar.text.includes('返回域名列表'), `return label mismatch ${report.return_bar.text}`);
  assert(report.return_bar.data_go === '#domains', `return data-v275-go mismatch ${report.return_bar.data_go}`);
  assert(report.return_bar.back_size.height >= 40 && report.return_bar.back_size.width >= 52, `return button too small ${JSON.stringify(report.return_bar.back_size)}`);
  assert(report.return_bar.previous_count === 1, `previous detail control missing ${report.return_bar.previous_count}`);
  assert(report.return_bar.next_count === 1, `next detail control missing ${report.return_bar.next_count}`);
  assert(report.return_bar.page_overflow <= 1, `detail page overflow ${report.return_bar.page_overflow}`);

  await installReturnEventProbe();
  assert(report.runtime.v278_script_count === 1, `V278 runtime script count ${report.runtime.v278_script_count}`);
  assert(report.runtime.v275_script_count === 1, `V275 runtime script count ${report.runtime.v275_script_count}`);

  await pointerClick(back);
  await page.waitForFunction(() => location.hash === '#domains', null, { timeout: 10000 });
  await snapshot('hash-domains');
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => resolve())));
  await snapshot('raf-1');
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => resolve())));
  await snapshot('raf-2');
  await page.waitForTimeout(50);
  await snapshot('plus-50ms');
  await page.waitForTimeout(70);
  await snapshot('plus-120ms');
  await page.waitForTimeout(80);
  await snapshot('plus-200ms');
  await page.waitForTimeout(150);
  await snapshot('plus-350ms');
  await page.waitForTimeout(250);
  await snapshot('plus-600ms');
  report.return_events = await page.evaluate(() => window.__p04ReturnAuditEvents || []);

  const queryAfter = page.locator('[data-v275-query]').first();
  await queryAfter.waitFor({ state: 'visible', timeout: 10000 });
  report.list_after.hash = await page.evaluate(() => location.hash);
  report.list_after.query = await queryAfter.inputValue();
  report.list_after.visible_count = await page.locator('.domain-card:visible').count();
  report.list_after.scroll_y = await page.evaluate(() => window.scrollY);
  report.list_after.target_visible = await (await domainCard(targetName)).isVisible();
  report.list_after.scroll_delta = Math.abs(report.list_after.scroll_y - report.list_before.scroll_y);
  report.list_after.page_overflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth);
  report.list_after.stored_scroll = await page.evaluate(() => sessionStorage.getItem('vf-infra-v275:scroll:domains'));
  report.list_after.scroll_height = await page.evaluate(() => document.documentElement.scrollHeight);

  assert(report.list_after.hash === '#domains', `return hash mismatch ${report.list_after.hash}`);
  assert(report.list_after.query === 'return-audit', `query lost after return ${report.list_after.query}`);
  assert(report.list_after.visible_count === domains.length, `visible count changed after return ${report.list_after.visible_count}`);
  assert(report.list_after.target_visible, 'target domain not visible after return');
  assert(report.list_after.scroll_delta <= 140, `list scroll context not restored delta=${report.list_after.scroll_delta} before=${report.list_before.scroll_y} after=${report.list_after.scroll_y}`);
  assert(report.list_after.page_overflow <= 1, `list page overflow after return ${report.list_after.page_overflow}`);

  await page.screenshot({ path: `${evidence}/mobile-domains-after-detail-return.png`, fullPage: true, animations: 'disabled' });
  assert(report.page_errors.length === 0, `page errors ${JSON.stringify(report.page_errors)}`);
  assert(report.console_errors.length === 0, `console errors ${JSON.stringify(report.console_errors)}`);
  report.status = report.failures.length === 0 ? 'PASS' : 'FAIL';
} finally {
  fs.writeFileSync(`${evidence}/P04_MOBILE_DOMAIN_DETAIL_RETURN_CONTEXT_AUDIT.json`, JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}

console.log(`P04_MOBILE_DOMAIN_DETAIL_RETURN_CONTEXT_AUDIT=${report.status}`);
if (report.status !== 'PASS') {
  console.error(report.failures.join('\n'));
  process.exit(1);
}
