import asyncio
import json
import os
import shutil
from pathlib import Path
from playwright.async_api import async_playwright

BASE = f"http://127.0.0.1:{os.environ['PORT']}"
PASSWORD = os.environ['ADMIN_PASS']
EVID = Path(os.environ['EVID'])
RESULT = {}

async def no_overflow(page, label):
    dims = await page.evaluate("() => ({sw:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth})")
    assert dims['sw'] <= dims['cw'] + 1, (label, dims)
    return dims

async def grid_info(page, selector, label, min_copy):
    el = page.locator(selector).first
    await el.wait_for(state='visible')
    info = await el.evaluate("""el => ({
      grid: getComputedStyle(el).gridTemplateColumns,
      width: el.getBoundingClientRect().width,
      hasSelect: !!el.querySelector(':scope > .vf-asset-select'),
      copyWidth: (el.querySelector('.vf-asset-copy') || el.querySelector('.vf-watch-copy') || el.querySelector('.vf-topic-copy'))?.getBoundingClientRect().width || 0
    })""")
    assert info['copyWidth'] >= min_copy, (label, info)
    return info

async def check_anonymous(page, width, suffix):
    out = {}
    r = await page.goto(BASE + '/start.php', wait_until='networkidle'); assert r and r.ok
    assert await page.locator('body.vf-functional-workspace').count() == 1
    start = await grid_info(page, '.surface-start .vf-asset-row', f'{width}-{suffix}-start', 105 if width <= 430 else 300)
    assert start['hasSelect'] is False, start
    assert len(start['grid'].split()) == 3, start
    out['start'] = start
    out['start_overflow'] = await no_overflow(page, f'{width}-{suffix}-start')
    await page.screenshot(path=str(EVID / 'screens' / f'{width}-{suffix}-start.png'), full_page=False)

    r = await page.goto(BASE + '/channels.php', wait_until='networkidle'); assert r and r.ok
    channels = await grid_info(page, '.surface-channels .vf-asset-row', f'{width}-{suffix}-channels', 95 if width <= 430 else 170)
    assert channels['hasSelect'] is False, channels
    assert len(channels['grid'].split()) == 3, channels
    out['channels'] = channels
    out['channels_overflow'] = await no_overflow(page, f'{width}-{suffix}-channels')
    await page.screenshot(path=str(EVID / 'screens' / f'{width}-{suffix}-channels.png'), full_page=False)

    r = await page.goto(BASE + '/start.php?layout=cards', wait_until='networkidle'); assert r and r.ok
    card = await grid_info(page, '.vf-asset-card', f'{width}-{suffix}-card', 90 if width <= 430 else 140)
    assert card['hasSelect'] is False, card
    assert len(card['grid'].split()) == 2, card
    out['card'] = card
    out['card_overflow'] = await no_overflow(page, f'{width}-{suffix}-card')

    for route in ('watch.php', 'topics.php'):
        r = await page.goto(BASE + '/' + route, wait_until='networkidle'); assert r and r.ok
        out[route] = await no_overflow(page, f'{width}-{suffix}-{route}')
    return out

async def check_admin(page, width):
    out = {}
    r = await page.goto(BASE + '/start.php', wait_until='networkidle'); assert r and r.ok
    start = await grid_info(page, '.surface-start .vf-asset-row', f'{width}-admin-start', 105 if width <= 430 else 250)
    assert start['hasSelect'] is True, start
    assert len(start['grid'].split()) == 4, start
    out['start'] = start

    r = await page.goto(BASE + '/channels.php', wait_until='networkidle'); assert r and r.ok
    channels = await grid_info(page, '.surface-channels .vf-asset-row', f'{width}-admin-channels', 90 if width <= 430 else 150)
    assert channels['hasSelect'] is True, channels
    assert len(channels['grid'].split()) == 4, channels
    out['channels'] = channels
    await page.screenshot(path=str(EVID / 'screens' / f'{width}-admin-channels.png'), full_page=False)
    return out

async def run_width(browser, width):
    context = await browser.new_context(viewport={'width': width, 'height': 900})
    page = await context.new_page()
    row = {}
    row['anonymous_before'] = await check_anonymous(page, width, 'anonymous-before')

    await page.goto(BASE + '/start.php', wait_until='networkidle')
    login = page.locator('.vf-global-domain-nav [data-vf-auth-login]')
    assert await login.is_visible()
    await login.click()
    await page.locator('[data-vf-auth-dialog] input[name="password"]').fill(PASSWORD)
    async with page.expect_navigation(wait_until='networkidle'):
        await page.locator('[data-vf-auth-submit]').click()
    row['admin'] = await check_admin(page, width)

    await page.goto(BASE + '/start.php', wait_until='networkidle')
    logout = page.locator('.vf-global-domain-nav [data-vf-auth-logout]')
    assert await logout.is_visible()
    async with page.expect_navigation(wait_until='networkidle'):
        await logout.click()
    row['anonymous_after'] = await check_anonymous(page, width, 'anonymous-after')
    await context.close()
    return row

async def main():
    EVID.mkdir(parents=True, exist_ok=True)
    (EVID / 'screens').mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        exe = shutil.which('google-chrome') or shutil.which('google-chrome-stable') or shutil.which('chromium') or shutil.which('chromium-browser')
        kwargs = {'headless': True, 'args': ['--no-sandbox']}
        if exe:
            kwargs['executable_path'] = exe
        browser = await p.chromium.launch(**kwargs)
        try:
            for width in (390, 1319, 1440):
                RESULT[str(width)] = await run_width(browser, width)
        finally:
            await browser.close()
    RESULT['verdict'] = 'PASS'
    (EVID / 'browser.json').write_text(json.dumps(RESULT, ensure_ascii=False, indent=2), encoding='utf-8')
    print('P01_ANONYMOUS_GRID_BROWSER=PASS')

asyncio.run(main())
