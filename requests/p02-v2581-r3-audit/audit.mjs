import { chromium } from 'playwright';

const base=process.env.VF_AUDIT_BASE_URL;
const password=process.env.VF_AUDIT_PASSWORD;
if(!base||!password) throw new Error('missing audit environment');

const findings=new Map();
const observations=[];
function add(sev,surface,code,detail){
  const key=[surface,code,detail].join('|');
  if(!findings.has(key)) findings.set(key,{severity:sev,surface,code,detail});
}
function note(surface,detail){ observations.push({surface,detail}); }

const browser=await chromium.launch({headless:true});
const context=await browser.newContext({viewport:{width:1440,height:900}});
const page=await context.newPage();
let activeSurface='boot';
page.on('pageerror',e=>add('P1',activeSurface,'PAGE_ERROR',String(e)));
page.on('console',m=>{ if(m.type()==='error') add('P2',activeSurface,'CONSOLE_ERROR',m.text().slice(0,260)); });

async function login(){
  activeSurface='登录入口';
  await page.goto(base+'/',{waitUntil:'networkidle'});
  await audit('登录入口','desktop');
  const unlock=page.locator('[data-open-login]').first();
  if(await unlock.count()){
    await page.evaluate(()=>openLogin());
    await page.waitForSelector('#loginForm input[name="password"]');
    await audit('登录弹窗','desktop');
    await page.locator('#loginForm input[name="password"]').fill(password);
    await page.locator('#loginSubmit').click();
    await page.waitForFunction(async()=>{const r=await fetch('/api.php?action=session',{cache:'no-store'});const j=await r.json();return !!j?.site?.auth;});
  }
}

