import { chromium } from 'playwright';
import AxeBuilder from '@axe-core/playwright';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const base = process.env.BASE_URL;
const password = process.env.ADMIN_PASSWORD || 'VfInfraE2E2549';
const dbPath = process.env.DB_PATH;
const shots = process.env.SCREENSHOT_DIR || 'screenshots';
if (!base || !dbPath) throw new Error('BASE_URL / DB_PATH required');
fs.mkdirSync(shots, { recursive: true });

const errors = [];
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, locale: 'zh-CN' });
const page = await context.newPage();
page.on('pageerror', (e) => errors.push(`PAGEERROR ${e.message}`));
page.on('console', (msg) => { if (msg.type() === 'error') errors.push(`CONSOLE ${msg.text()}`); });
page.on('response', (res) => { if (res.status() >= 500) errors.push(`HTTP${res.status()} ${res.url()}`); });

function assert(condition, message) { if (!condition) throw new Error(message); }
async function shot(name, pg = page) { await pg.screenshot({ path: path.join(shots, `${name}.png`), fullPage: true }); }
async function settle(ms = 220) { await page.waitForTimeout(ms); }
async function assertNoPageFailure() {
  const failure = page.locator('.v254-error-card, .empty-state').filter({ hasText: '页面加载失败' });
  assert(await failure.count() === 0, `page failure visible at ${page.url()}`);
}
async function axe(name) {
  const results = await new AxeBuilder({ page }).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();
  const serious = results.violations.filter((v) => ['critical','serious'].includes(v.impact || ''));
  fs.writeFileSync(path.join(shots, `${name}-axe.json`), JSON.stringify({ violations: results.violations }, null, 2));
  assert(serious.length === 0, `${name} axe serious/critical: ${serious.map(v=>v.id).join(',')}`);
}

// Fresh install through the real browser flow.
await page.goto(`${base}/setup.php`, { waitUntil: 'domcontentloaded' });
if (page.url().includes('setup.php')) {
  await page.locator('[name="site_name"]').fill('VF Infra E2E');
  await page.locator('[name="password"]').fill(password);
  await page.locator('[name="password_confirm"]').fill(password);
  await shot('00-setup');
  await Promise.all([
    page.waitForURL(/login\.php/, { timeout: 30000 }),
    page.locator('button[type="submit"]').click(),
  ]);
}

// Seed synthetic fixture into the isolated SQLite after the real installer completes.
const q = (s) => `'${String(s).replaceAll("'", "''")}'`;
const domainSql = [];
for (let i = 1; i <= 65; i++) {
  const n = String(i).padStart(3, '0');
  const expiry = i <= 4 ? '2026-08-20' : (i <= 12 ? '2026-09-10' : '2027-08-16');
  domainSql.push(`INSERT INTO domains(domain,project_name,registrar,renewal_price,currency,auto_renew,effective_expiry_date,effective_expiry_source,last_check_status,tags_json,created_at,updated_at) VALUES(${q(`fixture-${n}.example.test`)},${q(i%2?'演示项目 A':'演示项目 B')},'Example Registrar',12.50,'USD',${i%3===0?1:0},${q(expiry)},'manual','success','["E2E"]','2026-08-15 16:00:00','2026-08-15 16:00:00');`);
}
const sql = `PRAGMA foreign_keys=ON; BEGIN;\n${domainSql.join('\n')}
INSERT INTO alerts(domain_id,alert_type,reminder_days,severity,title,message,fingerprint,status,triggered_at,last_seen_at,last_triggered_at,handled_note) VALUES(1,'expiry',30,'medium','域名即将到期','请确认续费安排','e2e-alert-1','pending','2026-08-15 16:05:00','2026-08-15 16:05:00','2026-08-15 16:05:00','');
INSERT INTO cron_runs(run_type,started_at,finished_at,status,domain_count,success_count,failure_count,change_count,duration_ms,summary_json,error_message) VALUES('cron','2026-08-15 15:50:00','2026-08-15 15:51:00','success',65,65,0,0,60000,'{}','');
INSERT INTO domain_checks(domain_id,cron_run_id,checked_at,status,http_status,duration_ms,rdap_server,expiry_date,statuses_json,nameservers_json,registrar,raw_summary_json,error_code,error_message,changed_fields_json) VALUES(1,1,'2026-08-15 15:50:10','success',200,120,'https://rdap.example.test','2026-08-20','[]','[]','Example Registrar','{}','','','{}');
DELETE FROM update_history;
INSERT INTO update_history(operation_id,package_id,from_version,to_version,started_at,completed_at,result,failure_stage,release_manifest_sha256,update_package_sha256,details_json) VALUES('e2e-v253-attempt-1','P04','2.5.2','2.5.3','2026-08-15 16:00:00','2026-08-15 16:01:00','failed','prepare','m1','p1','{}');
INSERT INTO update_history(operation_id,package_id,from_version,to_version,started_at,completed_at,result,failure_stage,release_manifest_sha256,update_package_sha256,details_json) VALUES('e2e-v253-attempt-2','P04','2.5.2','2.5.3','2026-08-15 16:02:00','2026-08-15 16:03:00','success','','m1','p1','{}');
COMMIT;`;
execFileSync('sqlite3', [dbPath], { input: sql, stdio: ['pipe','pipe','pipe'] });

