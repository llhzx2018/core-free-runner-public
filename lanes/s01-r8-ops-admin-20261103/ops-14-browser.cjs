'use strict';
/**
 * S01 R8: real logged-in WordPress admin, Ops main pinned, 14 canonical
 * product surfaces (13 routes + Tools) at 1440 and 768.
 *
 * READ-ONLY: only login posts are allowed. During actual owner page reads,
 * any same-origin non-GET/HEAD request is intercepted and fails closed.
 * No recovery/restore, publishing, plugin removal or network OAuth invoked.
 * Results are scoped to initial render/navigation, not save/readback proof.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

const origin = process.env.S01_R8_OPS_ORIGIN || 'http://127.0.0.1:18881';
const dir = process.env.S01_R8_OPS_EVIDENCE || '/tmp/s01-r8-ops-admin-evidence';
const username = process.env.S01_R8_OPS_USER || 'synthetic';
const password = process.env.S01_R8_OPS_PASSWORD || 'synthetic-only-password';
const targets = JSON.parse(fs.readFileSync(path.join(dir, 'ops-targets.json'), 'utf8'));
assert.equal(targets.length, 14, 'Ops exact canonical surface count drifted');
assert.equal(new Set(targets.map(x => x.key)).size, 14, 'Ops surface identity collision');
const widths = [1440, 768];

(async () => {
  const evidence = [], failures = [];
  fs.mkdirSync(dir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  try {
    for (const width of widths) {
      const context = await browser.newContext({ viewport: { width, height: 920 }, acceptDownloads: false });
      const login = await context.newPage();
      await login.goto(origin + '/wp-login.php', { waitUntil: 'domcontentloaded', timeout: 35000 });
      await login.locator('#user_login').fill(username);
      await login.locator('#user_pass').fill(password);
      await login.locator('#wp-submit').click();
      await login.waitForURL(url => url.pathname.startsWith('/wp-admin/'), { timeout: 35000 });
      assert(await login.locator('#wpadminbar').count() > 0, 'Login did not establish WordPress administrator session');
      await login.close();

      const blockedWrites = [];
      // Only read-only admin pages after authentication. Do not allow WP
      // heartbeat or a plugin script to submit any change during this proof.
      await context.route('**/*', async route => {
        const request = route.request();
        if (request.url().startsWith(origin) && !['GET', 'HEAD', 'OPTIONS'].includes(request.method())) {
          blockedWrites.push({ url: request.url(), method: request.method() });
          await route.abort('blockedbyclient');
        } else {
          await route.continue();
        }
      });

      for (const { key, url, label, page: expectedPage, sensitive } of targets) {
        const page = await context.newPage();
        const errors = [], missing = [];
        page.on('pageerror', e => errors.push(String(e?.message || e)));
        page.on('response', response => {
          if (response.url().startsWith(origin) && /\.(css|js)(?:\?|$)/i.test(response.url()) && response.status() >= 400) {
            missing.push({ status: response.status(), url: response.url() });
          }
        });
        const row = { key, label, width, expectedPage, sensitive, source: 'three-component-WordPress-MariaDB-Chromium', verdict: 'NOT_CHECKED' };
        try {
          const beforeBlocked = blockedWrites.length;
          assert.equal(new URL(url).origin, origin, 'Admin URL must remain on isolated origin');
          const response = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
          row.status = response?.status() || 0;
          await page.locator('.vf-ops-admin-shell [data-vf-v13-route]').first().waitFor({ state: 'attached', timeout: 25000 });
          // Give bundled JS/CSS time to execute, without initiating tasks.
          await page.waitForLoadState('load', { timeout: 20000 });
          await page.evaluate(() => document.fonts.ready);
          row.dom = await page.evaluate(() => {
            const root = document.querySelector('.vf-ops-admin-shell');
            const canvas = root?.querySelector('[data-vf-v13-route]');
            const main = root?.querySelector('main.vf-v6-shell-main');
            const header = root?.querySelector('header.vf-v6-shell-header');
            const heading = main ? [...main.querySelectorAll('h1')].filter(el => el.getBoundingClientRect().height > 0) : [];
            const nav = [...(root?.querySelectorAll('.vf-v6-domain-nav [data-vf-s01-domain]') || [])].map(x => x.dataset.vfS01Domain);
            const scripts = [...document.querySelectorAll('script[src]')].filter(el => el.src.startsWith(location.origin));
            const styles = [...document.querySelectorAll('link[rel="stylesheet"]')].filter(el => el.href.startsWith(location.origin));
            return {
              shell: !!root, header: !!header, main: !!main,
              key: canvas?.getAttribute('data-vf-v13-route') || '',
              shellDomain: root?.getAttribute('data-vf-s01-domain') || '',
              headerVisible: !!header && header.getBoundingClientRect().height > 20,
              canvasHeight: canvas?.getBoundingClientRect().height || 0,
              headingCount: heading.length,
              headings: heading.map(n => n.textContent.trim()).slice(0, 4),
              domains: nav,
              width: innerWidth,
              docWidth: document.documentElement.scrollWidth,
              stylesheetCount: styles.length, scriptCount: scripts.length,
              errorPage: /there has been a critical error|sorry, you are not allowed to access this page|fatal error/i.test(
                (document.querySelector('#wpbody-content')?.textContent || '').slice(0, 3000)
              )
            };
          });
          assert.equal(row.status, 200, key + ': live wp-admin HTTP must be 200');
          assert(row.dom.shell && row.dom.header && row.dom.main && row.dom.headerVisible, key + ': shared actual Ops shell missing');
          assert.equal(row.dom.key, key, key + ': wrong real dispatched controller/workspace');
          assert.equal(row.dom.domWidth, undefined); // no synthetic width proxy
          assert(row.dom.canvasHeight > 35, key + ': route canvas is empty or collapsed');
          assert.equal(row.dom.headingCount, 1, key + ': must have exactly one visible product heading');
          assert.equal(new Set(row.dom.domains).size, 6, key + ': one six-domain product navigation required');
          assert(row.dom.stylesheetCount > 0, key + ': no first-party stylesheets loaded');
          assert(row.dom.docWidth <= width + 2, key + ': horizontal page overflow');
          assert(!row.dom.errorPage, key + ': WordPress fatal/permission page rendered');
          assert.deepEqual(errors, [], key + ': uncaught real browser JavaScript errors');
          assert.deepEqual(missing, [], key + ': first-party CSS/JS returned non-200');
          // Safe interaction with actual shell navigation, not business writes.
          if (key === 'dashboard' || key === 'tools' || key === 'system_plugins') {
            const nav = page.locator('.vf-v6-domain-mobile > summary');
            if (width === 768 && await nav.isVisible()) {
              await nav.click();
              assert(await page.locator('.vf-v6-domain-mobile').evaluate(el => el.open), key + ': mobile nav did not open');
              await nav.click();
              assert(!await page.locator('.vf-v6-domain-mobile').evaluate(el => el.open), key + ': mobile nav did not close');
              row.navToggle = 'PASS';
            }
          }
          assert.equal(blockedWrites.length, beforeBlocked, key + ': attempted automatic write on ordinary admin GET');
          if (width === 1440) {
            await page.screenshot({ path: path.join(dir, 'ops-' + key + '-1440.jpeg'), fullPage: true, type: 'jpeg', quality: 65 });
          }
          row.verdict = 'PASS';
        } catch (e) {
          row.verdict = 'FAIL';
          row.error = String(e?.message || e);
          row.clientErrors = errors;
          row.badAssets = missing;
          failures.push({ key, width, error: row.error, dom: row.dom || null, errors: errors.slice(0,5) });
        } finally {
          evidence.push(row);
          await page.close();
        }
      }
      await context.close();
      if (blockedWrites.length) failures.push({ width, error: 'Blocked unexpected unsafe automatic admin requests', blockedWrites });
    }
  } finally {
    await browser.close();
  }
  const report = {
    scope: '14 Ops canonical owner surfaces at 1440 and 768; actual admin login/read/navigation only',
    exactOpsSha: process.env.S01_R8_OPS_SHA || '',
    total: evidence.length, passed: evidence.filter(x=>x.verdict==='PASS').length,
    failed: failures.length, failures, pages: evidence,
    permissionBoundary: 'real manage_options synthetic localhost admin',
    operations: 'GET only after one isolated login; no save/recovery/publish/plugin deletion/OAuth',
    ownerProductionApproval: false
  };
  fs.writeFileSync(path.join(dir, 'ops-14-results.json'), JSON.stringify(report,null,2));
  console.log('S01_R8_OPS_14_ACTUAL_ADMIN_CHROMIUM ' + JSON.stringify({
    total:report.total,passed:report.passed,failed:report.failed,failures:report.failures
  }));
  assert.equal(failures.length,0,'Ops 14-surface actual admin READ gate must pass');
})().catch(e=>{console.error(e?.stack||e);process.exitCode=1;});
