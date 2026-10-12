"""Isolated real Chromium security regression: no network, no installed VF Start, synthetic token only."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

PRODUCT_JS = Path("product/src/assets/browser-helper.js").read_text(encoding="utf-8")
HTML = """<!doctype html><html><head><meta charset="utf-8"></head><body>
<button id="generateHelperToken">生成新令牌</button>
<dialog id="helperTokenDialog">
  <button type="button" data-close-token>关闭</button>
  <input id="helperSiteUrlModal" value="https://synthetic.invalid">
  <input id="newHelperToken" value="">
  <button data-copy-token type="button">复制连接信息</button>
  <span id="helperTokenCopyState">尚未复制</span>
  <div class="vf-helper-token-card"></div>
  <button data-close-token data-token-done type="button" disabled>复制后可关闭</button>
</dialog></body></html>"""

async def fresh(browser, allow_close=True):
    context = await browser.new_context()
    page = await context.new_page()
    await page.set_content(HTML)
    await page.evaluate("""(allowClose) => {
      window.__syntheticCopies = [];
      window.confirm = () => allowClose;
      Object.defineProperty(navigator, 'clipboard', {configurable:true,value:{
        writeText: async value => {window.__syntheticCopies.push(value);}
      }});
    }""", allow_close)
    await page.add_script_tag(content=PRODUCT_JS)
    await page.evaluate("""() => {
      document.getElementById('newHelperToken').value = 'SYNTHETIC-ONLY-NOT-A-REAL-SECRET';
      document.getElementById('helperTokenDialog').showModal();
    }""")
    return context, page

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--no-sandbox"])
        context, page = await fresh(browser)
        await page.locator("[data-copy-token]").click()
        assert len(await page.evaluate("window.__syntheticCopies")) == 1
        assert not await page.locator("[data-token-done]").is_disabled()
        await page.keyboard.press("Escape")
        assert not await page.locator("#helperTokenDialog").evaluate("(d) => d.open")
        assert await page.locator("#newHelperToken").input_value() == ""
        assert await page.locator("[data-token-done]").is_disabled()
        print("P01_247357_CHROMIUM_ESCAPE_AFTER_COPY_WIPES=PASS")
        await context.close()

        context, page = await fresh(browser, False)
        await page.keyboard.press("Escape")
        assert await page.locator("#helperTokenDialog").evaluate("(d) => d.open")
        assert await page.locator("#newHelperToken").input_value() == "SYNTHETIC-ONLY-NOT-A-REAL-SECRET"
        print("P01_247357_CHROMIUM_UNCOPIED_CANCEL_PRESERVES=PASS")
        await context.close()

        context, page = await fresh(browser, True)
        await page.keyboard.press("Escape")
        assert not await page.locator("#helperTokenDialog").evaluate("(d) => d.open")
        assert await page.locator("#newHelperToken").input_value() == ""
        print("P01_247357_CHROMIUM_UNCOPIED_CONFIRM_WIPES=PASS")
        await context.close()

        context, page = await fresh(browser)
        await page.evaluate("document.getElementById('helperTokenDialog').close()")
        await page.wait_for_function("document.getElementById('newHelperToken').value === ''")
        assert await page.locator("[data-token-done]").is_disabled()
        print("P01_247357_CHROMIUM_NATIVE_CLOSE_WIPES=PASS")
        await context.close()

        context, page = await fresh(browser)
        await page.locator("[data-copy-token]").click()
        await page.locator("[data-token-done]").click()
        assert not await page.locator("#helperTokenDialog").evaluate("(d) => d.open")
        assert await page.locator("#newHelperToken").input_value() == ""
        print("P01_247357_CHROMIUM_DONE_BUTTON_WIPES=PASS")
        await context.close()
        await browser.close()
    print("P01_247357_REAL_CHROMIUM_NO_DEPLOYMENT=PASS")

if __name__ == "__main__":
    asyncio.run(main())