function signature(el){
  const id=el.id?'#'+el.id:'';
  const cls=[...el.classList].slice(0,3).map(x=>'.'+x).join('');
  const name=el.getAttribute('name')?('[name="'+el.getAttribute('name')+'"]'):'';
  return (el.tagName||'').toLowerCase()+id+cls+name;
}
async function audit(surface,profile){
  activeSurface=surface;
  await page.waitForTimeout(80);
  const issues=await page.evaluate(({surface,profile})=>{
    const out=[];
    const visible=el=>{
      const s=getComputedStyle(el),r=el.getBoundingClientRect();
      return s.display!=='none'&&s.visibility!=='hidden'&&Number(s.opacity)>0.01&&r.width>1&&r.height>1;
    };
    const sig=el=>{
      const id=el.id?'#'+el.id:'';
      const cls=[...el.classList].slice(0,3).map(x=>'.'+x).join('');
      const name=el.getAttribute('name')?('[name="'+el.getAttribute('name')+'"]'):'';
      return (el.tagName||'').toLowerCase()+id+cls+name;
    };
    const root=document.documentElement;
    if(root.scrollWidth>root.clientWidth+3) out.push(['P2','HORIZONTAL_OVERFLOW','document '+root.scrollWidth+'>'+root.clientWidth]);
    const ids={};
    document.querySelectorAll('[id]').forEach(el=>{ids[el.id]=(ids[el.id]||0)+1;});
    Object.entries(ids).filter(([,n])=>n>1).forEach(([id,n])=>out.push(['P2','DUPLICATE_ID','#'+id+' x'+n]));

    const dialogs=[...document.querySelectorAll('.modal,.modal-card,[role="dialog"],dialog')].filter(visible);
    for(const el of dialogs){
      const r=el.getBoundingClientRect();
      if(r.left<-2||r.right>innerWidth+2||r.top<-2||r.bottom>innerHeight+2) out.push(['P2','DIALOG_CLIPPED',sig(el)+' rect='+JSON.stringify({l:Math.round(r.left),t:Math.round(r.top),r:Math.round(r.right),b:Math.round(r.bottom),vw:innerWidth,vh:innerHeight})]);
      if(el.scrollWidth>el.clientWidth+3) out.push(['P2','DIALOG_HORIZONTAL_OVERFLOW',sig(el)+' '+el.scrollWidth+'>'+el.clientWidth]);
    }

    const fixed=[...document.querySelectorAll('*')].filter(el=>visible(el)&&['fixed','sticky'].includes(getComputedStyle(el).position));
    for(const el of fixed){
      if(el.matches('#sidebar:not(.open)')) continue; // intentional closed mobile drawer
      const r=el.getBoundingClientRect();
      if(r.width>innerWidth+4||r.left<-6||r.right>innerWidth+6) out.push(['P2','FIXED_OFFSCREEN',sig(el)]);
    }

    const interact=[...document.querySelectorAll('button,a[href],input,select,textarea,summary,[role="button"],[tabindex]:not([tabindex="-1"])')].filter(visible);
    if(profile==='mobile'){
      for(const el of interact){
        const r=el.getBoundingClientRect();
        const type=(el.getAttribute('type')||'').toLowerCase();
        if(type==='hidden'||type==='file') continue;
        const touchOwner=(type==='checkbox'||type==='radio')?el.closest('label'):null;
        const touchOwnerHeight=touchOwner?touchOwner.getBoundingClientRect().height:0;
        if(r.height<40 && touchOwnerHeight<40 && !el.closest('.notebook-title-row,.content-row')) out.push(['P3','MOBILE_SMALL_TARGET',sig(el)+' h='+Math.round(r.height)]);
        if(['INPUT','SELECT','TEXTAREA'].includes(el.tagName)&&type!=='checkbox'&&type!=='radio'){
          const fs=parseFloat(getComputedStyle(el).fontSize)||0;
          if(fs>0&&fs<16) out.push(['P3','MOBILE_FORM_FONT_LT16',sig(el)+' '+fs+'px']);
        }
      }
    }

    for(const el of interact){
      if(el.tagName==='INPUT'&&['hidden','file'].includes((el.getAttribute('type')||'').toLowerCase())) continue;
      const id=el.id||'';
      const associatedLabel=id&&document.querySelector('label[for="'+CSS.escape(id)+'"]');
      const name=(el.getAttribute('aria-label')||el.getAttribute('aria-labelledby')||el.getAttribute('title')||el.textContent||el.getAttribute('placeholder')||el.getAttribute('value')||'').trim();
      if(!name && !associatedLabel && !el.closest('label')) out.push(['P3','UNNAMED_CONTROL',sig(el)]);
      if((el.scrollWidth>el.clientWidth+4||el.scrollHeight>el.clientHeight+6)&&['BUTTON','A'].includes(el.tagName)){
        const cs=getComputedStyle(el);
        if(cs.overflow!=='visible') out.push(['P3','CONTROL_CONTENT_CLIPPED',sig(el)+' '+el.scrollWidth+'x'+el.scrollHeight+' / '+el.clientWidth+'x'+el.clientHeight]);
      }
    }

    const texts=[...document.querySelectorAll('small,.form-note,.section-copy,.content-meta,.notebook-title-meta,.settings-nav-label,.tech')].filter(visible);
    for(const el of texts){
      const fs=parseFloat(getComputedStyle(el).fontSize)||0;
      const threshold=profile==='mobile'?10.5:9.5;
      if(fs>0&&fs<threshold) out.push(['P3','TINY_TEXT',sig(el)+' '+fs+'px']);
    }

    const inputs=[...document.querySelectorAll('input:not([type="hidden"]):not([type="file"]),select,textarea')].filter(visible);
    for(const el of inputs){
      const id=el.id;
      const labelled=el.getAttribute('aria-label')||el.getAttribute('aria-labelledby')||(id&&document.querySelector('label[for="'+CSS.escape(id)+'"]'))||el.closest('label')||el.getAttribute('placeholder');
      if(!labelled) out.push(['P3','FORM_CONTROL_NO_LABEL',sig(el)]);
    }

    return out;
  },{surface,profile});
  for(const [sev,code,detail] of issues) add(sev,surface,code,detail);
}

