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

async def asset_rows(page, title):
    return await page.locator('article[data-asset-row]').filter(has_text=title).count()

async def assert_shell(page, items, label):
    nav = page.locator('.vf-global-domain-nav')
    await nav.wait_for(state='visible')
    text = ' '.join((await nav.inner_text()).split())
    for item in items:
        assert item in text, (label, item, text)
    assert await page.locator('body.vf-functional-workspace').count() == 1
    assert await page.locator('#app.app-shell').count() == 0
    dims = await page.evaluate('() => ({sw:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth})')
    assert dims['sw'] <= dims['cw'] + 1, (label, dims)
    return {'nav': text, 'overflow': dims}

async def run_width(browser, width):
    context = await browser.new_context(viewport={'width': width, 'height': 900})
    page = await context.new_page()
    row = {}

    response = await page.goto(BASE + '/', wait_until='networkidle')
    assert response and response.ok
    headers = {k.lower(): v for k, v in (await response.all_headers()).items()}
    assert 'content-security-policy' in headers
    assert await page.locator('link[rel="canonical"]').count() == 1
    assert await page.locator('meta[name="description"]').count() == 1
    row['anonymous'] = await assert_shell(page, ['导航', '频道', '影视', '专题', '登录'], 'anonymous')
    assert await asset_rows(page, '严格私人导航') == 0
    await page.screenshot(path=str(EVID / 'screens' / f'{width}-anonymous.png'))

    login = page.locator('.vf-global-domain-nav [data-vf-auth-login]')
    assert await login.is_visible()
    await login.click()
    await page.locator('[data-vf-auth-dialog] input[name="password"]').fill(PASSWORD)
    async with page.expect_navigation(wait_until='networkidle'):
        await page.locator('[data-vf-auth-submit]').click()
    row['authenticated'] = await assert_shell(page, ['首页', '导航', '频道', '影视', '专题', '退出'], 'authenticated')
    await page.goto(BASE + '/?q=严格私人导航', wait_until='networkidle')
    assert await asset_rows(page, '严格私人导航') == 1

    for route, active in [('home.php','首页'),('start.php','导航'),('channels.php','频道'),('watch.php','影视'),('topics.php','专题')]:
        r = await page.goto(BASE + '/' + route, wait_until='networkidle')
        assert r and r.ok
        h = {k.lower(): v for k, v in (await r.all_headers()).items()}
        assert 'content-security-policy' in h
        await assert_shell(page, ['首页', '导航', '频道', '影视', '专题', '退出'], route)
        active_text = ' '.join(await page.locator('.vf-global-domain-nav a.active').all_inner_texts())
        assert active in active_text, (route, active_text)

    await page.goto(BASE + '/start.php', wait_until='networkidle')
    toolbar = page.locator('.vf-workspace-toolbar')
    await toolbar.wait_for(state='visible')
    bg = await toolbar.evaluate('el => getComputedStyle(el).backgroundColor')
    assert bg not in ('transparent', 'rgba(0, 0, 0, 0)'), bg
    await page.evaluate('window.scrollTo(0,600)')
    await page.wait_for_timeout(150)
    scroll_y = await page.evaluate('window.scrollY')
    assert scroll_y > 0, scroll_y
    box = await toolbar.bounding_box()
    assert box and box['y'] >= 0, box
    row['sticky'] = {'background': bg, 'box': box, 'scrollY': scroll_y}
    await page.screenshot(path=str(EVID / 'screens' / f'{width}-authenticated-sticky.png'))

    await page.goto(BASE + '/', wait_until='networkidle')
    logout = page.locator('.vf-global-domain-nav [data-vf-auth-logout]')
    assert await logout.is_visible()
    async with page.expect_navigation(wait_until='networkidle'):
        await logout.click()
    row['logout'] = await assert_shell(page, ['导航', '频道', '影视', '专题', '登录'], 'logout')
    await page.goto(BASE + '/?q=严格私人导航', wait_until='networkidle')
    assert await asset_rows(page, '严格私人导航') == 0
    channels = await page.goto(BASE + '/channels.php', wait_until='networkidle')
    assert channels and channels.ok
    robots = (await page.locator('meta[name="robots"]').get_attribute('content') or '').lower()
    assert 'noindex' in robots
    assert await asset_rows(page, '严格私人频道') == 0
    await page.screenshot(path=str(EVID / 'screens' / f'{width}-logout.png'))
    await context.close()
    return row

async def main():
    async with async_playwright() as p:
        exe = shutil.which('google-chrome') or shutil.which('google-chrome-stable') or shutil.which('chromium') or shutil.which('chromium-browser')
        kwargs = {'headless': True, 'args': ['--no-sandbox']}
        if exe:
            kwargs['executable_path'] = exe
        browser = await p.chromium.launch(**kwargs)
        try:
            for width in (390, 1440):
                RESULT[str(width)] = await run_width(browser, width)
        finally:
            await browser.close()
    RESULT['verdict'] = 'PASS'
    (EVID / 'browser-r2.json').write_text(json.dumps(RESULT, ensure_ascii=False, indent=2), encoding='utf-8')
    print('P01_V2363_STRICT_BROWSER_R2=PASS')

asyncio.run(main())
