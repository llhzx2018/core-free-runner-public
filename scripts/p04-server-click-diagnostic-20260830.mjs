import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const base = process.env.VF_E2E_BASE_URL || 'http://127.0.0.1:19045';
const evidence = process.env.EVIDENCE;
const candidate = process.env.CANDIDATE;
const webRoot = process.env.WEB_ROOT;
const productRoot = process.env.PRODUCT_ROOT || path.join(process.cwd(), 'product');
if (!evidence || !candidate || !webRoot) throw new Error('diagnostic environment missing');

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1365, height: 900 } });
await context.addInitScript(() => {
  const probe = window.__p04ServerClickProbe = {
    registrations: [], capture: [], bubble: [], target: [], stops: [], prevents: [], hashes: [], errors: [],
  };
  const clip = (value, n = 220) => String(value || '').replace(/\s+/g, ' ').slice(0, n);
  const originalAdd = EventTarget.prototype.addEventListener;
  EventTarget.prototype.addEventListener = function(type, listener, options) {
    try {
      if (this === document && type === 'click') {
        probe.registrations.push({
          phase: options === true || (options && options.capture) ? 'capture' : 'bubble',
          name: listener?.name || '',
          source: clip(listener),
        });
      }
    } catch (_) {}
    return originalAdd.call(this, type, listener, options);
  };
  const wrapEventMethod = (name, bucket) => {
    const original = Event.prototype[name];
    Event.prototype[name] = function(...args) {
      try {
        probe[bucket].push({
          type: this.type,
          target: clip(this.target?.outerHTML || this.target?.nodeName, 320),
          currentTarget: this.currentTarget === document ? 'document' : clip(this.currentTarget?.outerHTML || this.currentTarget?.nodeName, 160),
          stack: clip(new Error().stack, 900),
        });
      } catch (_) {}
      return original.apply(this, args);
    };
  };
  wrapEventMethod('stopImmediatePropagation', 'stops');
  wrapEventMethod('stopPropagation', 'stops');
  wrapEventMethod('preventDefault', 'prevents');
  originalAdd.call(document, 'click', (event) => {
    probe.capture.push({
      target: clip(event.target?.outerHTML || event.target?.nodeName, 320),
      defaultPrevented: event.defaultPrevented,
      hash: location.hash,
    });
  }, true);
  originalAdd.call(document, 'click', (event) => {
    probe.bubble.push({
      target: clip(event.target?.outerHTML || event.target?.nodeName, 320),
      defaultPrevented: event.defaultPrevented,
      hash: location.hash,
    });
  }, false);
  originalAdd.call(window, 'hashchange', () => probe.hashes.push(location.hash));
  originalAdd.call(window, 'error', (event) => probe.errors.push(String(event.error || event.message || 'error')));
});

const page = await context.newPage();
const password = 'Vf' + crypto.randomUUID().replaceAll('-', '') + 'Aa1';
const report = { status: 'DIAGNOSTIC', source_sha: candidate, before_filter: {}, after_filter: {}, direct_hash: {}, probe: null, page_errors: [], console_errors: [] };
page.on('pageerror', (e) => report.page_errors.push(String(e?.stack || e)));
page.on('console', (m) => { if (m.type() === 'error') report.console_errors.push(m.text()); });
const assert = (value, message) => { if (!value) throw new Error(message); };

async function cold(hash) {
  await page.goto('about:blank');
  await page.goto(`${base}/index.php#${hash}`, { waitUntil: 'domcontentloaded' });
  await page.locator('#v270-app h1').waitFor({ state: 'visible', timeout: 15000 });
  await page.waitForTimeout(600);
}

async function clickState(button) {
  await page.evaluate(() => {
    const probe = window.__p04ServerClickProbe;
    if (probe) {
      probe.capture.length = 0; probe.bubble.length = 0; probe.target.length = 0;
      probe.stops.length = 0; probe.prevents.length = 0; probe.hashes.length = 0; probe.errors.length = 0;
    }
  });
  await button.evaluate((node) => {
    node.addEventListener('click', (event) => {
      window.__p04ServerClickProbe?.target.push({
        target: String(event.target?.outerHTML || '').replace(/\s+/g, ' ').slice(0, 320),
        defaultPrevented: event.defaultPrevented,
        hash: location.hash,
      });
    }, { once: true });
  });
  const before = await page.evaluate(() => location.hash);
  await button.click();
  await page.waitForTimeout(250);
  return page.evaluate((beforeHash) => ({
    beforeHash,
    afterHash: location.hash,
    title: document.querySelector('#v270-app h1')?.textContent?.trim() || '',
    buttonStillPresent: Boolean(document.querySelector('table.server-table [data-v270-action="server"]')),
    probe: JSON.parse(JSON.stringify(window.__p04ServerClickProbe || {})),
  }), before);
}

