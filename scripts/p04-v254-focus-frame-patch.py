from pathlib import Path

p = Path('scripts/p04-v254-browser-e2e.mjs')
s = p.read_text(encoding='utf-8')
old = """await page.waitForFunction(() => document.querySelector('#drawer')?.getAttribute('aria-hidden') === 'true');
assert(await newDomain.evaluate((b) => b === document.activeElement), 'drawer did not return focus to opener');"""
new = """await page.waitForFunction(() => document.querySelector('#drawer')?.getAttribute('aria-hidden') === 'true');
await page.waitForFunction(() => document.querySelector('#page-actions [data-action=\"new-domain\"]') === document.activeElement);
assert(await newDomain.evaluate((b) => b === document.activeElement), 'drawer did not return focus to opener');"""
if s.count(old) != 1:
    raise SystemExit(f'drawer focus assertion sentinel mismatch: {s.count(old)}')
p.write_text(s.replace(old, new, 1), encoding='utf-8')
print('DRAWER_FOCUS_FRAME_PATCH=PASS')
