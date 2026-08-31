import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const base = process.env.VF_UPGRADE_BASE_URL || 'http://127.0.0.1:19121';
const evidenceDir = process.env.EVIDENCE || '';
const dataDir = process.env.VF_UPGRADE_DATA_DIR || '';
if (!evidenceDir || !dataDir) throw new Error('missing upgrade environment');
fs.mkdirSync(evidenceDir, { recursive:true });
const password = 'Vf' + crypto.randomUUID().replaceAll('-', '') + 'Aa1';
const report = {
  gate:'P04_V2811_TO_V2812_ATOMIC_BROWSER_UPGRADE',
  status:'FAIL', source_version:null, target_version:null,
  protected_sentinel:false, upgrade_heading:null,
  page_errors:[], console_errors:[], failures:[],
  external_provider_api_called:false, production_actions_executed:false, real_user_data_used:false,
};
const fail = m => report.failures.push(m);
const browser = await chromium.launch({ headless:true });
const context = await browser.newContext({ viewport:{ width:1440, height:900 } });
const page = await context.newPage();
page.on('pageerror', e => report.page_errors.push(String(e?.stack || e)));
page.on('console', m => { if (m.type() === 'error') report.console_errors.push(m.text()); });
try {
  await page.goto(`${base}/setup.php`, { waitUntil:'domcontentloaded' });
  await page.locator('#site_name').fill('VF Infra V2.8.12 Atomic Gate');
  await page.locator('#password').fill(password);
  await page.locator('#password_confirm').fill(password);
  await Promise.all([
    page.waitForURL(/login\.php\?installed=1/, { timeout:30000 }),
    page.getByRole('button', { name:'安装并进入系统' }).click(),
  ]);
  await page.locator('#admin-password').fill(password);
  await Promise.all([
    page.waitForURL(/index\.php(?:#.*)?$/, { timeout:30000 }),
    page.getByRole('button', { name:'登录' }).click(),
  ]);
  report.source_version = await page.locator('meta[name="app-version"]').getAttribute('content');
  if (report.source_version !== '2.8.11') fail(`source version ${report.source_version}`);

  fs.mkdirSync(dataDir, { recursive:true });
  const sentinel = path.join(dataDir, 'V2812_PROTECTED_SENTINEL.txt');
  fs.writeFileSync(sentinel, 'P04 V2.8.12 synthetic protected data sentinel\n');

  await page.goto(`${base}/repair-v2.8.12.php`, { waitUntil:'domcontentloaded' });
  const upgrade = page.getByRole('button', { name:/升级/ }).last();
  await upgrade.waitFor({ state:'visible', timeout:10000 });
  await upgrade.click();
  await page.waitForLoadState('domcontentloaded');
  const heading = page.getByRole('heading', { name:/升级完成/ }).first();
  await heading.waitFor({ state:'visible', timeout:30000 });
  report.upgrade_heading = (await heading.textContent())?.trim() || '';

  await page.goto(`${base}/index.php`, { waitUntil:'domcontentloaded' });
  report.target_version = await page.locator('meta[name="app-version"]').getAttribute('content');
  if (report.target_version !== '2.8.12') fail(`target version ${report.target_version}`);
  report.protected_sentinel = fs.existsSync(sentinel) && fs.readFileSync(sentinel, 'utf8').includes('synthetic protected data sentinel');
  if (!report.protected_sentinel) fail('protected sentinel not preserved');
  if (report.page_errors.length) fail(`page errors ${JSON.stringify(report.page_errors)}`);
  if (report.console_errors.length) fail(`console errors ${JSON.stringify(report.console_errors)}`);
  report.status = report.failures.length ? 'FAIL' : 'PASS';
  await page.screenshot({ path:path.join(evidenceDir, 'post-atomic-upgrade.png'), fullPage:true, animations:'disabled' });
} catch (e) {
  fail(String(e?.stack || e));
  report.status = 'FAIL';
} finally {
  fs.writeFileSync(path.join(evidenceDir, 'atomic-upgrade-report.json'), JSON.stringify(report, null, 2) + '\n');
  await context.close();
  await browser.close();
}
console.log(`P04_V2811_TO_V2812_ATOMIC_BROWSER_UPGRADE=${report.status}`);
if (report.failures.length) console.error(report.failures.join('\n'));
if (report.status !== 'PASS') process.exit(1);
