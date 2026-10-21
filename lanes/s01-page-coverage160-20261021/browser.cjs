const {chromium}=require('playwright');const fs=require('fs');
const baseline=process.argv[2]==='baseline',checks=[];
function check(name,pass,detail){checks.push({name,pass:!!pass,detail});if(!pass)throw Error(name+': '+JSON.stringify(detail));}
(async()=>{const browser=await chromium.launch();try{
 const origin='http://127.0.0.1:18880',target=origin+'/wp-admin/themes.php?page=vf-theme-modules&tab=layout&view=pages';
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(origin+'/wp-login.php');await page.locator('#user_login').fill('admin');await page.locator('#user_pass').fill('Synthetic-Only-Update-54!');await page.locator('input[name=redirect_to]').evaluate((x,v)=>x.value=v,target);await page.locator('#wp-submit').click();await page.waitForURL('**/wp-admin/**');await page.waitForLoadState('networkidle');
 const root=page.locator('[data-vf-frontend-pages]');
 check('canonical overview remains 20 types',await root.locator('[data-vf-page-context]').count()===20);
 check('review subjects remain 20 types plus shared header and footer',await root.locator('.vf-frontend-pages__progress-record').count()===22);
 if(baseline){check('159 reproduces missing coverage explanations',await root.locator('.vf-frontend-pages__coverage').count()===0);console.log('159_BASELINE_PASS');return;}
 check('type count is explicitly distinguished from page count',await root.locator('.vf-frontend-pages__scope').innerText().then(x=>x.includes('20 种页型，不是只有 20 个页面')&&x.includes('中英文')&&x.includes('页眉')&&x.includes('不代表')));
 for(const width of [1920,1440,1319,1024])for(const lang of ['en','zh']){
  await page.setViewportSize({width,height:1000});await page.goto(target+'&vf_pages_language='+lang,{waitUntil:'networkidle'});await page.evaluate(()=>document.fonts.ready);
  const rows=root.locator('[data-vf-page-context]');
  check(`${width}/${lang} all 20 explanations always visible`,await rows.count()===20&&await rows.locator('.vf-frontend-pages__coverage').evaluateAll(xs=>xs.length===20&&xs.every(x=>x.getBoundingClientRect().height>0&&x.innerText.includes('包含页面：')&&x.innerText.includes('同类状态 / 检查范围：'))));
  check(`${width}/${lang} no horizontal overflow`,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  check(`${width}/${lang} disclosures initially closed`,await rows.locator('details[open]').count()===0);
  check(`${width}/${lang} content remains explicitly unloaded`,await root.locator('#vf-frontend-pages-content').textContent().then(x=>x.includes('尚未加载')&&x.includes('不是全站只有 20 个页面')&&x.includes('动态搜索、归档'))&&await root.locator('.vf-frontend-pages__content-list li').count()===0);
  check(`${width}/${lang} existing actions stay readable beside explanations`,await rows.evaluateAll(xs=>xs.every(x=>{const a=x.querySelector('.vf-frontend-pages__actions').getBoundingClientRect(),n=x.querySelector('.vf-frontend-pages__name').getBoundingClientRect();return a.width>150&&n.right<=a.x+1;})));
  const hub=root.locator('[data-vf-page-context=tool_hub] .vf-frontend-pages__actions a[target=_blank]');check(`${width}/${lang} public language link preserved`,(await hub.getAttribute('href')).includes(lang==='zh'?'/zh/tools/':'/tools/'));
  await page.screenshot({path:`proof/overview-${lang}-${width}.png`,fullPage:true});
 }
 const tools=await root.locator('[data-vf-page-context=tool] .vf-frontend-pages__coverage').innerText();
 check('individual tools are named from current catalog',tools.includes('目录配置中的工具')&&/MP4/i.test(tools)&&tools.includes('备份')&&tools.includes('播放器')&&tools.includes('实际开放入口'),tools);
 check('archive includes category tag author and date',await root.locator('[data-vf-page-context=archive_list] .vf-frontend-pages__coverage').innerText().then(x=>['分类归档','标签归档','作者归档','日期归档'].every(k=>x.includes(k))));
 check('legal covers separate privacy and terms pages',await root.locator('[data-vf-page-context=legal] .vf-frontend-pages__coverage').innerText().then(x=>x.includes('隐私政策')&&x.includes('使用条款')));
 check('FAQ entries are not claimed to be separate detail pages',await root.locator('[data-vf-page-context=faq_page] .vf-frontend-pages__coverage').innerText().then(x=>x.includes('条目不等于独立详情页')));
 const filter=root.locator('form[method=get]').first();
 await filter.locator('input[name=vf_pages_q]').fill('作者归档');await filter.getByRole('button',{name:'筛选',exact:true}).click();await page.waitForLoadState('networkidle');
 check('search discovers subtype that old label hid',await root.locator('[data-vf-page-context]').count()===1&&await root.locator('[data-vf-page-context=archive_list]').count()===1);
 const edit=await root.locator('.vf-frontend-pages__actions .button').getAttribute('href');check('layout action retains type language and search',edit.includes('context=archive_list')&&edit.includes('vf_pages_language=zh')&&new URL(edit).searchParams.get('vf_pages_q')==='作者归档',edit);
 await filter.locator('input[name=vf_pages_q]').fill('备份');await filter.getByRole('button',{name:'筛选',exact:true}).click();await page.waitForLoadState('networkidle');
 check('tool names participate in type search',await root.locator('[data-vf-page-context=tool]').count()===1);
 await page.goto(target+'&vf_pages_language=en',{waitUntil:'networkidle'});
 await root.locator('#vf-frontend-pages-content > summary').click();const content=root.locator('[data-vf-frontend-content-form]');
 await content.locator('[name=vf_content_q]').fill('Directory coverage fixture');await content.locator('[name=vf_content_type]').selectOption('post');await content.locator('[data-vf-content-submit]').click();await page.waitForLoadState('networkidle');
 check('published content explicitly loads real 25 objects with 20 on first page',await root.locator('.vf-frontend-pages__content-list li').count()===20&&await root.locator('#vf-frontend-pages-content').innerText().then(x=>/找到 25 项/.test(x)&&/第 1 \/ 2 页/.test(x)));
 await content.getByRole('button',{name:'下一页',exact:true}).click();await page.waitForLoadState('networkidle');
 check('content pagination shows remaining objects and retains filters',await root.locator('.vf-frontend-pages__content-list li').count()===5&&await content.locator('[name=vf_content_q]').inputValue()==='Directory coverage fixture'&&await content.locator('[name=vf_content_type]').inputValue()==='post'&&await content.locator('[name=vf_pages_language]').inputValue()==='en'&&await root.locator('#vf-frontend-pages-content').innerText().then(x=>/第 2 \/ 2 页/.test(x)));
 await content.locator('[name=vf_pages_language]').selectOption('zh');await content.locator('[data-vf-content-submit]').click();await page.waitForLoadState('networkidle');
 const links=await root.locator('.vf-frontend-pages__content-list a[target=_blank]').evaluateAll(xs=>xs.map(x=>x.href));check('language change resets pagination and returns matching real URLs',links.length===20&&links.every(x=>x.startsWith(origin+'/zh/'))&&await root.locator('#vf-frontend-pages-content').innerText().then(x=>/第 1 \/ 2 页/.test(x)));
 const invalid=await page.request.post(target,{form:{vf_theme_action:'frontend_pages_read',vf_pages_language:'en',vf_content_type:'post',vf_content_q:'Directory coverage fixture',_wpnonce:'invalid-synthetic'}});const invalidBody=await invalid.text();check('invalid nonce still blocks content read',invalidBody.includes('页面已过期')&&!invalidBody.includes('class="vf-frontend-pages__content-list"'));
 await page.goto(target+'&vf_review_tools=1',{waitUntil:'networkidle'});check('explanations do not assert human PASS',await root.locator('.vf-frontend-pages__review-overview').innerText().then(x=>x.includes('本版人工确认 0 / 20')&&x.includes('开发完成不等于验收通过')));
 await root.locator('#vf-review-archive_list > details > summary').click();check('existing review record and state details remain reachable',await root.locator('#vf-review-archive_list .vf-frontend-pages__progress-record').isVisible());
 const cases=JSON.parse(fs.readFileSync('proof/cases.json','utf8')).cases;const response=await page.goto(cases.en.home,{waitUntil:'load'});check('public home remains available',response.status()===200&&await page.locator('h1').count()===1);
 check('no browser script errors',errors.length===0,errors);
 console.log('OVERVIEW_FOCUSED_PASS',checks.length);
 }finally{fs.writeFileSync('proof/'+(baseline?'baseline-results':'browser-results')+'.json',JSON.stringify({status:checks.every(x=>x.pass)?'PASS':'FAIL',count:checks.length,passed:checks.filter(x=>x.pass).length,checks},null,2));await browser.close();}})().catch(e=>{console.error(e);process.exit(1)});
