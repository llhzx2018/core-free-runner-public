import { chromium } from 'playwright';

const base=process.env.VF_R2_BASE_URL;
const password=process.env.VF_R2_PASSWORD;
if(!base||!password)throw new Error('missing R2 browser environment');
const assert=(ok,msg)=>{if(!ok)throw new Error(msg);};

const browser=await chromium.launch({headless:true});
const context=await browser.newContext({viewport:{width:1440,height:900}});
const page=await context.newPage();

async function login(){
  await page.goto(base+'/',{waitUntil:'networkidle'});
  const unlock=page.locator('[data-open-login]').first();
  if(await unlock.count()){
    await page.evaluate(()=>openLogin());
    await page.locator('#loginForm input[name="password"]').fill(password);
    await page.locator('#loginSubmit').click();
    await page.waitForFunction(async()=>{const j=await (await fetch('/api.php?action=session',{cache:'no-store'})).json();return !!j?.site?.auth;});
  }
}

async function seed(){
  return await page.evaluate(async()=>{
    const session=await (await fetch('/api.php?action=session',{cache:'no-store'})).json();
    const post=async(action,body)=>{
      const r=await fetch('/api.php?action='+action,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':session.csrf},body:JSON.stringify(body)});
      const j=await r.json();
      if(!j.ok)throw new Error(action+': '+JSON.stringify(j));
      return j;
    };
    const cat=await post('category_save',{name:'R2细节审计',description:'synthetic R2',icon:'folder'});
    const empty=await post('category_save',{name:'R2空分类',description:'synthetic empty R2',icon:'folder'});
    const ids=[];
    for(let i=0;i<2;i++){
      const x=await post('content_save',{category_id:cat.id,title:'R2重复内容'+i,content:'# R2 重复\n\n完全相同正文。',content_mode:'article',content_format:'markdown',primary_action:'read',status:'active'});
      ids.push(x.id);
    }
    return {categoryId:cat.id,emptyCategoryId:empty.id,ids};
  });
}

function named(el){
  if(!el)return false;
  return !!(el.getAttribute('aria-label')||el.getAttribute('aria-labelledby')||(el.labels&&el.labels.length)||el.closest('label')||el.getAttribute('placeholder'));
}

try{
  await login();
  const fixture=await seed();

  // Editor controls + semantic labels.
  await page.setViewportSize({width:390,height:844});
  await page.goto(base+'/',{waitUntil:'networkidle'});
  await page.evaluate(()=>openNewContent());
  await page.waitForSelector('.editor-page-form');
  await page.evaluate(()=>{const d=document.querySelector('#editorMore');if(d)d.open=true;});
  await page.waitForTimeout(180);

  const editor=await page.evaluate(()=>{
    const h=el=>el?.getBoundingClientRect().height||0;
    const font=el=>parseFloat(getComputedStyle(el).fontSize)||0;
    const visible=el=>!!el&&getComputedStyle(el).display!=='none'&&el.getClientRects().length>0;
    const named=el=>!!(el.getAttribute('aria-label')||el.getAttribute('aria-labelledby')||(el.labels&&el.labels.length)||el.closest('label')||el.getAttribute('placeholder'));
    const tabs=[...document.querySelectorAll('.editor-tabs button')].filter(visible).map(h);
    const toolbar=[...document.querySelectorAll('.vf-editor-toolbar button:not([hidden])')].filter(visible).map(h);
    const heading=document.querySelector('.vf-editor-heading-select');
    const record=[...document.querySelectorAll('.record-toggle')].filter(visible).map(h);
    const controls=['title','category_id','content','content_format','description','tags','aliases'].map(name=>document.querySelector('[name="'+name+'"]'));
    return {
      tabs,toolbar,headingHeight:h(heading),headingFont:font(heading),
      contentFont:font(document.querySelector('textarea[name="content"]')),
      record,
      named:controls.map(x=>({name:x?.getAttribute('name')||'',ok:named(x),id:x?.id||''}))
    };
  });
  assert(editor.tabs.length&&editor.tabs.every(x=>x>=43),'editor tabs still undersized '+JSON.stringify(editor));
  assert(editor.toolbar.length&&editor.toolbar.every(x=>x>=43),'editor toolbar still undersized '+JSON.stringify(editor));
  assert(editor.headingHeight>=43&&editor.headingFont>=16,'editor heading select still undersized '+JSON.stringify(editor));
  assert(editor.contentFont>=16,'editor textarea mobile font still undersized '+JSON.stringify(editor));
  assert(editor.record.length&&editor.record.every(x=>x>=43),'editor favorite/pinned touch labels still undersized '+JSON.stringify(editor));
  assert(editor.named.every(x=>x.ok),'editor controls still missing semantic names '+JSON.stringify(editor.named));
  console.log('P02_V2581_R2_EDITOR=PASS');

  // Settings semantic labels, including display/security/transfer.
  await page.goto(base+'/#settings=display',{waitUntil:'networkidle'});
  await page.waitForSelector('#settingsPanel');
  const displaySemantics=await page.evaluate(()=>[...document.querySelectorAll('#settingsPanel input:not([type="hidden"]):not([type="file"]),#settingsPanel select,#settingsPanel textarea')].filter(el=>getComputedStyle(el).display!=='none').map(el=>({name:el.name||el.id,ok:!!(el.getAttribute('aria-label')||el.getAttribute('aria-labelledby')||(el.labels&&el.labels.length)||el.closest('label'))})));
  assert(displaySemantics.length&&displaySemantics.every(x=>x.ok),'display settings semantic labels missing '+JSON.stringify(displaySemantics));

  await page.goto(base+'/#settings=security',{waitUntil:'networkidle'});
  await page.waitForSelector('#passwordForm');
  const passwordSemantics=await page.evaluate(()=>[...document.querySelectorAll('#passwordForm input')].map(el=>({name:el.name,ok:!!((el.labels&&el.labels.length)||el.getAttribute('aria-label')||el.getAttribute('aria-labelledby'))})));
  assert(passwordSemantics.length===3&&passwordSemantics.every(x=>x.ok),'password semantics missing '+JSON.stringify(passwordSemantics));

  await page.goto(base+'/#settings=transfer',{waitUntil:'networkidle'});
  await page.waitForSelector('#jsonMode');
  const jsonName=await page.locator('#jsonMode').getAttribute('aria-label');
  assert(jsonName==='JSON 导入方式','JSON mode semantic label missing: '+jsonName);
  console.log('P02_V2581_R2_FORM_SEMANTICS=PASS');

  // Notebook residual mobile details, including empty-state create action.
  await page.goto(base+'/',{waitUntil:'networkidle'});
  await page.evaluate(async id=>{await setMode('all','active');if(state.contentView!=='notebook')await setContentView('notebook');await selectCategory(id);},fixture.categoryId);
  await page.waitForSelector('#notebookTitleSearch');
  const notebook=await page.evaluate(()=>({
    searchHeight:document.querySelector('.notebook-title-search')?.getBoundingClientRect().height||0,
    searchFont:parseFloat(getComputedStyle(document.querySelector('#notebookTitleSearch')).fontSize)||0,
    countFont:parseFloat(getComputedStyle(document.querySelector('#notebookTitleCount')).fontSize)||0
  }));
  assert(notebook.searchHeight>=43&&notebook.searchFont>=16&&notebook.countFont>=11.5,'notebook mobile detail drift '+JSON.stringify(notebook));
  await page.evaluate(async id=>{await selectCategory(id);},fixture.emptyCategoryId);
  await page.waitForSelector('#notebookListEmptyNew');
  const emptyHeight=await page.locator('#notebookListEmptyNew').evaluate(el=>el.getBoundingClientRect().height);
  assert(emptyHeight>=43,'notebook empty-create touch target undersized '+emptyHeight);
  console.log('P02_V2581_R2_NOTEBOOK=PASS');

  // Standalone system page navigation/actions.
  for(const [path,selector] of [['/system-info.php','nav a,nav strong'],['/diagnose.php','nav a,nav strong,.actions a']]){
    await page.goto(base+path,{waitUntil:'networkidle'});
    const heights=await page.evaluate(sel=>[...document.querySelectorAll(sel)].filter(el=>getComputedStyle(el).display!=='none').map(el=>el.getBoundingClientRect().height),selector);
    assert(heights.length&&heights.every(x=>x>=43),'standalone mobile navigation undersized '+path+' '+JSON.stringify(heights));
  }
  console.log('P02_V2581_R2_STANDALONE_NAV=PASS');

  // Duplicate governance / comparison mobile detail typography.
  await page.goto(base+'/#settings=transfer',{waitUntil:'networkidle'});
  await page.waitForSelector('#settingsPanel');
  await page.evaluate(async()=>{const b=document.createElement('button');b.id='r2AuditDuplicateButton';b.hidden=true;document.body.appendChild(b);await openDuplicateGovernance(b);});
  await page.waitForSelector('.duplicate-governance-modal');
  const duplicate=await page.evaluate(()=>{
    const visible=el=>getComputedStyle(el).display!=='none'&&el.getClientRects().length>0;
    return {
      smallFonts:[...document.querySelectorAll('.duplicate-governance-modal .duplicate-section h3 small,.duplicate-governance-modal .duplicate-groups small')].filter(visible).map(el=>parseFloat(getComputedStyle(el).fontSize)||0),
      compareHeights:[...document.querySelectorAll('.duplicate-governance-modal [data-compare-left]')].filter(visible).map(el=>el.getBoundingClientRect().height)
    };
  });
  assert(duplicate.smallFonts.length&&duplicate.smallFonts.every(x=>x>=11.5),'duplicate governance tiny text remains '+JSON.stringify(duplicate));
  assert(duplicate.compareHeights.length&&duplicate.compareHeights.every(x=>x>=43),'duplicate governance compare action undersized '+JSON.stringify(duplicate));

  await page.locator('.duplicate-governance-modal [data-compare-left]').first().click();
  await page.waitForSelector('.content-compare-modal');
  const compare=await page.evaluate(()=>{
    const visible=el=>getComputedStyle(el).display!=='none'&&el.getClientRects().length>0;
    return {
      headerFonts:[...document.querySelectorAll('.content-compare-modal .compare-grid header small')].filter(visible).map(el=>parseFloat(getComputedStyle(el).fontSize)||0),
      buttons:[...document.querySelectorAll('.content-compare-modal .modal-footer .btn')].filter(visible).map(el=>el.getBoundingClientRect().height),
      selects:[...document.querySelectorAll('.content-compare-modal select')].map(el=>({id:el.id,named:!!((el.labels&&el.labels.length)||el.closest('label')||el.getAttribute('aria-label')||el.getAttribute('aria-labelledby'))}))
    };
  });
  assert(compare.headerFonts.length&&compare.headerFonts.every(x=>x>=11.5),'compare modal tiny metadata remains '+JSON.stringify(compare));
  assert(compare.buttons.length&&compare.buttons.every(x=>x>=43),'compare modal footer action undersized '+JSON.stringify(compare));
  assert(compare.selects.length===3&&compare.selects.every(x=>x.named),'compare modal selects lack semantics '+JSON.stringify(compare.selects));
  console.log('P02_V2581_R2_DUPLICATE_COMPARE=PASS');

  console.log('P02_V2581_R2_BROWSER=PASS');
} finally {
  await browser.close();
}