// Real login.
await page.goto(`${base}/login.php`, { waitUntil: 'domcontentloaded' });
await shot('01-login');
await axe('login');
await page.locator('#admin-password').fill(password);
await page.getByRole('button', { name: '登录' }).click();
await page.waitForSelector('.nav-item[data-nav="dashboard"]', { timeout: 30000 });
await settle(500);

const views = [
  ['dashboard','工作台'],['projects','项目'],['assets','全部资产'],['domains','域名'],['dns','DNS'],
  ['vps','VPS'],['providers','连接账号'],['billing','计费'],['alerts','提醒'],['checks','检查记录'],['settings','设置'],
];
for (const [key, label] of views) {
  await page.locator(`.nav-item[data-nav="${key}"]`).click();
  await page.waitForSelector(`#view-${key}.active`);
  await settle();
  await assertNoPageFailure();
  assert((await page.locator('#page-description').innerText()).trim().length > 4, `${key} missing page description`);
  assert(await page.locator('#page-actions .button.primary').count() <= 1, `${key} has multiple primary actions`);
  await shot(`1440-${key}`);
}

// Domain table: pagination, search and modal interaction.
await page.locator('.nav-item[data-nav="domains"]').click();
await settle();
assert(await page.locator('#view-domains .pagination').count() >= 1, 'domains pagination missing with 65 rows');
const pagerText = await page.locator('#view-domains .pagination').innerText();
assert(/(?:第\s*)?1\s*\/\s*2/.test(pagerText), `unexpected domain pager: ${pagerText}`);
const domainSearch = page.locator('#view-domains .search-box input').first();
await domainSearch.fill('fixture-001.example.test');
await domainSearch.press('Enter');
await settle(350);
assert(await page.getByText('fixture-001.example.test', { exact: true }).count() >= 1, 'domain search failed');
await domainSearch.fill('');
await domainSearch.press('Enter');
await settle(300);

// Lightweight create action uses Modal.
await page.locator('.nav-item[data-nav="projects"]').click();
await settle(180);
const newProject = page.locator('#page-actions [data-action="new-project"]');
assert(await newProject.count() >= 1, 'new-project primary action missing');
await newProject.click();
await page.waitForFunction(() => document.querySelector('#modal')?.getAttribute('aria-hidden') === 'false');
assert(await page.locator('#modal[role="dialog"][aria-modal="true"]').count() === 1, 'modal semantics missing');
assert(await page.locator('#modal').evaluate((m) => m.contains(document.activeElement)), 'modal initial focus not contained');
await shot('modal-new-project');
await page.keyboard.press('Tab');
assert(await page.locator('#modal').evaluate((m) => m.contains(document.activeElement)), 'modal tab focus escaped');
await page.keyboard.press('Escape');
await page.waitForFunction(() => document.querySelector('#modal')?.getAttribute('aria-hidden') === 'true');
assert(await newProject.evaluate((b) => b === document.activeElement), 'modal did not return focus to opener');

// Complex domain editor uses Drawer by design.
await page.locator('.nav-item[data-nav="domains"]').click();
await settle(180);
const newDomain = page.locator('#page-actions [data-action="new-domain"]');
assert(await newDomain.count() >= 1, 'new-domain primary action missing');
await newDomain.click();
await page.waitForFunction(() => document.querySelector('#drawer')?.getAttribute('aria-hidden') === 'false');
assert(await page.locator('#drawer').evaluate((d) => d.contains(document.activeElement)), 'drawer initial focus not contained');
await shot('drawer-new-domain');
await page.keyboard.press('Tab');
assert(await page.locator('#drawer').evaluate((d) => d.contains(document.activeElement)), 'drawer tab focus escaped');
await page.keyboard.press('Escape');
await page.waitForFunction(() => document.querySelector('#drawer')?.getAttribute('aria-hidden') === 'true');
assert(await newDomain.evaluate((b) => b === document.activeElement), 'drawer did not return focus to opener');

// Settings subpages and save-state success.
await page.locator('.nav-item[data-nav="settings"]').click();
await settle(450);
const settingsSections = ['basic','connections','reminders','rdap','email','data','backup','security','update','system'];
for (const section of settingsSections) {
  await page.locator(`[data-action="settings-section"][data-section="${section}"]`).click();
  await page.waitForSelector(`[data-settings-section="${section}"].active`);
  await settle(120);
  await shot(`settings-${section}`);
}

