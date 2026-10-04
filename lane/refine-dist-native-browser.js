'use strict';
const fs=require('fs');
const {chromium}=require('playwright');

const BASE='http://127.0.0.1:18092';
const WIDTHS=[1920,1440,1024,768,390];

async function metrics(page){
  return page.evaluate(()=>{
    const visible=e=>{if(!e)return false;const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden';};
    const visibleText=[...document.querySelectorAll('body *')].filter(visible).map(e=>(e.children.length===0?e.textContent:'').trim()).filter(Boolean).join(' ');
    return {
      h1:[...document.querySelectorAll('.vf-v6-shell-main h1')].filter(visible).map(e=>e.textContent.trim()),
      kicker:[...document.querySelectorAll('.vf-r18-pagehead-kicker')].filter(visible).map(e=>e.textContent.trim()),
      legacyGate:/SEO\s*Gate.*(?:自动运行|Run Gate|阻断|提醒)/i.test(visibleText),
      overflow:document.documentElement.scrollWidth>document.documentElement.clientWidth+2,
      title:document.title,
      bodyClass:document.body.className,
      refineScript:[...document.scripts].map(s=>s.src||'').find(src=>src.includes('admin-seo-refine'))||'',
      r53Style:[...document.querySelectorAll('link[rel="stylesheet"]')].map(l=>l.href||'').find(h=>h.includes('admin-current-r53-product-bundle'))||''
    };
  });
}

(async()=>{
  const browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1440,height:1100}});
  const failures=[],cases=[];

  await page.goto(BASE+'/wp-login.php',{waitUntil:'domcontentloaded'});
  await page.locator('#user_login').fill('admin');
  await page.locator('#user_pass').fill('Synthetic-Refine-Fixture-Only!');
  await Promise.all([page.waitForNavigation({waitUntil:'networkidle'}),page.locator('#wp-submit').click()]);
  if(new URL(page.url()).pathname.includes('wp-login.php'))throw new Error('SYNTHETIC_LOGIN_FAILED');

  for(const width of WIDTHS){
    await page.setViewportSize({width,height:1100});

    const contentUrl=BASE+'/wp-admin/admin.php?page=vf-toolsite-content&tab=workflow&workspace=articles';
    const contentResp=await page.goto(contentUrl,{waitUntil:'networkidle'});
    const contentState=await metrics(page);
    const contentControls=await page.evaluate(()=>({
      search:!!document.querySelector('input[name="vf_content_q"]'),
      type:!!document.querySelector('select[name="vf_content_type"]'),
      advanced:!!document.querySelector('.vf-content-manager-advanced-filters'),
      rows:document.querySelectorAll('[data-vf-content-row]').length,
      manage:document.querySelectorAll('[data-vf-content-more]').length
    }));
    if(contentResp.status()>=400)failures.push({width,case:'content-http',status:contentResp.status()});
    if(contentState.h1.length!==1||contentState.h1[0]!=='内容库')failures.push({width,case:'content-title',contentState});
    if(contentState.kicker.length)failures.push({width,case:'content-kicker',contentState});
    if(contentState.overflow)failures.push({width,case:'content-overflow',contentState});
    if(!contentControls.search||!contentControls.type||!contentControls.advanced||contentControls.rows<1||contentControls.manage<1)failures.push({width,case:'content-controls',contentControls});

    const refineUrl=BASE+'/wp-admin/admin.php?page=vf-toolsite-seo-keywords&tab=planner&workspace=refine';
    const refineResp=await page.goto(refineUrl,{waitUntil:'networkidle'});
    const refineState=await metrics(page);
    const refineControls=await page.evaluate(()=>({
      selector:!!document.querySelector('[data-vf-seo-selector]'),
      search:!!document.querySelector('input[name="seo_q"]'),
      type:!!document.querySelector('select[name="seo_type"]'),
      issue:!!document.querySelector('select[name="seo_issue"]'),
      perPage:!!document.querySelector('select[name="seo_per_page"]'),
      rows:document.querySelectorAll('.vf-o7-task-list>a').length,
      enabled:[...document.querySelectorAll('.vf-o7-filter-bar input,.vf-o7-filter-bar select,.vf-o7-filter-bar button')].every(e=>!e.disabled)
    }));
    if(refineResp.status()>=400)failures.push({width,case:'refine-http',status:refineResp.status()});
    if(refineState.h1.length!==1||refineState.h1[0]!=='单页精修')failures.push({width,case:'refine-title',refineState});
    if(refineState.kicker.length)failures.push({width,case:'refine-kicker',refineState});
    if(refineState.legacyGate)failures.push({width,case:'legacy-gate-visible',refineState});
    if(refineState.overflow)failures.push({width,case:'refine-overflow',refineState});
    if(!refineControls.selector||!refineControls.search||!refineControls.type||!refineControls.issue||!refineControls.perPage||!refineControls.enabled||refineControls.rows<1)failures.push({width,case:'refine-controls',refineControls});

    cases.push({width,content:contentState,contentControls,refine:refineState,refineControls});
  }

  await page.setViewportSize({width:1440,height:1100});
  await page.goto(BASE+'/wp-admin/admin.php?page=vf-toolsite-seo-keywords&tab=planner&workspace=refine',{waitUntil:'networkidle'});
  await page.locator('input[name="seo_q"]').fill('Refine Fixture 03');
  await Promise.all([page.waitForNavigation({waitUntil:'networkidle'}),page.locator('.vf-o7-filter-actions button[type="submit"]').click()]);
  const filtered=await page.evaluate(()=>[...document.querySelectorAll('.vf-o7-task-copy strong')].map(e=>e.textContent.trim()));
  if(filtered.length<1||filtered.some(t=>!t.includes('Refine Fixture 03')))failures.push({case:'refine-search-filter',filtered});

  await page.goto(BASE+'/wp-admin/admin.php?page=vf-toolsite-seo-keywords&tab=planner&workspace=refine',{waitUntil:'networkidle'});
  const enterCurrent=page.locator('.vf-o7-focus-task a.button[href*="post_id="]').first();
  if(await enterCurrent.count()!==1)failures.push({case:'refine-no-current-entry'});
  else{
    const detailHref=await enterCurrent.getAttribute('href');
    if(!detailHref)failures.push({case:'refine-current-entry-missing-href'});
    else await page.goto(detailHref,{waitUntil:'networkidle'});
    const detail=await page.evaluate(()=>({
      detail:!!document.querySelector('[data-vf-refine-page]'),
      steps:document.querySelectorAll('.vf-refine-steps>a').length,
      boundary:(document.querySelector('.vf-refine-boundary')?.textContent||'').trim(),
      postId:document.querySelector('[data-vf-refine-page]')?.getAttribute('data-post-id')||''
    }));
    if(!detail.detail||detail.steps!==5||!detail.boundary.includes('人工显式操作')||!detail.postId)failures.push({case:'refine-detail-structure',detail});

    const seoStep=page.locator('.vf-refine-steps>a').filter({hasText:'关键词与 SEO'}).first();
    if(await seoStep.count()!==1)failures.push({case:'refine-seo-step-missing'});
    else{
      await Promise.all([page.waitForNavigation({waitUntil:'networkidle'}),seoStep.click()]);
      const titleInput=page.locator('input[name="vf_ops_refinement_proposal[rank_math_title]"]');
      if(await titleInput.count()!==1)failures.push({case:'refine-title-input-missing'});
      else{
        const disabled=await titleInput.isDisabled();
        if(disabled){
          const coreProtected=await page.evaluate(()=>document.body.innerText.includes('核心保护')||document.body.innerText.includes('核心页面'));
          if(!coreProtected)failures.push({case:'refine-disabled-without-core-protection'});
        }else{
          await titleInput.fill('Synthetic SEO Title 1035');
          const preview=(await page.locator('[data-vf-serp-title]').innerText()).trim();
          if(preview!=='Synthetic SEO Title 1035')failures.push({case:'refine-serp-preview',preview});
        }
      }
    }
  }

  await browser.close();
  const result={pass:failures.length===0,cases,failures,owner_product_pass:false,production:'NOT_TOUCHED'};
  fs.writeFileSync('evidence/native-browser.json',JSON.stringify(result,null,2)+'\n');
  console.log(JSON.stringify(result));
  if(failures.length)process.exit(1);
})().catch(e=>{console.error(e);process.exit(1);});
