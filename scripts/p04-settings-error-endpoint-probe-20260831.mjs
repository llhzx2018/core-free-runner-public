import { chromium } from 'playwright';
import fs from 'node:fs';

const base = process.env.VF_E2E_BASE_URL || 'http://127.0.0.1:19080';
const evidence = process.env.EVIDENCE || '';
const source = process.env.SOURCE || '';
if (!evidence || !source) throw new Error('settings probe environment missing');
fs.mkdirSync(evidence, { recursive: true });

const password = 'Vf' + crypto.randomUUID().replaceAll('-', '') + 'Aa1';
const fault = 'Synthetic settings endpoint fault';
const report = {
  schema: 'p04-settings-error-endpoint-probe/v1',
  source_sha: source,
  synthetic_fault_only: true,
  production_actions_executed: false,
  external_provider_api_called: false,
  views: {},
  failures: [],
};
const browser = await chromium.launch({ headless: true });
let storageState;

async function setup() {
  const c = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await c.newPage();
  await p.goto(`${base}/setup.php`, { waitUntil: 'domcontentloaded' });
  await p.locator('#site_name').fill('VF Infra Settings Error Probe');
  await p.locator('#password').fill(password);
  await p.locator('#password_confirm').fill(password);
  await Promise.all([p.waitForURL(/login\.php\?installed=1/, { timeout: 30000 }), p.getByRole('button', { name: '安装并进入系统' }).click()]);
  await p.locator('#admin-password').fill(password);
  await Promise.all([p.waitForURL(/index\.php/, { timeout: 30000 }), p.getByRole('button', { name: '登录' }).click()]);
  storageState = await c.storageState();
  await c.close();
}

async function probe(name, viewport) {
  const c = await browser.newContext({ viewport, storageState });
  const p = await c.newPage();
  const requests = [];
  const consoleErrors = [];
  p.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  await p.route('**/*', async (route) => {
    const req = route.request();
    if (req.method() !== 'GET') return route.continue();
    const u = new URL(req.url());
    if (u.pathname.endsWith('/api.php') || u.pathname.endsWith('/experience.php')) {
      requests.push({ pathname: u.pathname, query: u.search });
    }
    if (u.pathname.endsWith('/api.php')) {
      return route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ ok: false, message: fault }) });
    }
    return route.continue();
  });
  await p.goto(`${base}/index.php#settings`, { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(2200);
  const appText = String(await p.locator('#v270-app').textContent().catch(() => '')).replace(/\s+/g, ' ').trim();
  const h1 = String(await p.locator('#v270-app h1').first().textContent().catch(() => '')).trim();
  const v271Error = await p.locator('.v271-help.danger').first().isVisible().catch(() => false);
  const v270Error = await p.locator('.v270-error').first().isVisible().catch(() => false);
  const result = {
    requests,
    app_text: appText.slice(0, 800),
    h1,
    v271_error_visible: v271Error,
    v270_error_visible: v270Error,
    fault_visible: appText.includes(fault),
    current_settings_marker: await p.locator('[data-v271-route^="settings"]').count() > 0,
    console_errors: consoleErrors,
  };
  report.views[name] = result;
  await p.screenshot({ path: `${evidence}/${name}-settings-error-probe.png`, fullPage: true, animations: 'disabled' });
  if (!requests.some((x) => x.pathname.endsWith('/api.php'))) report.failures.push(`${name}: no api.php GET observed`);
  if (!result.fault_visible) report.failures.push(`${name}: broad api.php fault was not visible in Settings UI`);
  await c.close();
}

try {
  await setup();
  await probe('desktop', { width: 1440, height: 900 });
  await probe('mobile', { width: 390, height: 844 });
} catch (e) {
  report.failures.push(String(e?.stack || e));
} finally {
  report.status = report.failures.length ? 'FAIL' : 'PASS';
  fs.writeFileSync(`${evidence}/P04_SETTINGS_ERROR_ENDPOINT_PROBE.json`, JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}
console.log(`P04_SETTINGS_ERROR_ENDPOINT_PROBE=${report.status}`);
if (report.failures.length) console.error(report.failures.join('\n'));
if (report.status !== 'PASS') process.exit(1);
