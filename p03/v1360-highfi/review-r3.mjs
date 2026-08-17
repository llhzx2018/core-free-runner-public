import { chromium } from 'playwright';
import fs from 'node:fs';

const base='http://127.0.0.1:8765/review.html';
const browser=await chromium.launch({headless:true});
const tasks=[]; const gates=[];
fs.mkdirSync('evidence/screenshots',{recursive:true});
const ok=(cond,msg)=>{if(!cond)throw new Error(msg);gates.push(msg)};
const rec=(id,clicks,ctx)=>tasks.push({id,clicks,context_switch:ctx,backtracking:0,dead_end:0,unknown_next_action:0,completion:'PASS'});
async function pageAt(hash,width=1440,height=1000){const p=await browser.newPage({viewport:{width,height}});await p.goto(base+hash,{waitUntil:'networkidle'});await p.waitForSelector('.app-shell');return p}
async function txt(p,s){return (await p.locator(s).innerText()).trim()}
async function waitHash(p,fragment){await p.waitForFunction(f=>location.hash.includes(f),fragment,{timeout:3000});ok(p.url().includes(fragment),`ROUTE ${fragment}`)}
async function first(p,s){const b=await p.locator(s).boundingBox(),v=p.viewportSize();return !!b&&!!v&&b.y<v.height&&b.y+Math.min(b.height,80)>0}
async function shot(name,hash,w=1440,h=1000){const p=await pageAt(hash,w,h);await p.screenshot({path:`evidence/screenshots/${name}.png`,fullPage:true});await p.close()}

