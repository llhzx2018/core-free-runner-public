import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const base = process.env.VF_E2E_BASE_URL || 'http://127.0.0.1:19050';
const evidence = process.env.EVIDENCE;
const source = process.env.SOURCE_SHA;
const webRoot = process.env.WEB_ROOT;
const productRoot = process.env.PRODUCT_ROOT || path.join(process.cwd(), 'product');
if (!evidence || !source || !webRoot) throw new Error('P04 search audit environment missing');

const password = 'Vf' + crypto.randomUUID().replaceAll('-', '') + 'Aa1';
const report = {
  schema: 'p04-global-search-current-audit/v1',
  source_sha: source,
  probes: [],
  mobile: {},
  page_errors: [],
  console_errors: [],
  production_actions_executed: false,
  synthetic_test_data_only: true,
};

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1365, height: 900 } });
const page = await context.newPage();
page.on('pageerror', (e) => report.page_errors.push(String(e?.stack || e)));
page.on('console', (m) => { if (m.type() === 'error') report.console_errors.push(m.text()); });

async function snapshot(query, file) {
  await page.goto(`${base}/index.php#overview`, { waitUntil: 'domcontentloaded' });
  await page.locator('#v270-search-input').waitFor({ state: 'visible', timeout: 15000 });
  await page.locator('#v270-search-input').fill(query);
  await page.locator('#v270-search-form').evaluate((form) => form.requestSubmit());
  await page.waitForTimeout(900);
  const data = await page.evaluate(() => {
    const app = document.querySelector('#v270-app');
    const h1 = app?.querySelector('h1')?.textContent?.trim() || '';
    const headings = [...(app?.querySelectorAll('h2,h3') || [])].map((n) => n.textContent?.trim() || '').filter(Boolean);
    const buttons = [...(app?.querySelectorAll('button') || [])].map((b) => ({
      text: b.textContent?.trim() || '',
      action: b.getAttribute('data-v270-action') || b.getAttribute('data-v271-action') || '',
      id: b.getAttribute('data-id') || '',
      aria: b.getAttribute('aria-label') || '',
    })).filter((b) => b.text || b.action);
    const resultLike = [...(app?.querySelectorAll('article,tr,.v270-mobile-card,.v271-provider-account') || [])]
      .map((n) => (n.textContent || '').replace(/\s+/g, ' ').trim())
      .filter(Boolean)
      .slice(0, 20);
    return {
      hash: location.hash,
      h1,
      headings,
      buttons,
      result_like: resultLike,
      app_text: (app?.innerText || '').replace(/\n{3,}/g, '\n\n').slice(0, 5000),
      search_value: document.querySelector('#v270-search-input')?.value || '',
    };
  });
  report.probes.push({ query, ...data });
  await page.screenshot({ path: `${evidence}/${file}`, fullPage: true, animations: 'disabled' });
}

try {
  await page.goto(`${base}/setup.php`, { waitUntil: 'domcontentloaded' });
  await page.locator('#site_name').fill('VF Infra Search Current Audit');
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

  const fixture = execFileSync('php', ['tests/fixtures/v260-user-task-fixture.php', webRoot], { cwd: productRoot, encoding: 'utf8' });
  if (!fixture.includes('P04_V260_USER_TASK_FIXTURE_PASS')) throw new Error('provider/server synthetic fixture failed');

  await snapshot('v260-edge-01', '01-search-server-name.png');
  await snapshot('203.0.113.26', '02-search-ip.png');
  await snapshot('V260 Linode', '03-search-provider.png');
  await snapshot('definitely-no-such-resource-20260830', '04-search-empty.png');

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${base}/index.php#overview`, { waitUntil: 'domcontentloaded' });
  await page.locator('#v270-search-input').waitFor({ state: 'visible', timeout: 15000 });
  await page.locator('#v270-search-input').fill('v260-edge-01');
  await page.locator('#v270-search-form').evaluate((form) => form.requestSubmit());
  await page.waitForTimeout(900);
  report.mobile = await page.evaluate(() => {
    const app = document.querySelector('#v270-app');
    const input = document.querySelector('#v270-search-input');
    return {
      hash: location.hash,
      h1: app?.querySelector('h1')?.textContent?.trim() || '',
      search_visible: !!(input && input.getBoundingClientRect().width > 0 && input.getBoundingClientRect().height > 0),
      search_box: input ? { width: input.getBoundingClientRect().width, height: input.getBoundingClientRect().height } : null,
      page_overflow: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - window.innerWidth,
      app_text: (app?.innerText || '').replace(/\n{3,}/g, '\n\n').slice(0, 3000),
    };
  });
  await page.screenshot({ path: `${evidence}/05-search-mobile-390.png`, fullPage: true, animations: 'disabled' });
} finally {
  fs.mkdirSync(evidence, { recursive: true });
  fs.writeFileSync(`${evidence}/P04_GLOBAL_SEARCH_CURRENT_AUDIT.json`, JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}

console.log('P04_GLOBAL_SEARCH_CURRENT_AUDIT=COMPLETE');
