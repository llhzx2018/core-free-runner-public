const fs = require('node:fs');
const assert = require('node:assert/strict');
const {chromium} = require('playwright');
const classes = 'vf-front-contract-body vf-theme-preset-m3u8_green vf-layout-ruler-strict vf-frontend-params-enforced vf-layout-ruler-enforced vf-frontend-layout-strict';
const title = '在浏览器中播放、检查和整理 M3U8 流';
const html = (family, lang) => `<!doctype html><html lang="${lang}"><head><meta charset="utf-8"><style>body{margin:0}#content{width:min(calc(100% - 64px),1200px);margin:0 auto}</style></head><body class="${classes} vf-page-family-context--${family}"><main id="content">${family === 'home' ? `<section class="vf-family-hero vf-data-hero vf-home-hero is-home"><div class="container-wide"><div class="vf-home-hero-layout"><div class="vf-home-hero-copy"><span class="vf-family-eyebrow">浏览器本地 M3U8 / HLS 工具</span><h1>${lang === 'zh-CN' ? title : 'Play, inspect and organize M3U8 streams in your browser'}</h1><p>从播放器开始，定位播放失败原因，检查播放列表结构。</p></div></div></div></section>` : `<section class="vf-directory-section--tools"><div class="container-wide"><div class="vf-directory-shell"><div class="vf-directory-toolbar"><form class="vf-directory-search" method="get" data-vf-directory-server-search><label for="vf-directory-search-tool-hub"><span class="screen-reader-text">搜索工具名称或用途</span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m21 21-4.35-4.35m2.35-5.65a8 8 0 1 1-16 0 8 8 0 0 1 16 0Z"></path></svg><input id="vf-directory-search-tool-hub" name="vf_q" type="search" inputmode="search" autocomplete="off" placeholder="搜索工具名称或用途" aria-label="搜索工具名称或用途" data-vf-directory-query></label><button type="submit" class="screen-reader-text">搜索整个目录</button></form><p class="vf-directory-count"><strong>11</strong> 个工具</p></div></div></div></section>`}</main></body></html>`;
(async () => {
  const browser = await chromium.launch({headless:true});
  const rows = [];
  try {
    for (const phase of ['baseline','candidate']) {
      for (const width of [1024,1280,1440,1920]) {
        for (const family of ['home','tool_hub']) {
          for (const lang of ['zh-CN','en']) {
            const page = await browser.newPage({viewport:{width,height:900}});
            await page.setContent(html(family,lang));
            await page.addStyleTag({path:`${phase === 'baseline' ? 'baseline' : 'target'}/src/assets/css/public/vf-theme-public-runtime.css`});
            const value = await page.evaluate(({family,title}) => {
              const overflow = document.documentElement.scrollWidth > innerWidth + 1;
              if(family === 'home') {
                const h=document.querySelector('h1'), text=h.firstChild, at=h.textContent.indexOf('检查');
                const rect=(i)=>{const r=document.createRange();r.setStart(text,i);r.setEnd(text,i+1);return r.getBoundingClientRect().y};
                return {overflow,title:h.textContent,wordBreak:getComputedStyle(h).wordBreak,phraseSameLine:at<0 ? null : Math.abs(rect(at)-rect(at+1))<1};
              }
              const input=document.querySelector('[data-vf-directory-query]'), label=input.parentElement, svg=label.querySelector('svg'), form=label.parentElement;
              const i=input.getBoundingClientRect(), l=label.getBoundingClientRect(), s=svg.getBoundingClientRect(), f=form.getBoundingClientRect();
              return {overflow,inputWidth:i.width,labelWidth:l.width,formWidth:f.width,inputHeight:i.height,inputRatio:i.width/f.width,centerDelta:Math.abs((i.y+i.height/2)-(s.y+s.height/2)),labelFlex:getComputedStyle(label).flexGrow,name:input.getAttribute('aria-label'),method:form.method};
            }, {family,title});
            if(phase==='candidate') {
              assert.equal(value.overflow,false,JSON.stringify({width,family,lang,value}));
              if(family==='home') {
                if(lang==='zh-CN'){assert.equal(value.title,title);assert.equal(value.phraseSameLine,true);assert.equal(value.wordBreak,'keep-all');}
                else assert.notEqual(value.wordBreak,'keep-all');
              } else {
                assert.ok(value.inputRatio>.80,JSON.stringify({width,lang,value}));
                assert.ok(value.centerDelta<1,JSON.stringify({width,lang,value}));
                assert.ok(value.inputHeight>=44);
                assert.equal(value.method,'get');
                await page.locator('.vf-directory-search>label').click();
                assert.equal(await page.evaluate(()=>document.activeElement.hasAttribute('data-vf-directory-query')),true);
                await page.getByRole('searchbox').fill('Playlist');
                assert.equal(await page.getByRole('searchbox').inputValue(),'Playlist');
                assert.notEqual(await page.locator('.vf-directory-search').evaluate(e=>getComputedStyle(e).boxShadow),'none');
                await page.getByRole('searchbox').press('Tab');
                assert.equal(await page.evaluate(()=>document.activeElement.tagName),'BUTTON');
              }
            }
            rows.push({phase,width,family,lang,...value});
            if(phase==='candidate'&&width===1440&&lang==='zh-CN') await page.screenshot({path:`proof/desktop-${family}.png`,fullPage:true});
            await page.close();
          }
        }
      }
    }
    assert.ok(rows.filter(r=>r.phase==='baseline'&&r.family==='tool_hub').some(r=>r.inputRatio<.5||r.centerDelta>1),'must reproduce baseline label/layout defect');
    const proof={status:'PASS',source_sha:process.env.TARGET_SHA,source_tree:process.env.TARGET_TREE,scope:'Exact shipped CSS bundle applied to public markup-shaped isolated fixture; not full WordPress, mobile, Production or domain-function acceptance',desktop_widths:[1024,1280,1440,1920],rows,mobile:'NOT_RUN_OWNER_DEFERRED',production:'NOT_MODIFIED'};
    fs.writeFileSync('proof/desktop.json',JSON.stringify(proof,null,2));
    console.log('DESKTOP_PROOF',JSON.stringify({status:proof.status,source_sha:proof.source_sha,source_tree:proof.source_tree,rows:rows.length,mobile:proof.mobile}));
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
