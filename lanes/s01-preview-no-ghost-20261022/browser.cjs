'use strict';
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
const browser=await chromium.launch();
try{
const page=await browser.newPage();
const html='<section data-vf-preview-page data-revision="none" data-state="idle">'
+'<select data-vf-preview-target>'
+'<option value="post:42" selected data-label="English-only article" data-family="article" data-path="/english-only/" data-paths=\'{"en":"/english-only/"}\' data-signed-paths=\'{"en":"/english-only/?signed=1"}\'>EN-only</option>'
+'<option value="page_type:missing" data-label="Not published" data-family="guide" data-path="" data-paths="{}" data-signed-paths="{}">Missing</option>'
+'<option value="route:tools" data-label="Tools" data-family="tool" data-path="/tools/" data-paths=\'{"en":"/tools/","zh":"/zh/tools/"}\' data-signed-paths=\'{"en":"/tools/","zh":"/zh/tools/"}\'>Tools</option>'
+'</select>'
+'<select data-vf-preview-language><option value="en" selected>English</option><option value="zh">中文</option></select>'
+'<div data-vf-preview-target-current-label></div><div data-vf-preview-target-current-family></div>'
+'<div data-vf-preview-target-current-path></div><a data-vf-preview-open-page target="_blank">Open</a>'
+'<button type="button" data-vf-preview-load hidden>Load</button>'
+'<div data-vf-preview-canvas hidden></div></section>';
await page.setContent(html,{url:'https://test.example/preview/'});
await page.evaluate(()=>{window.VFThemePreview={};window.__writes=[];window.fetch=()=>{window.__writes.push('fetch');throw Error('unexpected write')}});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.addScriptTag({path:'theme/src/assets/js/admin/admin-preview.js'});
await page.waitForFunction(()=>document.querySelector('[data-vf-preview-page]')?.dataset.scriptReady==='1');
const select=page.locator('[data-vf-preview-target]'),language=page.locator('[data-vf-preview-language]'),open=page.locator('[data-vf-preview-open-page]'),load=page.locator('[data-vf-preview-load]');
assert((await open.getAttribute('href')).includes('/english-only/'));
assert.equal(await load.isDisabled(),false);
await language.selectOption('zh');
assert.equal(await open.getAttribute('href'),null);
assert.equal(await open.getAttribute('aria-disabled'),'true');
assert.equal(await load.isDisabled(),true);
assert((await page.locator('[data-vf-preview-target-current-path]').textContent()).includes('尚无真实前台地址'));
console.log('PASS_PREVIEW_UNTRANSLATED_ARTICLE_NO_WRONG_LANGUAGE_LINK');
await select.selectOption('page_type:missing');
assert.equal(await open.getAttribute('href'),null);
assert.equal(await load.isDisabled(),true);
console.log('PASS_PREVIEW_UNPUBLISHED_TARGET_NO_HOME_FALLBACK');
await select.selectOption('route:tools');
assert.equal(await open.getAttribute('href'),'/zh/tools/');
assert.equal(await load.isDisabled(),false);
console.log('PASS_PREVIEW_PUBLISHED_ROUTE_OWN_LANGUAGE_OK');
await language.selectOption('en');
assert.equal(await open.getAttribute('href'),'/tools/');
assert.deepEqual(await page.evaluate(()=>window.__writes),[]);
assert.deepEqual(errors,[]);
console.log('PASS_PREVIEW_NORMAL_EN_ROUTE_NO_SAVE_OR_SCRIPT_ERROR');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
