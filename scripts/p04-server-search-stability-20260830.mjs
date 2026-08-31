import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const base = process.env.VF_E2E_BASE_URL;
const evidence = process.env.EVIDENCE;
const candidate = process.env.CANDIDATE;
const webRoot = process.env.WEB_ROOT;
const productRoot = process.env.PRODUCT_ROOT;
if (!base || !evidence || !candidate || !webRoot || !productRoot) throw new Error('diagnostic environment missing');

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1365, height: 900 } });
const page = await context.newPage();
const password = 'Vf' + crypto.randomUUID().replaceAll('-', '') + 'Aa1';
const report = { status: 'DIAGNOSTIC', source_sha: candidate, restored: {}, pointer: {}, dom: {}, page_errors: [], console_errors: [] };
page.on('pageerror', e => report.page_errors.push(String(e?.stack || e)));
page.on('console', m => { if (m.type() === 'error') report.console_errors.push(m.text()); });
const assert = (v, m) => { if (!v) throw new Error(m); };

async function cold(hash) {
  await page.goto('about:blank');
  await page.goto(`${base}/index.php#${hash}`, { waitUntil: 'domcontentloaded' });
  await page.locator('#v270-app h1').waitFor({ state: 'visible', timeout: 15000 });
  await page.waitForTimeout(600);
}

try {
  await page.goto(`${base}/setup.php`, { waitUntil: 'domcontentloaded' });
  await page.locator('#site_name').fill('VF Infra Search Hit Target Diagnostic');
  await page.locator('#password').fill(password);
  await page.locator('#password_confirm').fill(password);
  await Promise.all([page.waitForURL(/login\.php\?installed=1/), page.getByRole('button', { name: '安装并进入系统' }).click()]);
  await page.locator('#admin-password').fill(password);
  await Promise.all([page.waitForURL(/index\.php(?:#.*)?$/), page.getByRole('button', { name: '登录' }).click()]);

  const fixture = execFileSync('php', ['tests/fixtures/v260-user-task-fixture.php', webRoot], { cwd: productRoot, encoding: 'utf8' });
  assert(fixture.includes('P04_V260_USER_TASK_FIXTURE_PASS'), 'fixture failed');
  execFileSync('php', ['-r', 'require getenv("WEB_ROOT")."/bootstrap.php"; Database::connection()->exec("UPDATE compute_instances SET power_status=\'stopped\', external_status=\'stopped\' WHERE external_instance_id=\'v260-edge-01\'");'], { cwd: productRoot, env: { ...process.env, WEB_ROOT: webRoot }, encoding: 'utf8' });

  await cold('servers');
  const toolbar = page.locator('[data-v275-toolbar="servers"]');
  const search = toolbar.locator('input[type="search"]');
  const count = toolbar.locator('[data-v275-count]');
  const brief = page.locator('.v2812-server-brief');
  const row = page.locator('table.server-table tbody tr').filter({ hasText: 'v260-edge-01' }).first();
  await toolbar.waitFor({ state: 'visible', timeout: 10000 });
  await row.waitFor({ state: 'visible', timeout: 10000 });

  await search.fill('no-such-server');
  await page.waitForFunction(() => document.querySelector('[data-v275-toolbar="servers"] [data-v275-count]')?.textContent?.trim().startsWith('0 / 1'));
  await search.fill('v260-edge-01');
  await page.waitForFunction(() => {
    const count = document.querySelector('[data-v275-toolbar="servers"] [data-v275-count]')?.textContent?.trim() || '';
    const brief = document.querySelector('.v2812-server-brief')?.textContent?.replace(/\s+/g, ' ').trim() || '';
    const row = [...document.querySelectorAll('table.server-table tbody tr')].find(r => r.textContent?.includes('v260-edge-01'));
    return count.startsWith('1 / 1') && brief.includes('本页 1 台服务器') && row && !row.hidden;
  }, null, { timeout: 10000 });
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));

  const button = row.locator('[data-v270-action="server"]');
  const serverId = await button.getAttribute('data-id');
  const box = await button.boundingBox();
  assert(Boolean(serverId) && box, 'restored action missing');
  const center = { x: box.x + box.width / 2, y: box.y + box.height / 2 };
  report.restored = await page.evaluate(({ x, y }) => {
    const button = [...document.querySelectorAll('table.server-table [data-v270-action="server"]')].find(n => n.closest('tr')?.textContent?.includes('v260-edge-01'));
    const hit = document.elementFromPoint(x, y);
    window.__p04Probe = { capture: 0, bubble: 0, target: 0 };
    document.addEventListener('click', () => window.__p04Probe.capture++, true);
    document.addEventListener('click', () => window.__p04Probe.bubble++, false);
    button?.addEventListener('click', () => window.__p04Probe.target++);
    const describe = node => node ? { tag: node.tagName, cls: node.className || '', text: (node.textContent || '').trim().slice(0, 80), action: node.getAttribute?.('data-v270-action') || '', id: node.getAttribute?.('data-id') || '' } : null;
    return { hash: location.hash, hit: describe(hit), button: describe(button), same: hit === button || Boolean(hit?.closest?.('[data-v270-action="server"]') === button) };
  }, center);
  report.restored.count = (await count.innerText()).trim();
  report.restored.brief = (await brief.innerText()).replace(/\s+/g, ' ').trim();
  report.restored.box = box;

  await page.mouse.click(center.x, center.y);
  await page.waitForTimeout(400);
  report.pointer = await page.evaluate(() => ({ hash: location.hash, probe: window.__p04Probe }));

  if (report.pointer.hash === '#servers') {
    await button.evaluate(node => node.click());
    await page.waitForTimeout(400);
  }
  report.dom = await page.evaluate(() => ({
    hash: location.hash,
    title: document.querySelector('#v270-app h1')?.textContent?.trim() || '',
    summary: Boolean(document.querySelector('.v270-ref-summary[data-ref-lock="server-summary"]')),
    probe: window.__p04Probe,
  }));
} finally {
  fs.mkdirSync(evidence, { recursive: true });
  fs.writeFileSync(path.join(evidence, 'P04_SERVER_SEARCH_STABILITY.json'), JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}

console.log(JSON.stringify({ restored: report.restored, pointer: report.pointer, dom: report.dom }));
