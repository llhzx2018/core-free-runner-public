import { chromium } from 'playwright';

const origin = process.env.P01_TEST_ORIGIN || 'http://127.0.0.1:18621';
const password = process.env.P01_TEST_PASSWORD;
if (!password) throw new Error('BLOCKED_FIXTURE: missing synthetic Owner password');

const routes = [
  ['home', 'index.php'],
  ['start', 'start.php'],
  ['inbox', 'inbox.php'],
  ['channels', 'channels.php'],
  ['watch', 'watch.php'],
  ['music', 'music-home.php'],
  ['topics', 'topics.php'],
  ['courses', 'courses.php'],
  ['projects', 'projects.php'],
  ['tools', 'tools.php'],
  ['software', 'software.php']
];
const guestRoutes = routes.filter(row => row[0] !== 'inbox' && row[0] !== 'music');
const failures = [];
const passed = [];
const assert = (ok, message) => { if (!ok) throw new Error(message); };
const record = async (label, operation) => {
  try {
    await operation();
    passed.push(label);
    console.log('BROWSER_PASS:' + label);
  } catch (error) {
    failures.push({case: label, reason: String(error?.message || error).slice(0,480)});
    console.log('BROWSER_FAIL:' + label);
  }
};
const browser = await chromium.launch({headless: true, args: ['--no-sandbox']});
try {
  const owner = await browser.newContext({viewport: {width: 1440, height: 900}});
  await owner.route(/https?:\/\/(?!127\.0\.0\.1)/, request => request.abort());
  const login = await owner.request.post(origin + '/api.php?action=login', {data: {password}});
  assert(login.status() === 200 && (await login.text()).includes('"ok":true'), 'BLOCKED_FIXTURE: synthetic Owner login failed');
  const page = await owner.newPage();
  for (const width of [1440, 768]) {
    await page.setViewportSize({width, height: 900});
    for (const [mode, route] of routes) {
      await record('owner/' + width + '/' + mode, async () => {
        const response = await page.goto(origin + '/' + route, {waitUntil: 'domcontentloaded', timeout: 30000});
        assert(response?.status() === 200, 'source route HTTP ' + response?.status());
        const launcher = page.locator('[data-vf-local-manage-open]');
        await launcher.waitFor({state: 'visible', timeout: 12000});
        assert(await launcher.count() === 1, 'expected one Owner management launcher');
        await page.waitForFunction(() => Boolean(window.VFLocalManagementReturn), null, {timeout: 12000});
        assert(await page.locator('dialog[data-vf-local-management]').count() === 1, 'one native dialog missing');
        const before = new URL(page.url()).pathname;
        await launcher.click();
        const modal = page.locator('dialog[data-vf-local-management]');
        await modal.waitFor({state: 'visible', timeout: 12000});
        assert(await modal.evaluate(el => el.open && el.matches(':modal')), 'dialog.showModal() must own one modal');
        assert(new URL(page.url()).pathname === before, 'launch navigated away from current subsite');
        assert(await modal.locator('iframe').count() === 0, 'iframe detected inside modal');
        assert(await modal.locator('a[href*="manage.php"]').count() === 0, 'backend management link inside modal');
        const tasks = modal.locator('[data-vf-local-task]');
        const taskIds = await tasks.evaluateAll(nodes => nodes.map(node => node.dataset.vfLocalTask));
        assert(taskIds.length > 0, 'no usable task in modal');
        const selected = modal.locator('[data-vf-local-task][aria-pressed="true"]');
        assert(await selected.count() === 1, 'exactly one task should be selected');
        const dialogShape = await modal.evaluate(el => {
          const r = el.getBoundingClientRect();
          return {left: r.left, right: r.right, top: r.top, bottom: r.bottom, viewportWidth: innerWidth, viewportHeight: innerHeight};
        });
        assert(dialogShape.left >= -2 && dialogShape.right <= dialogShape.viewportWidth + 2, 'modal overflows horizontal viewport');
        assert(dialogShape.top >= -2 && dialogShape.bottom <= dialogShape.viewportHeight + 2, 'modal overflows vertical viewport');
        if (taskIds.length > 1) {
          const currentId = await selected.first().getAttribute('data-vf-local-task');
          const nextId = taskIds.find(id => id !== currentId);
          await modal.locator('[data-vf-local-task="' + nextId + '"]').click();
          assert(await modal.locator('[data-vf-local-task][aria-pressed="true"]').count() === 1, 'task switch lost selected state');
          assert(await modal.locator('[data-vf-local-task="' + nextId + '"]').getAttribute('aria-pressed') === 'true', 'wrong selected task');
          assert(new URL(page.url()).pathname === before, 'task switch navigated away');
        }
        await modal.locator('[data-vf-local-manage-close]').first().click();
        assert(!(await modal.evaluate(el => el.open)), 'close button did not close modal');
        assert(await launcher.evaluate(el => document.activeElement === el), 'focus not restored to opener');
        assert(new URL(page.url()).pathname === before, 'close navigated away');
      });
    }
  }
  await page.setViewportSize({width: 1440, height: 900});
  await record('inbox/capture-unsaved-guard', async () => {
    const response = await page.goto(origin + '/inbox.php', {waitUntil: 'domcontentloaded'});
    assert(response?.status() === 200, 'Inbox route unavailable');
    await page.locator('[data-vf-local-manage-open]').click();
    const modal = page.locator('dialog[data-vf-local-management]');
    await modal.locator('[data-vf-local-task="capture"]').click();
    const input = modal.locator('[data-vf-local-capture-url]');
    await input.fill('https://example.com/synthetic-unsaved-pr1820');
    let confirmations = 0;
    page.once('dialog', async prompt => { confirmations++; await prompt.dismiss(); });
    await modal.locator('[data-vf-local-task="governance"]').click();
    assert(confirmations === 1, 'dirty draft switch did not request confirmation');
    assert((await input.inputValue()).includes('synthetic-unsaved'), 'dismissed confirmation discarded draft');
    assert(await modal.locator('[data-vf-local-task="capture"]').getAttribute('aria-pressed') === 'true', 'dismissed confirmation changed task');
    page.once('dialog', async prompt => { confirmations++; await prompt.dismiss(); });
    await page.keyboard.press('Escape');
    assert(confirmations === 2 && await modal.evaluate(el => el.open), 'Escape bypassed dirty guard');
    page.once('dialog', async prompt => { confirmations++; await prompt.accept(); });
    await modal.locator('[data-vf-local-task="governance"]').click();
    assert(confirmations === 3, 'accepting discard confirmation was not requested');
    assert(await input.inputValue() === '', 'accepted discard did not reset draft');
    assert(await modal.locator('[data-vf-local-task="governance"]').getAttribute('aria-pressed') === 'true', 'accepted discard did not switch task');
    await modal.locator('[data-vf-local-manage-close]').first().click();
  });
  const captureName = 'P01 Synthetic Browser Capture 1820';
  await record('inbox/capture-save-and-refresh', async () => {
    const response = await page.goto(origin + '/inbox.php', {waitUntil: 'domcontentloaded'});
    assert(response?.status() === 200, 'Inbox route unavailable');
    const before = new URL(page.url()).pathname;
    await page.locator('[data-vf-local-manage-open]').click();
    const modal = page.locator('dialog[data-vf-local-management]');
    await modal.locator('[data-vf-local-task="capture"]').click();
    await modal.locator('[data-vf-local-capture-url]').fill('https://example.com/p01-pr1820-real-browser-capture');
    await modal.locator('[data-vf-local-capture-form] input[name="title"]').fill(captureName);
    await modal.locator('[data-vf-local-capture-submit]').click();
    await page.waitForFunction(() => {
      const node = document.querySelector('[data-vf-local-capture-status]');
      return Boolean(node && node.textContent.includes('已保存到私人待整理'));
    }, null, {timeout: 15000});
    assert(new URL(page.url()).pathname === before && await modal.evaluate(el => el.open), 'save navigated instead of updating same modal');
    assert(await modal.locator('[data-vf-local-capture-url]').inputValue() === '', 'saved input not reset');
    await modal.locator('[data-vf-local-manage-close]').first().click();
    await page.goto(origin + '/inbox.php', {waitUntil: 'domcontentloaded'});
    assert((await page.locator('body').innerText()).includes(captureName), 'saved private capture missing after Inbox refresh');
  });
  await record('tools/workflow-save-and-refresh', async () => {
    const response = await page.goto(origin + '/tools.php', {waitUntil: 'domcontentloaded'});
    assert(response?.status() === 200, 'Tools route unavailable');
    const before = new URL(page.url()).pathname;
    await page.locator('[data-vf-local-manage-open]').click();
    const modal = page.locator('dialog[data-vf-local-management]');
    await modal.locator('[data-vf-local-task="toolbox"]').click();
    await page.waitForFunction(() => {
      const node = document.querySelector('[data-vf-local-toolbox-scene]');
      return Boolean(node && node.options.length > 0);
    }, null, {timeout: 15000});
    const form = modal.locator('[data-vf-local-toolbox-form]');
    const status = modal.locator('[data-vf-local-toolbox-status]');
    await form.locator('[data-vf-local-toolbox-new]').click();
    const label = 'P01 Browser Synthetic Workflow 1820';
    await form.locator('input[name="name"]').fill(label);
    await form.locator('input[name="copy"]').fill('仅合成环境的保存刷新验证');
    await form.locator('textarea[name="keywords"]').fill('synthetic-validation');
    await form.locator('[data-vf-local-toolbox-save]').click();
    await page.waitForFunction(() => document.querySelector('[data-vf-local-toolbox-status]')?.textContent?.includes('已保存，工具箱列表已更新'), null, {timeout: 20000});
    assert(!/失败|未确认|暂未加载/.test(await status.innerText()), 'toolbox acknowledged save without usable refresh');
    assert(await form.locator('[data-vf-local-toolbox-group]').inputValue() === label, 'post-save group not immediately selected');
    assert(await form.locator('input[name="name"]').inputValue() === label, 'post-save workflow editor not refreshed');
    assert(new URL(page.url()).pathname === before, 'toolbox save navigated away');
    await modal.locator('[data-vf-local-manage-close]').first().click();
    await page.locator('[data-vf-local-manage-open]').click();
    await modal.locator('[data-vf-local-task="toolbox"]').click();
    await page.waitForFunction(expected => Array.from(document.querySelector('[data-vf-local-toolbox-group]')?.options || []).some(o => o.value === expected), label, {timeout: 15000});
    assert(await modal.locator('[data-vf-local-toolbox-group] option[value="' + label + '"]').count() === 1, 'saved workflow not persisted on reopen');
    await modal.locator('[data-vf-local-manage-close]').first().click();
  });
  const visitor = await browser.newContext({viewport: {width: 1440, height: 900}});
  await visitor.route(/https?:\/\/(?!127\.0\.0\.1)/, request => request.abort());
  const guestPage = await visitor.newPage();
  for (const [mode, route] of guestRoutes) {
    await record('guest/' + mode + '/owner-action-boundary', async () => {
      const resp = await guestPage.goto(origin + '/' + route, {waitUntil: 'domcontentloaded', timeout: 30000});
      assert(resp && resp.status() < 500, 'guest route error');
      assert(await guestPage.locator('[data-vf-local-manage-open]').count() === 0, 'guest sees Owner launcher');
      assert(await guestPage.locator('dialog[data-vf-local-management]').count() === 0, 'guest sees Owner dialog markup');
      assert(!(await guestPage.locator('body').innerText()).includes(captureName), 'guest leaked private capture');
    });
  }
  await record('guest/inbox-private-boundary', async () => {
    await guestPage.goto(origin + '/inbox.php', {waitUntil: 'domcontentloaded'});
    assert(!(await guestPage.locator('body').innerText()).includes(captureName), 'guest can read private Inbox capture');
  });
  await owner.close();
  await visitor.close();
} finally {
  await browser.close();
}
console.log(JSON.stringify({
  schema: 'p01-pr1820-isolated-native-browser/v1',
  passed: passed.length,
  failed: failures.length,
  failures: failures.slice(0, 40)
}));
if (failures.length) process.exit(1);
console.log('P01_PR1820_NATIVE_MODAL_BROWSER=PASS');
