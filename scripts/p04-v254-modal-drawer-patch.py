from pathlib import Path

p = Path('scripts/p04-v254-browser-e2e.mjs')
s = p.read_text(encoding='utf-8')
old = '''const newDomain = page.getByRole('button', { name: '新增域名' });
assert(await newDomain.count() >= 1, 'new-domain primary action missing');
await newDomain.click();
await page.waitForFunction(() => document.querySelector('#modal')?.getAttribute('aria-hidden') === 'false');
assert(await page.locator('#modal[role="dialog"][aria-modal="true"]').count() === 1, 'modal semantics missing');
assert(await page.locator('#modal').evaluate((m) => m.contains(document.activeElement)), 'modal initial focus not trapped');
await shot('modal-new-domain');
await page.keyboard.press('Tab');
assert(await page.locator('#modal').evaluate((m) => m.contains(document.activeElement)), 'modal tab focus escaped');
await page.keyboard.press('Escape');
await page.waitForFunction(() => document.querySelector('#modal')?.getAttribute('aria-hidden') === 'true');
assert(await newDomain.evaluate((b) => b === document.activeElement), 'modal did not return focus to opener');

// Settings subpages and save-state success.'''
new = '''// Lightweight create action uses Modal.
await page.locator('.nav-item[data-nav="projects"]').click();
await settle(180);
const newProject = page.getByRole('button', { name: '新增项目' });
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
const newDomain = page.getByRole('button', { name: '新增域名' });
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

// Settings subpages and save-state success.'''
if s.count(old) != 1:
    raise SystemExit(f'modal/drawer block sentinel mismatch: {s.count(old)}')
p.write_text(s.replace(old, new, 1), encoding='utf-8')
print('MODAL_DRAWER_E2E_PATCH=PASS')
