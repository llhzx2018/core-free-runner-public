'use strict';
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:900},deviceScaleFactor:1});
    const results = [];
    for (const route of ['/', '/zh/']) {
      await page.goto('http://127.0.0.1:18880' + route, {waitUntil:'domcontentloaded'});
      await page.waitForTimeout(500);
      const check = await page.evaluate(() => {
        const sizes = {};
        for (const [name, selector] of Object.entries({
          section_intro: '.vf-home-section-head p',
          tool_body: '.vf-home-tool-card p',
          faq_body: '.vf-home-boundary-card p',
          steps_body: '.vf-home-steps-list p',
          footer_intro: '.vf-production-footer-brand p',
          footer_link: '.vf-production-footer-col .vf-footer-link',
        })) {
          const el = document.querySelector(selector);
          sizes[name] = el ? Number.parseFloat(getComputedStyle(el).fontSize) : null;
        }
        return {
          sizes,
          title:document.title,
          h1:document.querySelectorAll('main h1,#content h1').length,
          cards:document.querySelectorAll('.vf-home-tool-card').length,
          viewportOverflow:document.documentElement.scrollWidth > innerWidth + 2,
        };
      });
      for (const key of ['section_intro','tool_body','faq_body','steps_body']) {
        if (check.sizes[key] !== 16) throw new Error(route + ' ' + key + ' expected 16px got ' + check.sizes[key]);
      }
      for (const key of ['footer_intro','footer_link']) {
        if (check.sizes[key] !== 15) throw new Error(route + ' ' + key + ' expected 15px got ' + check.sizes[key]);
      }
      if (check.viewportOverflow) throw new Error(route + ' desktop horizontal overflow');
      if (check.cards !== 6) throw new Error(route + ' homepage expected 6 tools got ' + check.cards);
      if (!check.title || !check.h1) throw new Error(route + ' title/h1 missing');
      results.push({route,...check});
    }
    process.stdout.write('R14_DESKTOP_READING_RENDER_PASS='+JSON.stringify(results)+'\n');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
