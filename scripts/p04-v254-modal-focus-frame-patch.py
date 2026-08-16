from pathlib import Path

p = Path('scripts/p04-v254-browser-e2e.mjs')
s = p.read_text(encoding='utf-8')
old = """await page.waitForFunction(() => document.querySelector('#modal')?.getAttribute('aria-hidden') === 'true');
assert(await newProject.evaluate((b) => b === document.activeElement), 'modal did not return focus to opener');"""
new = """await page.waitForFunction(() => document.querySelector('#modal')?.getAttribute('aria-hidden') === 'true');
await page.waitForFunction(() => document.querySelector('#page-actions [data-action=\"new-project\"]') === document.activeElement);
assert(await newProject.evaluate((b) => b === document.activeElement), 'modal did not return focus to opener');"""
if s.count(old) != 1:
    raise SystemExit(f'modal focus assertion sentinel mismatch: {s.count(old)}')
p.write_text(s.replace(old, new, 1), encoding='utf-8')
print('MODAL_FOCUS_FRAME_PATCH=PASS')
