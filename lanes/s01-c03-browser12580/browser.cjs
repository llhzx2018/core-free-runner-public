'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium } = require('playwright');
const base = 'http://127.0.0.1:18880';
const checks = [], errors = [];
const check = (ok, name, detail = null) => {
  checks.push({ name, pass: !!ok, detail });
  assert(ok, name + (detail == null ? '' : ': ' + JSON.stringify(detail).slice(0, 250)));
};
async function waitDone(page) {
  await page.waitForFunction(() => {
    const r = document.querySelector('[data-vf-module="browser-stream-test"]');
    return r && r.getAttribute('data-vf-browser-stream-has-result') === '1'
      && r.getAttribute('data-vf-browser-stream-busy') === '0';
  }, null, { timeout: 60000 });
}
(async () => {
  const browser = await chromium.launch({ headless: true, args: ['--autoplay-policy=no-user-gesture-required'] });
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 920 }, permissions: ['clipboard-read','clipboard-write'], acceptDownloads: true });
    const page = await context.newPage();
    page.on('pageerror', e => errors.push(String(e.message).slice(0, 170)));
    const response = await page.goto(base + '/m3u8-browser-stream-test/', { waitUntil: 'domcontentloaded', timeout: 60000 });
    check(response && response.status() === 200, 'published WordPress test route returns HTTP 200', response?.status());
    const root = page.locator('[data-vf-module="browser-stream-test"]').first();
    check((await root.count()) === 1, 'plugin shortcode mounts browser tester exactly once');
    await page.waitForFunction(() => !!document.querySelector('[data-vf-module="browser-stream-test"]')?.getAttribute('data-vf-browser-stream-events-bound'), null, {timeout: 30000});
    check(!!(await root.getAttribute('data-vf-browser-stream-events-bound')), 'browser runtime really binds events');
    check((await root.locator('[data-vf-primary-action]').count()) === 1, 'exactly one primary action');
    check(await root.locator('[data-vf-browser-stream-mode-button="pro"]').count() === 1, 'professional mode entry exists');
    check(await root.locator('[data-vf-browser-stream-result-shell]').isHidden(), 'result starts hidden');
    await root.locator('[data-vf-browser-stream-check]').click();
    check((await root.getAttribute('data-vf-browser-stream-has-result')) !== '1', 'empty URL cannot fake pass');
    check(await root.locator('[data-vf-browser-stream-recovery]').isVisible(), 'empty input gives actionable recovery');
    await root.locator('[data-vf-browser-stream-url]').fill('not-a-media-url');
    await root.locator('[data-vf-browser-stream-check]').click();
    check((await root.locator('[data-vf-browser-stream-status]').innerText()).length > 8, 'invalid URL supplies readable error');
    await root.locator('[data-vf-browser-stream-mode-button="pro"]').click();
    check((await root.getAttribute('data-vf-browser-stream-mode')) === 'pro', 'professional mode switches');
    const manual = root.locator('[data-vf-browser-stream-manifest]');
    await manual.fill('#EXTM3U\n#EXT-X-TARGETDURATION:2\n#EXTINF:2,\nseg.ts\n#EXT-X-ENDLIST');
    await root.locator('[data-vf-browser-stream-check]').click();
    await waitDone(page);
    check((await root.locator('[data-vf-browser-stream-signal]').getAttribute('data-state')) === 'manual', 'pasted text is classified MANUAL, not playback PASS');
    await root.locator('[data-vf-browser-stream-clear]').click();
    check((await root.getAttribute('data-vf-browser-stream-has-result')) !== '1', 'clear invalidates previous report');
    await root.locator('[data-vf-browser-stream-mode-button="simple"]').click();
    await root.locator('[data-vf-browser-stream-sample]').click();
    await waitDone(page);
    const sampleState = await root.locator('[data-vf-browser-stream-signal]').getAttribute('data-state');
    check(sampleState === 'success', 'bundled fixture reaches real playback success', sampleState);
    const media = await root.locator('[data-vf-browser-video]').evaluate(v => ({ readyState:v.readyState, width:v.videoWidth, height:v.videoHeight, error:v.error?.code || 0 }));
    check(media.readyState >= 2 && media.width > 0 && !media.error, 'real decoded video has media dimensions', media);
    const sampleUrl = await root.locator('[data-vf-browser-stream-url]').inputValue();
    check(sampleUrl.includes('demo.m3u8'), 'sample populates real bundled media URL');
    await root.locator('[data-vf-browser-stream-clear]').click();
    const signedToken = 'SYNTHETIC_PRIVATE_TOKEN_12580';
    await root.locator('[data-vf-browser-stream-url]').fill(sampleUrl + '?auth=' + signedToken);
    await root.locator('[data-vf-browser-stream-check]').click();
    await waitDone(page);
    check(await root.locator('[data-vf-browser-stream-copy]').isEnabled(), 'copy report enabled after actual signed run');
    await root.locator('[data-vf-browser-stream-copy]').click();
    const copied = await page.evaluate(() => navigator.clipboard.readText());
    check(copied.length > 50 && !copied.includes(signedToken), 'copied report strips signed query tokens', copied.length);
    const dlPromise = page.waitForEvent('download', { timeout: 12000 });
    await root.locator('[data-vf-browser-stream-export]').click();
    const dl = await dlPromise;
    const exported = fs.readFileSync(await dl.path(), 'utf8');
    const json = JSON.parse(exported);
    check(!!json.issueCodes && !exported.includes(signedToken) && !exported.includes('mediaManifestText'), 'downloaded JSON is parseable and excludes token and raw manifest');
    check(dl.suggestedFilename().endsWith('.json'), 'export produces JSON download');
    await root.locator('[data-vf-browser-stream-clear]').click();
    check((await root.locator('[data-vf-browser-stream-status]').innerText()).length > 0, 'clear produces visible status');
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(600);
    const visual = await root.evaluate(el => {
      const button = el.querySelector('[data-vf-browser-stream-check]');
      const bounds = el.getBoundingClientRect();
      return { font: parseFloat(getComputedStyle(el).fontSize), buttonHeight: button.getBoundingClientRect().height, rootWidth: bounds.width, screen: window.innerWidth, scrollWidth: document.documentElement.scrollWidth };
    });
    check(visual.font >= 15, 'mobile font readable >=15px', visual);
    check(visual.buttonHeight >= 44, 'touch target height >=44px', visual);
    check(visual.rootWidth <= visual.screen + 2, 'browser tester fits 390px viewport', visual);
    check(errors.length === 0, 'no uncaught browser JavaScript exceptions', errors);
    await page.screenshot({ path:'proof/bst-390.png', fullPage: true });
    fs.writeFileSync('proof/browser.json', JSON.stringify({ status:'PASS', checks, production:'NOT_EXECUTED' }, null, 2));
    console.log('BROWSER_WORDPRESS_M3U8_PASS', JSON.stringify({ checks:checks.length, media, visual }));
  } finally { await browser.close(); }
})().catch(err => { console.error('BROWSER_WORDPRESS_M3U8_FAIL', err.stack || String(err), JSON.stringify({checks,errors}).slice(0,3000)); process.exitCode = 1; });
