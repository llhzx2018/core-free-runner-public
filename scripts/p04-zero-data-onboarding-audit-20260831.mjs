import { chromium } from 'playwright';
import fs from 'node:fs';

const base = process.env.VF_E2E_BASE_URL || 'http://127.0.0.1:19078';
const evidence = process.env.EVIDENCE || '';
const source = process.env.SOURCE || '';
if (!evidence || !source) throw new Error('zero-data onboarding audit environment missing');
fs.mkdirSync(evidence, { recursive: true });

const password = 'Vf' + crypto.randomUUID().replaceAll('-', '') + 'Aa1';
const report = {
  schema: 'p04-zero-data-onboarding-audit/v1',
  source_sha: source,
  status: 'FAIL',
  views: {},
  findings: [],
  failures: [],
  page_errors: [],
  console_errors: [],
  fresh_install_zero_assets: true,
  synthetic_test_data_only: false,
  production_actions_executed: false,
};

const routeDefs = [
  ['overview', '#overview'],
  ['domains', '#domains'],
  ['servers', '#servers'],
  ['providers', '#providers'],
];
const viewports = [
  ['desktop', { width: 1440, height: 900 }],
  ['mobile', { width: 390, height: 844 }],
];

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: viewports[0][1] });
const page = await context.newPage();
page.on('pageerror', (e) => report.page_errors.push(String(e?.stack || e)));
page.on('console', (m) => { if (m.type() === 'error') report.console_errors.push(m.text()); });

function addFinding(severity, key, issue, observed = null) {
  report.findings.push({ severity, key, issue, ...(observed === null ? {} : { observed }) });
}

async function installAndLogin() {
  await page.goto(`${base}/setup.php`, { waitUntil: 'domcontentloaded' });
  await page.locator('#site_name').fill('VF Infra Zero Data Onboarding Audit');
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

async function inspectView(routeName, hash, viewportName, viewport) {
  await page.setViewportSize(viewport);
  await page.goto(`${base}/index.php?audit=${Date.now()}${hash}`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(650);
  await page.waitForFunction((expected) => location.hash === expected, hash, { timeout: 10000 });

  const key = `${viewportName}:${routeName}`;
  const data = await page.evaluate(() => {
    const visible = (node) => Boolean(node && (node.offsetWidth || node.offsetHeight || node.getClientRects().length));
    const text = (node) => (node?.textContent || '').replace(/\s+/g, ' ').trim();
    const actions = [...document.querySelectorAll('button, a[href], [role="button"]')]
      .filter(visible)
      .map((node) => {
        const rect = node.getBoundingClientRect();
        return {
          tag: node.tagName.toLowerCase(),
          text: text(node).slice(0, 140),
          aria_label: node.getAttribute('aria-label') || '',
          title: node.getAttribute('title') || '',
          href: node.getAttribute('href') || '',
          v270_action: node.getAttribute('data-v270-action') || '',
          v271_action: node.getAttribute('data-v271-action') || '',
          v275_go: node.getAttribute('data-v275-go') || '',
          width: Math.round(rect.width * 10) / 10,
          height: Math.round(rect.height * 10) / 10,
        };
      })
      .filter((item) => item.text || item.aria_label || item.href || item.v270_action || item.v271_action || item.v275_go);
    const bodyText = text(document.querySelector('#v270-app') || document.body);
    const headings = [...document.querySelectorAll('h1,h2,h3')].filter(visible).map((node) => text(node)).filter(Boolean);
    const emptyMatches = [...new Set((bodyText.match(/[^。；！？]{0,30}(?:暂无|还没有|没有|未添加|未录入|暂无数据|空)[^。；！？]{0,50}/g) || []).map((s) => s.trim()))].slice(0, 20);
    const guidanceMatches = [...new Set((bodyText.match(/[^。；！？]{0,35}(?:添加|新建|录入|开始|设置|先|下一步|导入|创建)[^。；！？]{0,60}/g) || []).map((s) => s.trim()))].slice(0, 24);
    return {
      hash: location.hash,
      title: document.title,
      headings,
      body_excerpt: bodyText.slice(0, 2600),
      actions,
      empty_matches: emptyMatches,
      guidance_matches: guidanceMatches,
      overflow_x: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth,
      scroll_height: Math.max(document.documentElement.scrollHeight, document.body.scrollHeight),
    };
  });

  data.primary_action_candidates = data.actions.filter((item) => /添加|新建|录入|开始|创建|设置|导入/.test(`${item.text} ${item.aria_label} ${item.title}`));
  data.detail_action_candidates = data.actions.filter((item) => item.v270_action || item.v271_action || item.v275_go);
  report.views[key] = data;

  if (data.overflow_x > 1) addFinding('ux', key, 'horizontal_overflow', data.overflow_x);
  if (!data.headings.length) addFinding('ux', key, 'missing_visible_heading');

  if (routeName !== 'overview') {
    const hasEmptySignal = data.empty_matches.length > 0 || /暂无|还没有|没有|未添加|未录入/.test(data.body_excerpt);
    const hasGuidance = data.guidance_matches.length > 0 || /添加|新建|录入|开始|创建|设置|导入/.test(data.body_excerpt);
    const hasAction = data.primary_action_candidates.length > 0;
    if (!hasEmptySignal) addFinding('ux', key, 'zero_state_not_explicit');
    if (!hasGuidance) addFinding('ux', key, 'zero_state_missing_next_step_copy');
    if (!hasAction) addFinding('ux', key, 'zero_state_missing_visible_action');
  } else {
    const hasOnboardingSignal = /添加|新建|录入|开始|创建|设置|先/.test(data.body_excerpt) || data.primary_action_candidates.length > 0;
    if (!hasOnboardingSignal) addFinding('ux', key, 'overview_missing_first_step_guidance');
  }

  if (viewportName === 'mobile') {
    const actionable = data.actions.filter((item) => item.v270_action || item.v271_action || /添加|新建|录入|开始|创建|设置|导入/.test(`${item.text} ${item.aria_label}`));
    const undersized = actionable.filter((item) => item.height > 0 && item.height < 40);
    if (undersized.length) addFinding('ux', key, 'mobile_action_under_40px', undersized.slice(0, 12));
  }

  await page.screenshot({ path: `${evidence}/${viewportName}-${routeName}-zero-data.png`, fullPage: true, animations: 'disabled' });
}

try {
  await installAndLogin();
  for (const [viewportName, viewport] of viewports) {
    for (const [routeName, hash] of routeDefs) {
      await inspectView(routeName, hash, viewportName, viewport);
    }
  }
  if (report.page_errors.length) report.failures.push(`page errors: ${JSON.stringify(report.page_errors)}`);
  if (report.console_errors.length) report.failures.push(`console errors: ${JSON.stringify(report.console_errors)}`);
  report.status = report.failures.length === 0 ? 'PASS' : 'FAIL';
} catch (error) {
  report.failures.push(String(error?.stack || error));
  report.status = 'FAIL';
} finally {
  fs.writeFileSync(`${evidence}/P04_ZERO_DATA_ONBOARDING_AUDIT.json`, JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}

console.log(`P04_ZERO_DATA_ONBOARDING_AUDIT=${report.status}`);
console.log(`P04_ZERO_DATA_ONBOARDING_FINDINGS=${JSON.stringify(report.findings)}`);
if (report.status !== 'PASS') process.exit(1);
