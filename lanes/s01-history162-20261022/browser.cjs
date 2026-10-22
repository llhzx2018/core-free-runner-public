const {chromium}=require('playwright');const fs=require('fs');
const baseline=process.argv[2]==='baseline',checks=[];
function check(name,pass,detail){checks.push({name,pass:!!pass,detail});if(!pass)throw Error(name+': '+JSON.stringify(detail));}
(async()=>{const browser=await chromium.launch();try{
 const origin='http://127.0.0.1:18880',target=origin+'/wp-admin/themes.php?page=vf-theme-modules&tab=layout&view=pages';
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(origin+'/wp-login.php');await page.locator('#user_login').fill('admin');await page.locator('#user_pass').fill('Synthetic-Only-Update-54!');await page.locator('input[name=redirect_to]').evaluate((x,v)=>x.value=v,target);await page.locator('#wp-submit').click();await page.waitForURL('**/wp-admin/**');await page.waitForLoadState('networkidle');
 const root=page.locator('[data-vf-frontend-pages]');
 check('canonical denominator stays 20 plus 2 shared',await root.locator('[data-vf-page-context]').count()===20&&await root.locator('.vf-frontend-pages__progress-record').count()===22);
 if(baseline){
 check('161 reproduces absent history despite existing published work',await root.locator('section[aria-label="已有桌面精修记录"]').count()===0);
 check('161 existing human acceptance is current before upgrade',await root.locator('.vf-frontend-pages__review-overview').textContent().then(x=>x.includes('本版人工确认 1 / 20')));
 console.log('161_HISTORY_BASELINE_PASS');return;}
 for(const width of [1920,1440,1319,1024])for(const lang of ['en','zh']){
  await page.setViewportSize({width,height:1000});await page.goto(target+'&vf_pages_language='+lang,{waitUntil:'networkidle'});await page.evaluate(()=>document.fonts.ready);
  check(width+'/'+lang+' visible history summaries on all 20 types',await root.locator('[data-vf-page-context] .vf-frontend-pages__coverage').evaluateAll(xs=>xs.length===20&&xs.every(x=>x.innerText.includes('已有精修记录：')&&x.getBoundingClientRect().height>0)));
  check(width+'/'+lang+' all 22 evidence sections present',await root.locator('section[aria-label="已有桌面精修记录"]').count()===22);
  check(width+'/'+lang+' no horizontal overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  check(width+'/'+lang+' no content implicitly loaded',await root.locator('.vf-frontend-pages__content-list li').count()===0&&await root.locator('#vf-frontend-pages-content').textContent().then(x=>x.includes('尚未加载')));
  check(width+'/'+lang+' history never increments human count',await root.locator('.vf-frontend-pages__review-overview').textContent().then(x=>x.includes('本版人工确认 0 / 20')));
  check(width+'/'+lang+' evidence is bounded desktop history',await root.locator('[aria-label="已有精修与剩余验收说明"]').innerText().then(x=>x.includes('不代表当前版本')&&x.includes('手机验收继续暂缓')&&x.includes('不因记录为空而重复执行')));
 }
 await page.setViewportSize({width:1440,height:1000});await page.goto(target+'&vf_pages_language=en',{waitUntil:'networkidle'});
 const all=root.locator('.vf-frontend-pages__progress-record');
 const hrefs=await all.locator('section[aria-label="已有桌面精修记录"] a').evaluateAll(xs=>xs.map(x=>x.href));
 check('all evidence links are exact release or run HTTPS URLs',hrefs.length>=40&&hrefs.every(x=>/^https:\/\/github.com\/llhzx2018\/(vf-tools-theme\/releases\/tag\/v1\.35\.\d+|core-free-runner-public\/actions\/runs\/\d+)$/.test(x)),hrefs);
 for(const context of ['home','tool','archive_list','contact_page']){
  const row=root.locator('[data-vf-page-context="'+context+'"]');await row.locator(':scope > details > summary').click();
  check(context+' history reachable separately from human form',await row.locator('section[aria-label="已有桌面精修记录"]').isVisible());
 }
 const home=root.locator('#vf-review-home');
 check('old genuine human acceptance retained and marked previous version',await home.locator('.vf-frontend-pages__progress-record').textContent().then(x=>x.includes('人工已确认')&&x.includes('上版记录，当前版待复核')&&x.includes('Synthetic existing owner record preserved')));
 const contact=root.locator('#vf-review-contact_page');
 check('existing needs-changes note preserved',await contact.locator('.vf-frontend-pages__progress-record').textContent().then(x=>x.includes('需要修改')&&x.includes('Synthetic contact note preserved')));
 const tool=root.locator('#vf-review-tool');
 check('tool history includes workspace results backup and domain limit',await tool.locator('section').first().innerText().then(x=>['1.35.154','1.35.155','1.35.158','领域功能'].every(t=>x.includes(t))));
 check('archive history states disabled dates are not forced open',await root.locator('#vf-review-archive_list section').first().innerText().then(x=>x.includes('1.35.161')&&x.includes('未启用的日期归档无需')));
 check('empty manual record says absent rather than unfinished engineering',await tool.locator('.vf-frontend-pages__progress-record').textContent().then(x=>x.includes('尚未保存人工复验记录')));
 await page.screenshot({path:'proof/history-en-1440.png',fullPage:true});
 await page.goto(target+'&vf_pages_language=zh&vf_review_device=mobile&vf_review_tools=1',{waitUntil:'networkidle'});
 const about=root.locator('#vf-review-about_page');await about.locator(':scope > details > summary').click();await about.locator('.vf-frontend-pages__progress-record > details > summary').click();
 check('unknown-schema record remains protected and cannot be overwritten',await about.locator('button[type=submit]').isDisabled()&&await about.textContent().then(x=>x.includes('旧记录格式异常')||x.includes('历史验证范围')));
 check('desktop history is not converted to mobile PASS',await about.textContent().then(x=>x.includes('这些记录仅覆盖桌面；手机验收暂缓')));
 await page.goto(target+'&vf_pages_language=zh',{waitUntil:'networkidle'});
 const filter=root.locator('form[method=get]').first();await filter.locator('[name=vf_pages_q]').fill('作者归档');await filter.getByRole('button',{name:'筛选',exact:true}).click();await page.waitForLoadState('networkidle');
 check('existing subtype filter and history preserved together',await root.locator('[data-vf-page-context]').count()===1&&await root.locator('#vf-review-archive_list .vf-frontend-pages__coverage').innerText().then(x=>x.includes('1.35.161')));
 await root.locator('#vf-review-archive_list > details > summary').click();
 await page.screenshot({path:'proof/history-zh-archive.png',fullPage:true});
 const invalid=await page.request.post(target,{form:{vf_theme_action:'frontend_pages_review_save',vf_review_subject:'home',vf_pages_language:'en',vf_review_device:'desktop',vf_review_phase:'complete',vf_review_status:'accepted',vf_review_note:'Should never be stored',vf_review_revision:'a'.repeat(64),vf_review_version:'1.35.162',_wpnonce:'invalid-synthetic'}});
 check('history display does not bypass existing nonce protection',(await invalid.text()).includes('页面已过期'));
 const anonymous=await page.request.get(target,{headers:{Cookie:''}});
 check('anonymous admin access still requires login',anonymous.url().includes('wp-login.php'));
 const cases=JSON.parse(fs.readFileSync('proof/cases.json','utf8')).cases;const response=await page.goto(cases.en.home,{waitUntil:'load'});check('public home unaffected',response.status()===200&&await page.locator('h1').count()===1);
 check('no browser errors',errors.length===0,errors);
 console.log('HISTORY_FOCUSED_PASS',checks.length);
 }finally{fs.writeFileSync('proof/'+(baseline?'baseline-results':'browser-results')+'.json',JSON.stringify({status:checks.every(x=>x.pass)?'PASS':'FAIL',count:checks.length,passed:checks.filter(x=>x.pass).length,checks},null,2));await browser.close();}})().catch(e=>{console.error(e);process.exit(1)});