async function seed(){
  return await page.evaluate(async()=>{
    const s=await (await fetch('/api.php?action=session',{cache:'no-store'})).json();
    const post=async(action,body)=>{const r=await fetch('/api.php?action='+action,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':s.csrf},body:JSON.stringify(body)});const j=await r.json();if(!j.ok)throw new Error(action+': '+JSON.stringify(j));return j;};
    const cat=await post('category_save',{name:'细节审计分类-超长名称用于检查布局溢出和按钮挤压',description:'synthetic detail audit',icon:'folder'});
    const ids=[];
    for(let i=0;i<12;i++){
      const title=i===0?'这是一个非常非常非常非常非常非常非常长的中文标题用于检查窄屏布局以及操作按钮是否会发生遮挡或错位_'+i:(i===1?'UNBROKEN_'+('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'.repeat(5)):'DETAIL_AUDIT_'+String(i).padStart(2,'0'));
      const content=(i===2||i===3)?'# 重复内容\n\n完全相同的正文用于重复治理对比。':('# 审计资料 '+i+'\n\n'+('用于检查阅读、编辑、列表、滚动和响应式布局的中文段落。\n\n'.repeat(24)));
      const x=await post('content_save',{category_id:cat.id,title,content,content_mode:'article',content_format:'markdown',primary_action:'read',status:'active'});
      ids.push(x.id);
    }
    return {categoryId:cat.id,ids};
  });
}

async function desktopAndMobile(surface,prep){
  await page.setViewportSize({width:1440,height:900});
  if(prep) await prep();
  await audit(surface+' · 1440','desktop');
  await page.setViewportSize({width:1024,height:768});
  await page.waitForTimeout(120);
  await audit(surface+' · 1024','desktop');
  await page.setViewportSize({width:390,height:844});
  await page.waitForTimeout(120);
  await audit(surface+' · 390','mobile');
  await page.setViewportSize({width:1440,height:900});
}

try{
  await login();
  const fixture=await seed();

  // Explicit route-intent checks that generic geometry cannot catch.
  await page.evaluate(()=>{
    localStorage.removeItem('vftb-scratch-workspace-open-v1');
    localStorage.setItem('vftb-mode','all');
    localStorage.setItem('vftb-status','active');
    localStorage.setItem('vftb-content-view','list');
  });
  await page.goto(base+'/?scratch=1',{waitUntil:'networkidle'});
  await page.waitForTimeout(500);
  if(await page.locator('#scratchWorkspaceV259').count()===0) add('P2','Scratch 直达入口','SCRATCH_QUICK_ROUTE_IGNORED','/?scratch=1 未自动打开临时页签工作台');
  await page.evaluate(()=>localStorage.removeItem('vftb-scratch-workspace-open-v1'));

  for(const target of ['system','updates','backup']){
    await page.goto(base+'/system-info.php',{waitUntil:'networkidle'});
    await page.evaluate(()=>{
      localStorage.setItem('vftb-mode','all');
      localStorage.setItem('vftb-status','active');
      localStorage.setItem('vftb-content-view','list');
    });
    await page.goto(base+'/#settings='+target,{waitUntil:'networkidle'});
    await page.waitForTimeout(220);
    const routed=await page.evaluate(t=>typeof state!=='undefined'&&state.mode==='settings'&&state.settingsSection===t,target).catch(()=>false);
    if(!routed) add('P2','系统独立页返回入口','SETTINGS_DEEPLINK_IGNORED','#settings='+target+' 未路由到对应设置子页');
  }
  await page.goto(base+'/',{waitUntil:'networkidle'});
  await page.waitForFunction(()=>typeof state!=='undefined'&&state.site&&state.site.auth);


  await desktopAndMobile('全部资料列表',async()=>{
    await page.evaluate(async()=>{await setMode('all','active'); if(state.contentView!=='list') await setContentView('list');});
    await page.waitForSelector('.content-row');
  });

  await desktopAndMobile('分类资料列表',async()=>{
    await page.evaluate(async id=>{if(state.contentView!=='list')await setContentView('list');await selectCategory(id);},fixture.categoryId);
    await page.waitForSelector('.content-row');
  });

  await desktopAndMobile('回收站',async()=>{
    await page.evaluate(async()=>{await setMode('all','trash');});
    await page.waitForTimeout(160);
  });

  await desktopAndMobile('笔记工作区/阅读',async()=>{
    await page.evaluate(async()=>{await setMode('all','active');await setContentView('notebook');});
    await page.waitForSelector('.notebook-list-pane');
    const row=page.locator('.notebook-title-row').first();
    if(await row.count()) await row.click();
    await page.waitForTimeout(180);
  });

  await desktopAndMobile('新建编辑器',async()=>{
    await page.evaluate(()=>openNewContent());
    await page.waitForTimeout(180);
  });

  // leave editor without mutations by discarding local draft state.
  // Use a fresh app boot before Settings surface enumeration so the audit does
  // not race setMode()'s intentionally fire-and-forget list reload.
  await page.evaluate(async()=>{ if(typeof clearEditorState==='function'){clearEditorState();state.editorItem=null;} await setMode('all','active'); });
  await page.goto(base+'/system-info.php',{waitUntil:'networkidle'});
  await page.goto(base+'/#settings=basic',{waitUntil:'networkidle'});
  await page.waitForSelector('#settingsPanel');

  const settings=['basic','content','display','search','transfer','system','updates','backup','security'];
  const labels={basic:'设置/基础',content:'设置/内容分类',display:'设置/显示排序',search:'设置/搜索使用',transfer:'设置/导入导出',system:'设置/系统概览',updates:'设置/在线升级',backup:'设置/备份恢复',security:'设置/安全隐私'};
  for(const section of settings){
    await desktopAndMobile(labels[section],async()=>{
      await page.evaluate(async s=>{await openSettings(s);},section);
      await page.waitForSelector('#settingsPanel');
      await page.waitForTimeout(100);
    });
  }

  await page.setViewportSize({width:1440,height:900});
  await page.evaluate(async()=>{await openSettings('transfer');});
  const dummy=await page.evaluateHandle(()=>{const b=document.createElement('button');b.textContent='audit';b.hidden=true;document.body.appendChild(b);return b;});
  await page.evaluate(async b=>{await openDuplicateGovernance(b);},dummy);
  await page.waitForSelector('.duplicate-governance-modal');
  await audit('重复内容治理 · 1440','desktop');
  const compare=page.locator('[data-compare-left]').first();
  if(await compare.count()){
    await compare.click();
    await page.waitForTimeout(160);
    await audit('内容对比合并 · 1440','desktop');
    await page.setViewportSize({width:390,height:844});
    await page.waitForTimeout(100);
    await audit('内容对比合并 · 390','mobile');
    await page.setViewportSize({width:1440,height:900});
  } else add('P2','重复内容治理','COMPARE_ENTRY_MISSING','已创建重复正文但扫描结果没有可用对比入口');

  // standalone authenticated pages
  for(const [path,name] of [['/system-info.php','系统信息'],['/system-baseline.php','系统基线'],['/diagnose.php','运行健康']]){
    await page.setViewportSize({width:1440,height:900});
    await page.goto(base+path,{waitUntil:'networkidle'});
    await audit(name+' · 1440','desktop');
    await page.setViewportSize({width:390,height:844});
    await page.waitForTimeout(100);
    await audit(name+' · 390','mobile');
  }

  // scratch
  await page.setViewportSize({width:1440,height:900});
  await page.goto(base+'/scratch/',{waitUntil:'networkidle'});
  await audit('Scratch · 1440','desktop');
  await page.setViewportSize({width:390,height:844});
  await page.waitForTimeout(100);
  await audit('Scratch · 390','mobile');

  const items=[...findings.values()];
  const rank={P1:1,P2:2,P3:3};
  items.sort((a,b)=>(rank[a.severity]-rank[b.severity])||a.surface.localeCompare(b.surface)||a.code.localeCompare(b.code));
  for(const f of items) console.log('FINDING|'+f.severity+'|'+f.surface+'|'+f.code+'|'+f.detail.replaceAll('\n',' '));
  const counts={P1:0,P2:0,P3:0};
  for(const f of items) counts[f.severity]++;
  console.log('AUDIT_SURFACE_COUNT=25');
  console.log('AUDIT_FINDING_COUNT='+items.length);
  console.log('AUDIT_P1='+counts.P1);
  console.log('AUDIT_P2='+counts.P2);
  console.log('AUDIT_P3='+counts.P3);
  console.log('P02_V2581_DETAIL_AUDIT=COMPLETE');
} finally {
  await browser.close();
}
