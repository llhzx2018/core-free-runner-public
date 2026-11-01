import {chromium} from 'playwright';
const origin=process.env.P01_TEST_ORIGIN, password=process.env.P01_TEST_PASSWORD;
if(!/^http:\/\/127\.0\.0\.1:\d+$/.test(origin||'')||!password||
 !/^\/tmp\/p01-ia6-487-parity$/.test(process.env.VF_E2E_RUNTIME_ROOT||'')||
 process.env.VF_IA6_DISPOSABLE_ACK!=='IA6-487-DOMAIN-BATCH-ONLY')
 throw Error('REFUSED_NONDISPOSABLE_P01_E2E');
const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
const ok=(condition,why)=>{if(!condition)throw Error(why);};
let categoryWrites=[],settingsWrites=0;
try {
 const context=await browser.newContext({viewport:{width:1440,height:900}});
 await context.route(/https?:\/\/(?!127\.0\.0\.1)/,r=>r.abort());
 const login=await context.request.post(origin+'/api.php?action=login',{data:{password}});
 ok(login.status()===200&&(await login.text()).includes('"ok":true'),'owner_login');
 const page=await context.newPage();
 page.on('request',req=>{
  if(req.method()!=='POST')return;
  const u=new URL(req.url());
  if(['category_save','category_delete','category_reorder'].includes(u.searchParams.get('action')))categoryWrites.push(u.searchParams.get('action'));
  if(/settings|configuration/.test(u.searchParams.get('action')||''))settingsWrites++;
 });
 // Real canonical category create -> SQLite -> independent bootstrap readback -> same-page navigation re-render.
 await page.goto(origin+'/start.php',{waitUntil:'domcontentloaded'});
 const before=page.url();
 await page.locator('[data-vf-local-manage-open]').click();
 const modal=page.locator('#vf-local-management');
 await modal.locator('[data-vf-local-task="category"]').click();
 const local=modal.locator('[data-vf-local-category-area]');
 await local.locator('[data-vf-local-category-create]').click();
 const editor=local.locator('[data-vf-category-native-form]');
 await editor.waitFor({state:'visible'});
 const name='P01 487 仅临时测试分类';
 await editor.locator('input[name="name"]').fill(name);
 await editor.locator('textarea[name="description"]').fill('Synthetic disposable Owner category');
 await editor.locator('[data-vf-category-native-save]').click();
 await local.locator('[data-vf-category-native-status]').filter({hasText:'分类已保存'}).waitFor({timeout:12000});
 ok(categoryWrites.filter(x=>x==='category_save').length===1,'category_one_canonical_save');
 const backend=await page.evaluate(async()=>{const r=await fetch('api.php?action=bootstrap',{credentials:'same-origin'});return r.json()});
 ok(backend.ok===true,'category_bootstrap_readback');
 const created=(backend.data?.categories||[]).find(x=>x.name===name&&String(x.lifecycle_state||'active')==='active');
 ok(created&&Number(created.id)>0,'category_sqlite_write_readback');
 ok((await page.locator('[data-start-category-section] .vf-category-tree').innerText()).includes(name),
   'category_sidebar_updates_without_navigation');
 ok(page.url()===before,'category_same_document_url');

 const select=local.locator('[data-vf-local-category-select]');
 await select.selectOption(String(created.id));
 await local.locator('[data-vf-local-category-edit]').click();
 await editor.waitFor({state:'visible'});
 await editor.locator('[data-vf-category-native-delete]').click();
 await editor.locator('[data-vf-category-native-delete-phrase]').fill('删除分类');
 await editor.locator('[data-vf-category-native-delete-commit]').click();
 await local.locator('[data-vf-category-native-status]').filter({hasText:'移入回收站'}).waitFor({timeout:12000});
 ok(categoryWrites.filter(x=>x==='category_delete').length===1,'category_one_canonical_delete');
 const after=await page.evaluate(async()=>{const r=await fetch('api.php?action=bootstrap',{credentials:'same-origin'});return r.json()});
 ok(!(after.data?.categories||[]).some(x=>Number(x.id)===Number(created.id)&&String(x.lifecycle_state||'active')==='active'),'category_deleted_independently');
 ok(page.url()===before,'category_delete_no_navigation');
 console.log('P01_IA6_CATEGORY_REAL_SQLITE_SAVE_READBACK_DELETE=PASS');
 console.log('P01_IA6_CATEGORY_SAME_PAGE_TREE_AND_URL=PASS');

 // Watch must own the one and only TMDB credential editor, not Global settings.
 await page.goto(origin+'/watch.php',{waitUntil:'domcontentloaded'});
 await page.locator('[data-vf-local-manage-open]').click();
 const dialog=page.locator('#vf-local-management');
 await dialog.locator('[data-vf-local-task="watch-metadata"]').click();
 const watch=dialog.locator('[data-vf-local-watch-metadata-area]');
 ok(await watch.isVisible(),'watch_metadata_current_dialog');
 const tmdb=watch.locator('[data-vf-tmdb-root]');
 ok(await tmdb.count()===1,'watch_one_native_token_editor');
 ok(await dialog.locator('[data-vf-tmdb-root]').count()===1,'no_second_token_authority');
 const help=tmdb.locator('a[href="https://www.themoviedb.org/settings/api"]');
 ok(await help.count()===1,'original_tmdb_help_link');
 ok(await help.getAttribute('rel')==='noopener noreferrer','tmdb_external_help_safe');
 await tmdb.locator('summary').click();
 await tmdb.locator('[data-vf-tmdb-load]').click();
 await tmdb.locator('[data-vf-tmdb-status]').filter({hasText:/已|连接|未|授权/}).waitFor({timeout:12000});
 ok(await dialog.locator('[data-vf-tmdb-root]').count()===1,'token_editor_singleton_after_status');
 console.log('P01_IA6_WATCH_TMDB_NATIVE_OWNER_LOCATION=PASS');

 // Global display defaults only fill a draft. Never POST until separate save confirmation.
 await dialog.locator('[data-vf-management-tab="global"]').click();
 await dialog.locator('[data-vf-global-group="settings"]').click();
 const settings=dialog.locator('[data-vf-global-settings-root]');
 await settings.locator('[data-vf-global-settings-load]').click();
 const form=settings.locator('[data-vf-global-settings-editor]');
 await form.waitFor({state:'visible',timeout:12000});
 const view=form.locator('[name="defaultView"]');
 await view.selectOption('grid');
 const oldWrites=settingsWrites;
 await settings.locator('[data-vf-global-settings-display-defaults]').click();
 const defaults=await form.evaluate(el=>{
   const f=el.elements;
   return {v:f.namedItem('defaultView')?.value,d:f.namedItem('defaultDensity')?.value,
     size:f.namedItem('pageSize')?.value,
     desc:f.namedItem('showDescriptions')?.checked,domain:f.namedItem('showDomains')?.checked};
 });
 ok(defaults.v==='list'&&defaults.d==='comfortable'&&defaults.size==='20'&&defaults.desc===true&&defaults.domain===true,
   'five_legacy_display_defaults');
 ok(settingsWrites===oldWrites,'defaults_only_staged_not_saved');
 await settings.locator('[data-vf-global-settings-revert]').click();
 ok(settingsWrites===oldWrites,'revert_zero_write');
 console.log('P01_IA6_GLOBAL_DISPLAY_DEFAULTS_DRAFT_ONLY=PASS');
 console.log('P01_IA6_DOMAIN_OWNER_BROWSER_BATCH=PASS');
 await context.close();
} finally { await browser.close(); }