try {
  await page.goto(`${base}/setup.php`, { waitUntil: 'domcontentloaded' });
  await page.locator('#site_name').fill('VF Infra Server Click Diagnostic');
  await page.locator('#password').fill(password);
  await page.locator('#password_confirm').fill(password);
  await Promise.all([page.waitForURL(/login\.php\?installed=1/), page.getByRole('button', { name: '安装并进入系统' }).click()]);
  await page.locator('#admin-password').fill(password);
  await Promise.all([page.waitForURL(/index\.php(?:#.*)?$/), page.getByRole('button', { name: '登录' }).click()]);

  const fixture = execFileSync('php', ['tests/fixtures/v260-user-task-fixture.php', webRoot], { cwd: productRoot, encoding: 'utf8' });
  assert(fixture.includes('P04_V260_USER_TASK_FIXTURE_PASS'), 'server fixture failed');
  execFileSync('php', ['-r', 'require getenv("WEB_ROOT")."/bootstrap.php"; Database::connection()->exec("UPDATE compute_instances SET power_status=\'stopped\', external_status=\'stopped\' WHERE external_instance_id=\'v260-edge-01\'");'], { cwd: productRoot, env: { ...process.env, WEB_ROOT: webRoot }, encoding: 'utf8' });

  await cold('servers');
  const row = page.locator('table.server-table tbody tr').filter({ hasText: 'v260-edge-01' }).first();
  await row.waitFor({ state: 'visible' });
  let button = row.locator('[data-v270-action="server"]');
  const serverId = await button.getAttribute('data-id');
  assert(Boolean(serverId), 'server data-id missing');

  report.before_filter = await clickState(button);

  if (report.before_filter.afterHash !== '#servers') {
    await cold('servers');
  }
  const toolbar = page.locator('[data-v275-toolbar="servers"]');
  await toolbar.waitFor({ state: 'visible', timeout: 10000 });
  const search = toolbar.locator('input[type="search"]');
  await search.fill('no-such-server');
  await page.waitForTimeout(120);
  await search.fill('v260-edge-01');
  const row2 = page.locator('table.server-table tbody tr').filter({ hasText: 'v260-edge-01' }).first();
  await row2.waitFor({ state: 'visible' });
  button = row2.locator('[data-v270-action="server"]');
  report.after_filter = await clickState(button);

  await page.evaluate((id) => { location.hash = `#server/${encodeURIComponent(id)}`; }, serverId);
  await page.waitForTimeout(700);
  report.direct_hash = await page.evaluate(() => ({
    hash: location.hash,
    title: document.querySelector('#v270-app h1')?.textContent?.trim() || '',
    summary: Boolean(document.querySelector('.v270-ref-summary[data-ref-lock="server-summary"]')),
    error: document.querySelector('#v270-app .v270-error')?.textContent?.trim() || '',
  }));

  report.probe = await page.evaluate(() => JSON.parse(JSON.stringify(window.__p04ServerClickProbe || {})));
} finally {
  fs.mkdirSync(evidence, { recursive: true });
  fs.writeFileSync(`${evidence}/P04_SERVER_CLICK_DIAGNOSTIC.json`, JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}

console.log(JSON.stringify({
  before: { hash: report.before_filter.afterHash, capture: report.before_filter.probe?.capture?.length, target: report.before_filter.probe?.target?.length, bubble: report.before_filter.probe?.bubble?.length, stops: report.before_filter.probe?.stops?.length, prevents: report.before_filter.probe?.prevents?.length, hashes: report.before_filter.probe?.hashes },
  after: { hash: report.after_filter.afterHash, capture: report.after_filter.probe?.capture?.length, target: report.after_filter.probe?.target?.length, bubble: report.after_filter.probe?.bubble?.length, stops: report.after_filter.probe?.stops?.length, prevents: report.after_filter.probe?.prevents?.length, hashes: report.after_filter.probe?.hashes },
  direct: report.direct_hash,
}));
