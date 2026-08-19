import { chromium } from 'playwright';
import fs from 'node:fs';

const base = process.env.P01_BASE || 'http://127.0.0.1:18121/';
const evidenceDir = process.env.P01_EVIDENCE || 'evidence';
let browser;
try {
  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));

  await page.goto(base, { waitUntil: 'networkidle' });
  await page.click('#loginButton');
  await page.fill('[name=password]', 'MaintenanceTest!2026');
  await page.click('#loginSubmit');
  await page.waitForFunction(() => document.body.classList.contains('is-admin'));
  await page.waitForSelector('.category-row--root');

  // Home is a stable starting point: category rail always starts at the top.
  await page.evaluate(() => document.getElementById('sidebarScroll').scrollTop = 450);
  await page.click('[data-view="home"]');
  await page.waitForTimeout(160);
  const homeTop = await page.evaluate(() => document.getElementById('sidebarScroll').scrollTop);
  if (homeTop > 2) throw new Error('HOME_SCROLL_TOP ' + homeTop);

  // Expanding a lower root must not move the navigation viewport.
  const roots = page.locator('[data-root-wrap]');
  const rootCount = await roots.count();
  if (rootCount < 8) throw new Error('ROOT_FIXTURE ' + rootCount);
  const target = roots.nth(rootCount - 3);
  await target.scrollIntoViewIfNeeded();
  await page.waitForTimeout(80);
  const before = await page.evaluate(() => document.getElementById('sidebarScroll').scrollTop);
  await target.locator('.nav-chevron').click();
  await page.waitForTimeout(180);
  const after = await page.evaluate(() => document.getElementById('sidebarScroll').scrollTop);
  if (Math.abs(after - before) > 2) throw new Error(`EXPAND_JUMP ${before}->${after}`);
  await target.locator('.category-row--child').first().waitFor({ state: 'visible' });

  const geom = await target.evaluate(root => {
    const rr = root.querySelector('.category-row--root');
    const cr = root.querySelector('.category-row--child');
    const rm = rr.querySelector('.category-nav-main');
    const cm = cr.querySelector('.category-nav-main');
    const rc = rr.querySelector('.nav-count');
    const cc = cr.querySelector('.nav-count');
    const cl = cr.querySelector('.nav-label');
    return {
      rootH: rr.getBoundingClientRect().height,
      childH: cr.getBoundingClientRect().height,
      rootFont: getComputedStyle(rm).fontSize,
      childFont: getComputedStyle(cm).fontSize,
      rootCountW: rc.getBoundingClientRect().width,
      childCountW: cc.getBoundingClientRect().width,
      rootCountFont: getComputedStyle(rc).fontSize,
      childCountFont: getComputedStyle(cc).fontSize,
      childOverflow: cl.scrollWidth - cl.clientWidth,
    };
  });
  if (Math.abs(geom.rootH - 36) > 1 || Math.abs(geom.childH - 36) > 1) throw new Error('ROW_HEIGHT ' + JSON.stringify(geom));
  if (geom.rootFont !== '13px' || geom.childFont !== '13px') throw new Error('ROW_FONT ' + JSON.stringify(geom));
  if (Math.abs(geom.rootCountW - 30) > 1 || Math.abs(geom.childCountW - 30) > 1 || geom.rootCountFont !== '11px' || geom.childCountFont !== '11px') throw new Error('COUNT_ALIGN ' + JSON.stringify(geom));
  if (geom.childOverflow > 1) throw new Error('CHILD_TRUNCATED ' + JSON.stringify(geom));

  await target.locator('.category-row--child .category-nav-main').first().click();
  await page.waitForTimeout(140);
  const active = await page.locator('.category-row.active').first().evaluate(el => ({
    bg: getComputedStyle(el).backgroundColor,
    beforeDisplay: getComputedStyle(el, '::before').display,
    beforeContent: getComputedStyle(el, '::before').content,
  }));
  if (active.beforeDisplay !== 'none' && active.beforeContent !== 'none') throw new Error('GREEN_RAIL ' + JSON.stringify(active));
  if (active.bg !== 'rgb(241, 243, 242)') throw new Error('ACTIVE_NOT_NEUTRAL ' + JSON.stringify(active));

  for (const width of [390, 480, 640, 768, 1024, 1280, 1440, 1920]) {
    await page.setViewportSize({ width, height: 900 });
    await page.waitForTimeout(60);
    const overflow = await page.evaluate(() => Math.max(
      document.documentElement.scrollWidth - document.documentElement.clientWidth,
      document.body.scrollWidth - document.body.clientWidth,
    ));
    if (overflow > 1) throw new Error(`FRONT_OVERFLOW ${width} ${overflow}`);
  }

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(base + 'links-admin.php', { waitUntil: 'networkidle' });
  const top = await page.locator('.vf-rail-item>span').allTextContents();
  const expected = ['网址', '浏览器助手', '备份与恢复', '设置', '更新'];
  if (JSON.stringify(top) !== JSON.stringify(expected)) throw new Error('ADMIN_TOP ' + JSON.stringify(top));
  const subs = await page.locator('.vf-rail-section.active .vf-rail-subitem').allTextContents();
  for (const label of ['网址健康', '重复网址', '导入导出']) if (!subs.includes(label)) throw new Error('MISSING_MERGE ' + label);
  for (const label of ['标签', '推广链接', '网址图标', '高级']) if (subs.includes(label) || top.includes(label)) throw new Error('RETIRED_NAV ' + label);

  await page.click('#addLink');
  await page.waitForSelector('#editDialog[open]');
  if (await page.getByText('标签', { exact: true }).count()) throw new Error('TAG_EDIT_FIELD_REMAINS');
  await page.locator('#editDialog .vf-dialog-close').click();

  const redirects = [
    ['manage.php', 'links-admin.php'],
    ['tags.php', 'links-admin.php?notice=tags-retired'],
    ['affiliate.php', 'links-admin.php?notice=affiliate-retired'],
    ['governance.php', 'links-admin.php?notice=governance-retired'],
    ['icons.php', 'settings.php#display'],
    ['jobs.php', 'system.php'],
    ['security.php', 'settings.php#account'],
  ];
  for (const [from, to] of redirects) {
    await page.goto(base + from, { waitUntil: 'networkidle' });
    if (!page.url().includes(to)) throw new Error(`REDIRECT ${from} ${page.url()}`);
  }

  await page.goto(base + 'tags.php', { waitUntil: 'networkidle' });
  const notice = await page.locator('[role="status"]').textContent();
  if (!notice.includes('标签功能已退役')) throw new Error('TAG_NOTICE');

  await page.goto(base + 'plugins.php', { waitUntil: 'networkidle' });
  if (!(await page.locator('h1').textContent()).includes('RSS 与扩展')) throw new Error('RSS_SETTINGS');
  await page.goto(base + 'system.php', { waitUntil: 'networkidle' });
  if (!(await page.locator('h1').textContent()).includes('系统状态')) throw new Error('SYSTEM_SETTINGS');

  // Simulate a successful future Atomic update. The new runtime must reload itself.
  await page.goto(base + 'update.php', { waitUntil: 'networkidle' });
  await page.evaluate(() => {
    const steps = document.getElementById('updateSteps');
    steps.hidden = false;
    steps.textContent = '✓ Atomic 升级完成 ✓ 更新完成';
    document.getElementById('updateState').textContent = '更新完成，当前版本：V2.21.21';
  });
  await page.waitForURL(u => u.searchParams.has('vf_refresh'), { timeout: 5000 });

  if (errors.length) throw new Error('PAGE_ERRORS ' + errors.join(' | '));
  const result = {
    pass: true,
    homeTop,
    before,
    after,
    geom,
    active,
    adminTop: top,
    urlSubmenu: subs,
    redirects: 'PASS',
    autoReload: 'PASS',
    responsive: '390-1920 PASS',
    pageErrors: 0,
  };
  fs.writeFileSync(`${evidenceDir}/browser.json`, JSON.stringify(result, null, 2));
  console.log('P01_22121_BROWSER_PASS');
} catch (e) {
  fs.writeFileSync(`${evidenceDir}/browser-error.txt`, String(e?.stack || e) + '\n');
  throw e;
} finally {
  if (browser) await browser.close();
}
