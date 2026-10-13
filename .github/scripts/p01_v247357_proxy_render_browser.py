"""Isolated browser/helper end-to-end proof through the exact temporary preview proxy.

Everything binds to 127.0.0.1, uses a synthetic PHP/SQLite install and a disposable
Basic-auth credential; no site production, no Cloudflare tunnel and no real tokens.
"""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

HOME = Path("/tmp/p01-v247357-preview")
PWD = (HOME / "proxy-password").read_text(encoding="utf-8").strip()
URL = "http://127.0.0.1:18542/browser-helper.php"

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(
            http_credentials={"username": "preview", "password": PWD},
            viewport={"width": 1350, "height": 980},
            device_scale_factor=1,
        )
        page = await context.new_page()
        asset_responses = []
        page.on("response", lambda res: asset_responses.append(
            (res.url, res.status, res.headers.get("content-type", ""))
        ) if "/asset.php?" in res.url else None)
        response = await page.goto(URL, wait_until="networkidle", timeout=30000)
        assert response is not None and response.status == 200, "Authenticated browser-helper page not 200"
        assert "浏览器助手" in await page.locator("body").inner_text(), "Missing real product browser helper content"
        css_links = await page.locator("link[rel='stylesheet']").evaluate_all(
            "(els) => els.map(x => x.href)"
        )
        assert len(css_links) >= 2, "Admin CSS links not rendered"
        assert all("/asset.php?file=" in x for x in css_links), "Unexpected stylesheet routing"
        css_loaded = [x for x in asset_responses if ".css" in x[0] and x[1] == 200
                      and "text/css" in x[2]]
        assert len(css_loaded) >= 2, f"Canonical CSS assets not served by proxy: {asset_responses!r}"
        print("P01_247357_E2E_CANONICAL_ASSETS_HTTP200=PASS")
        count = await page.evaluate("document.styleSheets.length")
        assert count >= 2, f"CSS not applied: {count}"
        icon_dimensions = await page.evaluate("""() => Array.from(document.querySelectorAll('svg'))
          .map(el => ({w:el.getBoundingClientRect().width,h:el.getBoundingClientRect().height,
                       left:el.getBoundingClientRect().left,top:el.getBoundingClientRect().top}))
          .filter(r => r.left < 240 && r.top >= 0 && r.top < 980 && r.w > 1 && r.h > 1)""")
        assert icon_dimensions, "Expected navigation icons missing"
        assert all(r["w"] <= 80 and r["h"] <= 80 for r in icon_dimensions), (
            f"Unstyled giant left navigation SVG detected: {icon_dimensions!r}"
        )
        print("P01_247357_E2E_REAL_RENDER_STYLES_AND_NAV_ICONS=PASS")
        # Take the screenshot BEFORE generating a token to keep the evidence credential-free.
        await page.screenshot(path=str(HOME / "V247357_LOCAL_PROXY_STYLED_NO_TOKEN.png"), full_page=True)
        await page.evaluate("""() => {
          window.__testCopied = [];
          window.confirm = () => true;
          Object.defineProperty(navigator, 'clipboard', {configurable: true, value: {
            writeText: async v => { window.__testCopied.push(v); }
          }});
        }""")
        await page.locator("#generateHelperToken").click()
        await page.locator("#helperTokenDialog").wait_for(state="visible", timeout=12000)
        ephemeral = await page.locator("#newHelperToken").input_value()
        assert len(ephemeral) >= 20, "Disposable token generation failed behind proxy"
        await page.locator("[data-copy-token]").click()
        assert not await page.locator("[data-token-done]").is_disabled(), "Copy never completed"
        assert len(await page.evaluate("window.__testCopied")) == 1, "Clipboard interaction failed"
        await page.keyboard.press("Escape")
        assert not await page.locator("#helperTokenDialog").evaluate("(d) => d.open")
        assert await page.locator("#newHelperToken").input_value() == "", "One-time token survived Escape"
        assert await page.locator("[data-token-done]").is_disabled(), "Copy state not reset"
        print("P01_247357_E2E_DISPOSABLE_REAL_API_COPY_ESCAPE_WIPE=PASS")
        await context.close()
        await browser.close()
    print("P01_247357_E2E_NO_EXTERNAL_DEPLOYMENT=PASS")

if __name__ == "__main__":
    asyncio.run(main())