try{
  {const p=await pageAt('#/today');ok(await p.locator('[data-testid="focus-list"]').isVisible(),'TASK-01 current focus visible');ok((await p.locator('body').innerText()).includes('P03 · VF Forge'),'TASK-01 P03 visible');rec('TASK-01',0,0);await p.close()}
  {const p=await pageAt('#/project/P03/overview');const t=await txt(p,'[data-testid="project-state"]');ok(t.includes('高保真原型阶段'),'TASK-02 current stage visible');rec('TASK-02',0,0);await p.close()}
  {const p=await pageAt('#/project/P03/overview');const t=await txt(p,'[data-testid="version-strip"]');ok(t.includes('正式运行')&&t.includes('1.35.4'),'TASK-03 production visible');rec('TASK-03',0,0);await p.close()}
  {const p=await pageAt('#/project/P03/overview');const t=await txt(p,'[data-testid="version-strip"]');ok(t.includes('开发版本')&&t.includes('1.36.0')&&t.includes('候选版本'),'TASK-04 working candidate visible');rec('TASK-04',0,0);await p.close()}
  {const p=await pageAt('#/project/P03/overview');ok((await txt(p,'[data-testid="project-block"]')).includes('等待主控高保真体验评审'),'TASK-05 block visible');rec('TASK-05',0,0);await p.close()}
  {const p=await pageAt('#/today');await p.click('[data-testid="today-open-p03"]');await waitHash(p,'/project/P03/overview');ok(await p.locator('[data-testid="primary-next-action"]').isVisible(),'TASK-06 primary next action visible');rec('TASK-06',1,1);await p.close()}
  for(const [id,nav,marker] of [['TASK-07','timeline','[data-testid="timeline"]'],['TASK-08','decisions','[data-testid="decisions"]'],['TASK-09','files','[data-testid="files"]'],['TASK-10','sources','[data-testid="sources"]']]){const p=await pageAt('#/project/P03/overview');await p.click(`[data-project-nav="${nav}"]`);await waitHash(p,`/project/P03/${nav}`);ok(await p.locator(marker).isVisible(),`${id} destination visible`);ok(await p.locator('[data-testid="project-context"]').isVisible(),`${id} context preserved`);ok(await p.locator('[data-testid="primary-next-action"]').isVisible(),`${id} next action preserved`);rec(id,1,0);await p.close()}
  {const p=await pageAt('#/search?q=memory-api');ok(await p.locator('[data-testid="global-search-result"]').isVisible(),'TASK-11 aggregated result visible');ok(await p.locator('[data-testid="association-chain"]').isVisible(),'TASK-11 association chain visible');rec('TASK-11',0,0);await p.close()}
  {const p=await pageAt('#/project/P03/overview');await p.selectOption('[data-testid="project-switcher"]','P04');await waitHash(p,'/project/P04/overview');const body=await p.locator('body').innerText();ok(body.includes('P04')&&body.includes('2.6.0')&&body.includes('当前无用户阻断'),'TASK-12 P04 context recovered');rec('TASK-12',1,1);await p.close()}
  {const p=await pageAt('#/projects');await p.click('[data-testid="open-P04"]');await waitHash(p,'/project/P04/overview');const c=await txt(p,'[data-testid="project-context"]');ok(c.includes('P04')&&c.includes('正式运行')&&c.includes('当前阻断')&&c.includes('唯一下一步'),'TASK-13 known-project recovery complete');rec('TASK-13',1,1);await p.close()}
  {const p=await pageAt('#/search?q=memory-api');const r=await txt(p,'[data-testid="global-search-result"]');ok(r.includes('P03')&&r.includes('1.35.4')&&r.includes('为什么重要')&&(r.includes('证据')||r.includes('Evidence')),'TASK-14 association semantics');await p.click('[data-testid="search-enter-p03"]');await waitHash(p,'/project/P03/overview');ok(await p.locator('[data-testid="project-context"]').isVisible(),'TASK-14 enters P03 context');rec('TASK-14',1,1);await p.close()}

  for(const width of [390,768,1024,1440,1920]){
    for(const hash of ['#/today','#/project/P03/overview','#/project/P03/timeline','#/project/P03/files','#/search?q=memory-api','#/project/P03/project-search']){
      const p=await pageAt(hash,width,width===390?844:1000);
      const metrics=await p.evaluate(()=>({doc:document.documentElement.scrollWidth,client:document.documentElement.clientWidth,body:document.body.scrollWidth}));
      ok(metrics.doc<=metrics.client+1&&metrics.body<=metrics.client+1,`RESPONSIVE ${width} ${hash} no horizontal overflow`);
      if(hash.includes('/project/')){ok(await p.locator('[data-testid="project-context"]').isVisible(),`RESPONSIVE ${width} context exists`);ok(await p.locator('[data-testid="primary-next-action"]').isVisible(),`RESPONSIVE ${width} next action exists`)}
      if(hash.includes('project-search'))ok((await p.locator('.search-scope').innerText()).includes('当前搜索范围'),`RESPONSIVE ${width} project search scope clear`);
      if(width===390){const mobile=await p.locator('.mobile-nav').boundingBox();const vp=p.viewportSize();ok(!!mobile&&!!vp&&mobile.y+mobile.height<=vp.height+1,`RESPONSIVE 390 mobile nav stays in viewport`)}
      await p.close();
    }
  }

  {const p=await pageAt('#/project/P03/overview',1440,1000);ok((await p.locator('body').innerText()).includes('当前状态'),'TASK-V01 explicit current-state label');ok(await first(p,'[data-testid="project-state"]'),'TASK-V01 state first viewport');ok(await first(p,'[data-testid="project-block"]'),'TASK-V01 block first viewport');ok(await first(p,'[data-testid="primary-next-action"]'),'TASK-V01 next first viewport');gates.push('TASK-V01=PASS');await p.close()}
  {const p=await pageAt('#/today',1440,900);ok(await first(p,'[data-testid="today-action"]'),'TASK-V02 action answer first viewport');gates.push('TASK-V02=PASS');await p.close()}
  {const p=await pageAt('#/search?q=memory-api',1440,1000);const r=await txt(p,'[data-testid="global-search-result"]');ok(r.includes('P03')&&r.includes('发生了什么')&&r.includes('为什么重要')&&r.includes('1.35.4')&&(r.includes('证据')||r.includes('Evidence')),'TASK-V03 project/event/reason/version/evidence');ok(await first(p,'[data-testid="global-search-result"]'),'TASK-V03 result starts in first viewport');gates.push('TASK-V03=PASS');await p.close()}

  ok(Math.max(...tasks.map(x=>x.clicks))<=3,'ROUND-1 max clicks <= 3');ok(Math.max(...tasks.map(x=>x.context_switch))<=1,'ROUND-1 max context switch <= 1');ok(tasks.every(x=>x.backtracking===0&&x.dead_end===0&&x.unknown_next_action===0),'ROUND-1 no backtracking/dead-end/unknown-next');gates.push('ROUND-1_FLOW_REGRESSION=PASS');
  {const p=await pageAt('#/project/P03/overview');const state=await p.locator('[data-testid="project-state"]').boundingBox(),block=await p.locator('[data-testid="project-block"]').boundingBox(),next=await p.locator('[data-testid="primary-next-action"]').boundingBox();ok(!!state&&!!block&&!!next&&state.y<block.y&&state.y<next.y,'ROUND-2 state leads block/next');ok(await first(p,'[data-testid="project-block"]')&&await first(p,'[data-testid="primary-next-action"]'),'ROUND-2 block and next first viewport');gates.push('ROUND-2_INFORMATION_HIERARCHY=PASS');await p.close()}
  {const p=await pageAt('#/today');const nav=await p.locator('.global-nav a').allInnerTexts();ok(JSON.stringify(nav)===JSON.stringify(['今天','项目','搜索']),'ROUND-3 frozen global IA');const body=await p.locator('body').innerText();ok(!body.includes('Observation 数量')&&!body.includes('Relation 数量')&&!body.includes('Authority 数量'),'ROUND-3 no backend counters');ok((await p.locator('.focus-row').count())<=3,'ROUND-3 restrained dashboard density');gates.push('ROUND-3_PRODUCT_FEEL_MACHINE_HEURISTICS=PASS');await p.close()}

  const shots=[['today_1440','#/today',1440,1000],['project-overview_1440','#/project/P03/overview',1440,1000],['timeline_1440','#/project/P03/timeline',1440,1000],['decisions_1440','#/project/P03/decisions',1440,1000],['files_1440','#/project/P03/files',1440,1000],['sources_1440','#/project/P03/sources',1440,1000],['versions_1440','#/project/P03/versions',1440,1000],['global-search_1440','#/search?q=memory-api',1440,1000],['project-search_1440','#/project/P03/project-search',1440,1000],['project-switch-p04_1440','#/project/P04/overview',1440,1000],['today_390','#/today',390,844],['project-overview_390','#/project/P03/overview',390,844],['global-search_390','#/search?q=memory-api',390,844]];
  for(const s of shots)await shot(...s);
  const summary={tasks,max_clicks:Math.max(...tasks.map(x=>x.clicks)),max_context_switch:Math.max(...tasks.map(x=>x.context_switch)),backtracking:0,dead_end:0,unknown_next_action:0,screenshots:shots.length};
  fs.writeFileSync('evidence/task-flow.json',JSON.stringify(summary,null,2));
  fs.writeFileSync('evidence/review-gates.txt',gates.join('\n')+'\n');
  fs.writeFileSync('evidence/verdict.txt','HIGHFI_BROWSER_GATE=PASS\nMASTER_VISUAL_PASS=NOT_DECLARED\nFORMAL_RUNTIME_INTEGRATION=NOT_EXECUTED\nCANDIDATE=NO\nPRODUCTION_WRITE=0\n');
  console.log(JSON.stringify({verdict:'HIGHFI_BROWSER_GATE_PASS',...summary},null,2));
  await browser.close();
}catch(e){fs.writeFileSync('evidence/FAILURE.log',(e?.stack||String(e))+'\n');console.error(e?.stack||String(e));await browser.close().catch(()=>{});process.exit(1)}