await page.locator('[data-action="settings-section"][data-section="update"]').click();
await settle();
const historyRow = page.locator('#settings-update .detail-history-row').filter({ hasText: 'V2.5.2 → V2.5.3' }).first();
assert(await historyRow.count() === 1, 'V2.5.2 -> V2.5.3 history summary missing');
assert((await historyRow.locator('.badge').innerText()).includes('成功'), 'final update history is not success');
assert((await historyRow.innerText()).includes('早前失败已由后续成功收正'), 'attempt reconciliation explanation missing');
assert((await historyRow.innerText()).includes('2026-08-16'), 'Asia/Shanghai history date conversion not observed');

await page.locator('[data-action="settings-section"][data-section="basic"]').click();
await settle();
const tz = page.locator('[name="timezone"]');
assert(await tz.inputValue() === 'Asia/Shanghai', 'timezone is not Asia/Shanghai');
const siteName = page.locator('[name="site_name"]');
await siteName.fill('VF Infra E2E V254');
await page.getByRole('button', { name: '保存设置' }).click();
await page.waitForSelector('.toast.success');
assert((await page.locator('.toast.success').last().innerText()).includes('设置'), 'settings save success toast missing');

// Accessible labels in visible Settings fields.
const unlabeled = await page.locator('#settings-basic input:not([type="hidden"]),#settings-basic select,#settings-basic textarea').evaluateAll((nodes) => nodes.filter((el) => {
  if (el.getAttribute('aria-label') || el.getAttribute('aria-labelledby')) return false;
  if (el.id && document.querySelector(`label[for="${CSS.escape(el.id)}"]`)) return false;
  return !el.closest('label');
}).length);
assert(unlabeled === 0, `settings basic has ${unlabeled} unlabeled controls`);

await axe('dashboard-settings-basic');

// Synthetic partial error: the page must remain usable.
await page.route('**/api.php?action=settings*', async (route) => {
  const response = await route.fetch();
  const payload = await response.json();
  payload.partial_errors = [{ module: '系统诊断', message: 'E2E 合成模块读取失败。', reference: 'E2EPARTIAL' }];
  await route.fulfill({ response, json: payload });
});
await page.locator('.nav-item[data-nav="dashboard"]').click();
await page.locator('.nav-item[data-nav="settings"]').click();
await settle(500);
assert(await page.locator('.v254-partial-error').count() >= 1, 'partial error banner missing');
assert(await page.locator('#settings-form').count() === 1, 'partial error collapsed settings workspace');
await shot('state-partial-error');
await page.unroute('**/api.php?action=settings*');

// Synthetic full error and real retry recovery.
await page.route('**/api.php?action=dashboard*', async (route) => {
  await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ ok:false, message:'工作台数据暂时无法读取。错误编号：E2E123' }) });
});
await page.locator('.nav-item[data-nav="projects"]').click(); await settle(120);
await page.locator('.nav-item[data-nav="dashboard"]').click(); await settle(350);
assert(await page.locator('#view-dashboard .v254-error-card').count() === 1, 'full error normalization missing');
await shot('state-full-error');
await page.unroute('**/api.php?action=dashboard*');
await page.locator('#view-dashboard [data-action="reload-view"]').click();
await settle(450);
assert(await page.locator('#view-dashboard .v254-error-card').count() === 0, 'retry did not recover dashboard');

// Empty state is a real isolated-runtime state for connected accounts.
await page.locator('.nav-item[data-nav="providers"]').click(); await settle();
assert(await page.locator('#view-providers .empty-state, #view-providers .compact-empty, #view-providers .notice').count() >= 1, 'provider empty-state not present');
await shot('state-empty-providers');

// Responsive evidence: representative dense pages at formal widths.
for (const width of [1440,1366,1280,1024,760]) {
  await page.setViewportSize({ width, height: 950 });
  for (const key of ['dashboard','domains','settings']) {
    await page.locator(`.nav-item[data-nav="${key}"]`).click();
    await settle(180);
    if (key === 'settings') {
      await page.locator('[data-action="settings-section"][data-section="update"]').click();
      await settle(100);
    }
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 4);
    assert(!overflow, `${key} viewport ${width} causes document horizontal overflow`);
    await shot(`responsive-${width}-${key}`);
  }
}

await page.setViewportSize({ width: 1440, height: 1000 });
await page.locator('.nav-item[data-nav="domains"]').click(); await settle();
await axe('domains');
await page.locator('.nav-item[data-nav="settings"]').click(); await settle();
await axe('settings');

// CSP readback: no unsafe-inline regression on normal app/login.
for (const endpoint of ['index.php','login.php']) {
  const res = await context.request.get(`${base}/${endpoint}`);
  const csp = res.headers()['content-security-policy'] || '';
  assert(csp && !csp.includes("'unsafe-inline'"), `${endpoint} CSP unsafe-inline or missing`);
}

await browser.close();
if (errors.length) {
  fs.writeFileSync(path.join(shots, 'browser-errors.txt'), errors.join('\n') + '\n');
  throw new Error(`browser errors: ${errors.join(' | ')}`);
}
console.log('P04_V254_BROWSER_E2E=PASS');
