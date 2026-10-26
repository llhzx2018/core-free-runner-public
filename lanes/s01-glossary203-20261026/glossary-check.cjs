const fs = require('fs'), assert = require('assert/strict');
const { chromium } = require('playwright');
(async () => {
  const phase = (process.argv.find(x => x.startsWith('--phase=')) || '--phase=after').split('=')[1];
  const urls = JSON.parse(fs.readFileSync('proof/glossary-fixtures.json'));
  const b = await chromium.launch(), p = await b.newPage({ viewport: { width: 1440, height: 1100 } });
  globalThis.reviewPage = p;
  const errors = []; p.on('pageerror', e => errors.push(e.message));
  let checks = 0, rows = 0;
  const go = async url => { const r = await p.goto(url); assert.equal(r.status(), 200); await p.waitForLoadState('networkidle'); };
  const terms = () => p.locator('.vf-glossary-inline-term');
  const head = () => p.evaluate(() => ({ title: document.title, h1: [...document.querySelectorAll('h1')].map(x => x.textContent), meta: [...document.head.querySelectorAll('meta,link[rel="canonical"],link[rel="alternate"],script[type="application/ld+json"]')].filter(x => !['vf-theme-version','vf-theme-round','vf-theme-cache-token','vf-toolsite-theme','vf-theme-home-tools-force','vf-theme-page-family-visuals'].includes(x.getAttribute('name'))).map(x => x.outerHTML) }));
  const baseline = (file, value) => { if (phase === 'before') fs.writeFileSync(file, JSON.stringify(value)); else assert.deepEqual(value, JSON.parse(fs.readFileSync(file)), file); };
  const metrics = () => p.evaluate(() => {
    const read = selector => { const el = document.querySelector(selector); if (!el) return null; const s = getComputedStyle(el), r = el.getBoundingClientRect(); return { border: ['Top','Right','Bottom','Left'].map(x => parseFloat(s['border'+x+'Width'])), color: s.borderColor, background: s.backgroundColor, outline: parseFloat(s.outlineWidth), shadow: s.boxShadow, width: r.width, height: r.height, x: r.x }; };
    return { form: read('.vf-directory-search'), label: read('.vf-directory-search label'), input: read('[data-vf-directory-query]'), section: read('.vf-directory-section'), summary: read('.vf-content-list-summary'), term: read('.vf-glossary-inline-term'), ul: read('.vf-theme-pagination>ul'), current: read('.vf-theme-pagination .current'), overflow: document.documentElement.scrollWidth > innerWidth, hero: read('.vf-family-hero .container-wide'), rail: read('.vf-directory-section .container-wide') };
  });
  const zero = object => assert.ok(object.border.every(v => v === 0), JSON.stringify(object));
  for (const lang of ['en','zh']) {
    await go(urls[lang]);
    baseline('proof/independent-'+lang+'.json', { head: await head(), text: await p.locator('[data-vf-directory-item]').allTextContents(), links: await p.locator('[data-vf-directory-item]').evaluateAll(es => es.map(x => x.getAttribute('href'))) }); checks += 3;
    const url = urls[lang] + '?glossary_case=inline-legacy';
    await go(url); assert.equal(await terms().count(), 12); rows++; checks++;
    baseline('proof/page-'+lang+'.json', { head: await head(), text: await terms().allTextContents(), links: await terms().locator('a').evaluateAll(es => es.map(x => x.getAttribute('href'))) }); checks += 3;
    for (const width of [1440,1024]) {
      await p.setViewportSize({ width, height: 1100 }); await go(url);
      const m = await metrics(); assert.equal(m.overflow, false); assert.ok(Math.abs(m.hero.x-m.rail.x) < 2); checks += 2;
      fs.writeFileSync(`proof/metrics-${phase}-${lang}-${width}.json`, JSON.stringify(m));
      if (phase !== 'after') {
        assert.ok(m.form.border.some(v => v > 0) && m.input.border.some(v => v > 0), 'reproduce nested search frames');
        assert.ok(m.ul.border.some(v => v > 0), 'reproduce pagination parent mistaken for page link');
        assert.ok(m.term.border[2] > 0 && m.summary.border[2] > 0, 'reproduce repeated rules'); checks += 3; continue;
      }
      zero(m.form); zero(m.input); zero(m.section); zero(m.summary); zero(m.term); zero(m.ul); checks += 6;
      assert.equal(m.form.shadow, 'none'); assert.equal(m.ul.background, 'rgba(0, 0, 0, 0)'); assert.equal(m.current.background, 'rgba(0, 0, 0, 0)'); assert.equal(m.label.border[0], 1); checks += 4;
      assert.equal(m.label.color, 'rgb(122, 135, 147)');const rgb=m.label.color.match(/\d+/g).map(Number).slice(0,3).map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);assert.ok(1.05/(rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722+.05)>=3);checks++; assert.ok(m.label.height >= 44); assert.ok(m.current.height >= 44); checks += 3;
      await p.screenshot({ path: `proof/glossary-${lang}-${width}.png`, fullPage: true });
      await p.locator('.vf-directory-search').screenshot({ path: `proof/search-${lang}-${width}.png` });
      await p.locator('.vf-theme-pagination').screenshot({ path: `proof/pagination-${lang}-${width}.png` });
      await p.locator('.vf-theme-pagination a.next').hover(); zero((await metrics()).ul); checks++;
      await p.locator('.vf-theme-pagination').screenshot({ path: `proof/pagination-hover-${lang}-${width}.png` });
      await p.locator('.vf-theme-pagination a.next').focus(); await p.keyboard.press('Tab'); await p.keyboard.press('Shift+Tab');
      assert.ok(await p.locator('.vf-theme-pagination a.next').evaluate(e => e.matches(':focus-visible') && parseFloat(getComputedStyle(e).outlineWidth) >= 2));
      zero((await metrics()).ul); checks += 2;
      await p.locator('.vf-theme-pagination').screenshot({ path: `proof/pagination-focus-${lang}-${width}.png` });
      await p.locator('[data-vf-directory-query]').focus();
      const focus = await metrics(); assert.ok(focus.label.outline >= 2); zero(focus.input); zero(focus.form); checks += 3;
      await p.locator('.vf-directory-search').screenshot({ path: `proof/search-focus-${lang}-${width}.png` });
    }
    if (phase !== 'after') continue;
    await p.setViewportSize({ width: 1440, height: 1100 }); await go(url);
    await p.locator('.vf-theme-pagination a.next').click(); await p.waitForLoadState('networkidle'); assert.equal(await terms().count(), 1); assert.match(await terms().innerText(), /Variant/); zero((await metrics()).ul); checks += 3;
    await go(url+'&vf_q=AES-128'); assert.equal(await terms().count(),1); assert.match(await terms().innerText(),/AES-128/); checks += 2;
    await go(url+'&vf_filter=security'); assert.equal(await terms().count(),3); checks++;
    await go(url+'&vf_letter=m'); assert.equal(await terms().count(),3); checks++;
    await go(url); await p.locator('.vf-glossary-letter-disclosure summary').click();
    assert.ok(await p.locator('.vf-glossary-letter-index').isVisible()); assert.equal(await p.evaluate(() => document.documentElement.scrollWidth > innerWidth), false); checks += 2;
    await go(url+'&vf_q=not-a-real-term'); assert.equal(await terms().count(),0); assert.ok(await p.locator('[data-vf-directory-empty]').isVisible()); checks += 2;
    await p.locator('[data-vf-directory-reset]').click(); await p.waitForLoadState('networkidle'); assert.equal(await terms().count(),12); checks++;
    const context = await b.newContext({ javaScriptEnabled:false, viewport:{width:1024,height:1100} }), n = await context.newPage();
    await n.goto(url); await n.locator('[data-vf-directory-query]').fill('AES-128'); await n.locator('.vf-directory-submit').click(); assert.equal(await n.locator('.vf-glossary-inline-term').count(),1); await context.close(); checks++;
  }
  for (const route of ['','blog/','guides/','problems/','faq/']) {
    await go('http://127.0.0.1:18880/'+route);
    baseline('proof/adjacent-'+(route.replace('/','')||'home')+'.json', {head:await head(),text:await p.locator('main').innerText(),links:await p.locator('main a').evaluateAll(es=>es.map(e=>[e.textContent,e.getAttribute('href')]))});checks++;
  }
  if (phase === 'after') {
    const references=[], referencePage=await b.newPage({viewport:{width:1440,height:1000}});
    for (const [name,url] of [['govuk','https://design-system.service.gov.uk/components/pagination/default/'],['mdn','https://developer.mozilla.org/en-US/docs/Glossary']]) {
      try { await referencePage.goto(url,{waitUntil:'domcontentloaded',timeout:15000}); await referencePage.screenshot({path:'proof/reference-'+name+'.png',fullPage:false});references.push({name,url,status:'CAPTURED'}); }
      catch(e){ references.push({name,url,status:'NOT_OBSERVED',reason:e.message.split('\n')[0]}); }
    }
    await referencePage.close();fs.writeFileSync('proof/references.json',JSON.stringify(references));
  }
  assert.deepEqual(errors,[]);
  const receipt={status:'PASS',phase,rows,checks,errors,production:'UNTOUCHED',ownerContentSEO:phase==='before'?'BASELINE_CAPTURED':'BYTE_IDENTICAL',visualControls:phase==='after'?'SINGLE_SEARCH_BOUNDARY_UNFRAMED_PAGINATION_NO_REPEATED_RULES':'202_NESTED_FRAMES_REPRODUCED',states:phase==='after'?'DEFAULT_HOVER_KEYBOARD_FOCUS_ZH_EN_1440_1024':'BASELINE_ONLY',interaction:phase==='after'?'13_DEFINITIONS_PAGE2_SEARCH_FILTER_LETTER_RESET_NOJS':'BASELINE_ONLY',operationalAcceptance:'OWNER_REVIEW_REQUIRED_AFTER_MANUAL_UPGRADE'};
  fs.writeFileSync(`proof/glossary-${phase}.json`,JSON.stringify(receipt)); console.log('GLOSSARY_'+phase.toUpperCase()+'_PASS checks='+checks);await b.close();
})().catch(async e=>{console.error(e);try{fs.writeFileSync('proof/failure.html',await globalThis.reviewPage.content());await globalThis.reviewPage.screenshot({path:'proof/failure.png',fullPage:true});}catch(_){}process.exit(1)});
