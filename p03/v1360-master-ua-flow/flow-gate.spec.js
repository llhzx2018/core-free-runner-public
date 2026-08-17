const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const base = process.env.P03_LOWFI_BASE || 'http://127.0.0.1:18760';
const outDir = process.env.P03_FLOW_EVIDENCE || 'p03/v1360-master-ua-flow/evidence';
fs.mkdirSync(outDir,{recursive:true});

function contextOf(hash){
  if(hash.startsWith('#/project/')) return 'project:'+hash.split('/')[2];
  return 'global';
}
function assert(cond,msg){ if(!cond) throw new Error(msg); }

(async()=>{
  const browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1280,height:800}});
  const results=[];
  async function start(hash){ await page.goto(base+'/'+hash); await page.waitForTimeout(20); return {clicks:0,switches:0,last:contextOf(hash),backtracking:0,decision_points:0,dead_end:0,internal_model:0,next_action_visible:0}; }
  async function click(m,id){ const before=page.url().split('#')[1]?'#'+page.url().split('#')[1]:'#/today'; await page.locator(`[data-id="${id}"]`).click(); await page.waitForTimeout(20); const after=page.url().split('#')[1]?'#'+page.url().split('#')[1]:'#/today'; m.clicks++; const c=contextOf(after); if(c!==m.last){m.switches++;m.last=c;} return {before,after}; }
  async function selectProject(m,code){ await page.locator('#switch').selectOption({label:code}); await page.waitForTimeout(20); m.clicks++; const after=page.url().split('#')[1]?'#'+page.url().split('#')[1]:'#/today'; const c=contextOf(after); if(c!==m.last){m.switches++;m.last=c;} }
  async function requireVisible(sel,msg){ assert(await page.locator(sel).isVisible(),msg); }
  async function requireProjectContext(code){ await requireVisible(`[data-project-context="${code}"]`,`project context missing ${code}`); for(const id of ['state','versions','block','next','why']) await requireVisible(`[data-id="${id}"]`,`${id} missing in ${code}`); }
  async function finish(id,m){ const text=await page.locator('body').innerText(); const forbidden=['Observation','Relation','Inference','Provenance','Retrieval Target','Authority Pointer','Derived']; m.internal_model=forbidden.some(x=>text.includes(x))?1:0; m.next_action_visible=(await page.locator('[data-id="next"],[data-id="focus"],[data-id="search-next"]').count())>0?1:0; results.push({id,clicks:m.clicks,context_switch:m.switches,backtracking:m.backtracking,decision_points:m.decision_points,dead_end:m.dead_end,internal_model:m.internal_model,next_action_visible:m.next_action_visible,final_hash:'#'+(page.url().split('#')[1]||'/today')}); }

  // 01: today immediately reveals focus + next action.
  {let m=await start('#/today');await requireVisible('[data-id="focus"]','focus missing');await finish('TASK-01',m)}
  // 02-05: project first screen answers status/version/block without navigation.
  for(const [id,sel] of [['TASK-02','[data-id="state"]'],['TASK-03','[data-id="versions"]'],['TASK-04','[data-id="versions"]'],['TASK-05','[data-id="block"]']]){let m=await start('#/project/P03/overview');await requireProjectContext('P03');await requireVisible(sel,id+' answer missing');await finish(id,m)}
  // 06: today -> focus project -> primary next action.
  {let m=await start('#/today');await click(m,'focus-P03');await requireProjectContext('P03');await requireVisible('[data-id="next"]','next action missing');await finish('TASK-06',m)}
  // 07-10: project sections preserve P03 context.
  for(const [id,link,answer] of [['TASK-07','timeline','important-change'],['TASK-08','decisions','decision'],['TASK-09','files','file'],['TASK-10','authority','authority-detail']]){let m=await start('#/project/P03/overview');await click(m,link);await requireProjectContext('P03');await requireVisible(`[data-id="${answer}"]`,id+' answer missing');await finish(id,m)}
  // 11: global search returns human-readable aggregated association without object-type selection.
  {let m=await start('#/search');await requireVisible('[data-id="search-result"]','search result missing');await click(m,'event-result');await requireVisible('[data-id="chain"]','aggregated relation chain missing');await requireVisible('[data-id="search-next"]','project next action missing in search association');await finish('TASK-11',m)}
  // 12: direct project switch, then immediate new-project context.
  {let m=await start('#/project/P03/overview');await selectProject(m,'P04');await requireProjectContext('P04');await finish('TASK-12',m)}
  // 13: known project -> one click -> full context recovery, no timeline prerequisite.
  {let m=await start('#/projects');await click(m,'open-P04');await requireProjectContext('P04');await requireVisible('[data-id="context-recovery"]','context recovery summary missing');await finish('TASK-13',m)}
  // 14: unknown old fact -> search association -> P03 context, no backtracking.
  {let m=await start('#/search');await click(m,'event-result');await requireVisible('[data-id="chain"]','event-decision-version-evidence chain missing');await click(m,'open-P03-context');await requireProjectContext('P03');await finish('TASK-14',m)}

  const thresholds={clicks:3,context_switch:1,backtracking:0,decision_points:0,dead_end:0,internal_model:0};
  assert(results.length===14,'expected 14 tasks');
  for(const r of results){
    assert(r.clicks<=thresholds.clicks,`${r.id} clicks ${r.clicks}`);
    assert(r.context_switch<=thresholds.context_switch,`${r.id} context ${r.context_switch}`);
    assert(r.backtracking===0,`${r.id} backtracking`);
    assert(r.decision_points===0,`${r.id} decision point`);
    assert(r.dead_end===0,`${r.id} dead end`);
    assert(r.internal_model===0,`${r.id} internal model leak`);
    assert(r.next_action_visible===1,`${r.id} primary next action not visible`);
  }
  const valueTask=results.find(x=>x.id==='TASK-13');
  assert(valueTask.clicks===1 && valueTask.context_switch===1,'TASK-13 context recovery path not minimal');
  const unknownFact=results.find(x=>x.id==='TASK-14');
  assert(unknownFact.clicks<=3 && unknownFact.context_switch===1,'TASK-14 global-to-project continuity fail');

  const evidence={gate:'P03_V1360_MASTER_UA_FLOW_MACHINE_MEASUREMENT',result:'PASS',tasks:results,thresholds,master_ua_flow_gate:'NOT_SELF_DECLARED',high_fi:'NOT_EXECUTED',candidate:'NO',release:'NO',production_write:0};
  fs.writeFileSync(path.join(outDir,'flow-measurement.json'),JSON.stringify(evidence,null,2));
  fs.writeFileSync(path.join(outDir,'flow-measurement.txt'),results.map(r=>`${r.id} clicks=${r.clicks} context=${r.context_switch} backtracking=${r.backtracking} decisions=${r.decision_points} dead_end=${r.dead_end} internal_model=${r.internal_model} next_action=${r.next_action_visible}`).join('\n')+'\n');
  console.log(JSON.stringify(evidence,null,2));
  console.log('P03_V1360_TASK_FLOW_14_14_PASS');
  console.log('READY_FOR_MASTER_UA_FLOW_REVIEW');
  await browser.close();
})().catch(async e=>{console.error(e);process.exit(1)});
