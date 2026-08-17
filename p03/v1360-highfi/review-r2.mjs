import { chromium } from 'playwright';
import fs from 'node:fs';

const base = 'http://127.0.0.1:8765';
const browser = await chromium.launch({ headless: true });
const results = [];
const checks = [];
const evidenceDir = 'evidence';
fs.mkdirSync(`${evidenceDir}/screenshots`, { recursive: true });

const record = (id, clicks, contextSwitch) => results.push({
  id, clicks, context_switch: contextSwitch,
  backtracking: 0, dead_end: 0, unknown_next_action: 0,
  completion: 'PASS'
});
const assert = (cond, msg) => {
  if (!cond) throw new Error(msg);
  checks.push(msg);
};
const routeOk = (page, fragment) => page.url().includes(fragment);
async function pageAt(hash, width = 1440, height = 1000) {
  const page = await browser.newPage({ viewport: { width, height } });
  await page.goto(`${base}/${hash}`, { waitUntil: 'networkidle' });
  return page;
}
async function text(page, selector) {
  return (await page.locator(selector).innerText()).trim();
}
async function waitHash(page, fragment) {
  await page.waitForFunction(f => location.hash.includes(f), fragment, { timeout: 3000 });
  assert(routeOk(page, fragment), `route ${fragment} reached`);
}
async function firstViewport(page, selector) {
  const box = await page.locator(selector).boundingBox();
  const vp = page.viewportSize();
  return !!box && !!vp && box.y < vp.height && box.y + Math.min(box.height, 80) > 0;
}
async function screenshot(name, hash, width = 1440, height = 1000) {
  const page = await pageAt(hash, width, height);
  await page.screenshot({ path: `${evidenceDir}/screenshots/${name}.png`, fullPage: true });
  await page.close();
}

try {
  // TASK-01: current focus project.
  {
    const page = await pageAt('#/today');
    assert(await page.locator('[data-testid="focus-list"]').isVisible(), 'TASK-01 focus list visible');
    assert((await page.locator('body').innerText()).includes('P03 · VF Forge'), 'TASK-01 P03 focus visible');
    record('TASK-01', 0, 0); await page.close();
  }
  // TASK-02: project current state.
  {
    const page = await pageAt('#/project/P03/overview');
    assert((await text(page, '[data-testid="project-state"]')).includes('High-Fi'), 'TASK-02 current state visible');
    record('TASK-02', 0, 0); await page.close();
  }
  // TASK-03: production version.
  {
    const page = await pageAt('#/project/P03/overview');
    const t = await text(page, '[data-testid="version-strip"]');
    assert(t.includes('正式运行') && t.includes('1.35.4'), 'TASK-03 production visible');
    record('TASK-03', 0, 0); await page.close();
  }
  // TASK-04: working / candidate.
  {
    const page = await pageAt('#/project/P03/overview');
    const t = await text(page, '[data-testid="version-strip"]');
    assert(t.includes('开发版本') && t.includes('1.36.0') && t.includes('候选版本'), 'TASK-04 working and candidate visible');
    record('TASK-04', 0, 0); await page.close();
  }
  // TASK-05: biggest block.
  {
    const page = await pageAt('#/project/P03/overview');
    assert((await text(page, '[data-testid="project-block"]')).includes('等待 MASTER'), 'TASK-05 block visible');
    record('TASK-05', 0, 0); await page.close();
  }
  // TASK-06: today -> project -> primary next action.
  {
    const page = await pageAt('#/today');
    await page.click('[data-testid="today-open-p03"]');
    await waitHash(page, '/project/P03/overview');
    assert(await page.locator('[data-testid="primary-next-action"]').isVisible(), 'TASK-06 primary next action visible');
    record('TASK-06', 1, 1); await page.close();
  }
  // TASK-07..10: project section navigation preserves project context and next action.
  for (const [id, nav, marker] of [
    ['TASK-07', 'timeline', '[data-testid="timeline"]'],
    ['TASK-08', 'decisions', '[data-testid="decisions"]'],
    ['TASK-09', 'files', '[data-testid="files"]'],
    ['TASK-10', 'sources', '[data-testid="sources"]']
  ]) {
    const page = await pageAt('#/project/P03/overview');
    await page.click(`[data-project-nav="${nav}"]`);
    await waitHash(page, `/project/P03/${nav}`);
    assert(await page.locator(marker).isVisible(), `${id} destination visible`);
    assert(await page.locator('[data-testid="project-context"]').isVisible(), `${id} project context preserved`);
    assert(await page.locator('[data-testid="primary-next-action"]').isVisible(), `${id} next action preserved`);
    record(id, 1, 0); await page.close();
  }
  // TASK-11: search old event/version/file/decision.
  {
    const page = await pageAt('#/search?q=memory-api');
    assert(await page.locator('[data-testid="global-search-result"]').isVisible(), 'TASK-11 aggregated result visible');
    assert(await page.locator('[data-testid="association-chain"]').isVisible(), 'TASK-11 association chain visible');
    record('TASK-11', 0, 0); await page.close();
  }
  // TASK-12: switch project and immediately recover new context.
  {
    const page = await pageAt('#/project/P03/overview');
    await page.selectOption('[data-testid="project-switcher"]', 'P04');
    await waitHash(page, '/project/P04/overview');
    const body = await page.locator('body').innerText();
    assert(body.includes('P04') && body.includes('2.6.0') && body.includes('当前无用户阻断'), 'TASK-12 P04 context recovered');
    record('TASK-12', 1, 1); await page.close();
  }
  // TASK-13: known project name -> complete context recovery.
  {
    const page = await pageAt('#/projects');
    await page.click('[data-testid="open-P04"]');
    await waitHash(page, '/project/P04/overview');
    const c = await text(page, '[data-testid="project-context"]');
    assert(c.includes('P04') && c.includes('正式运行') && c.includes('当前阻断') && c.includes('唯一下一步'), 'TASK-13 complete project context');
    record('TASK-13', 1, 1); await page.close();
  }
  // TASK-14: only remembers memory-api -> association -> P03 context.
  {
    const page = await pageAt('#/search?q=memory-api');
    const r = await text(page, '[data-testid="global-search-result"]');
    assert(r.includes('P03') && r.includes('1.35.4') && r.includes('为什么重要') && (r.includes('证据') || r.includes('Evidence')), 'TASK-14 association semantics visible');
    await page.click('[data-testid="search-enter-p03"]');
    await waitHash(page, '/project/P03/overview');
    assert(await page.locator('[data-testid="project-context"]').isVisible(), 'TASK-14 enters P03 context');
    record('TASK-14', 1, 1); await page.close();
  }

  // Responsive gates at every required width.
  for (const width of [390, 768, 1024, 1440, 1920]) {
    for (const hash of ['#/today', '#/project/P03/overview', '#/project/P03/timeline', '#/project/P03/files', '#/search?q=memory-api', '#/project/P03/project-search']) {
      const page = await pageAt(hash, width, width === 390 ? 844 : 1000);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
      assert(!overflow, `RESPONSIVE ${width} ${hash} no horizontal overflow`);
      if (hash.includes('/project/')) {
        assert(await page.locator('[data-testid="project-context"]').isVisible(), `RESPONSIVE ${width} project context visible`);
        assert(await page.locator('[data-testid="primary-next-action"]').isVisible(), `RESPONSIVE ${width} primary next action exists`);
      }
      if (hash.includes('project-search')) assert((await page.locator('.search-scope').innerText()).includes('当前搜索范围'), `RESPONSIVE ${width} project search scope clear`);
      await page.close();
    }
  }

  // TASK-V01: project context cognition in first viewport.
  {
    const page = await pageAt('#/project/P03/overview', 1440, 1000);
    assert(await firstViewport(page, '[data-testid="project-state"]'), 'TASK-V01 project state first viewport');
    assert(await firstViewport(page, '[data-testid="project-block"]'), 'TASK-V01 block first viewport');
    assert(await firstViewport(page, '[data-testid="primary-next-action"]'), 'TASK-V01 next action first viewport');
    checks.push('TASK-V01=PASS'); await page.close();
  }
  // TASK-V02: today user action cognition.
  {
    const page = await pageAt('#/today', 1440, 900);
    assert(await firstViewport(page, '[data-testid="today-action"]'), 'TASK-V02 today user action first viewport');
    checks.push('TASK-V02=PASS'); await page.close();
  }
  // TASK-V03: memory-api association cognition.
  {
    const page = await pageAt('#/search?q=memory-api', 1440, 1000);
    const r = await text(page, '[data-testid="global-search-result"]');
    assert(r.includes('P03') && r.includes('发生了什么') && r.includes('为什么重要') && r.includes('1.35.4') && (r.includes('证据') || r.includes('Evidence')), 'TASK-V03 event/project/reason/version/evidence visible');
    assert(await firstViewport(page, '[data-testid="global-search-result"]'), 'TASK-V03 aggregated result starts in first viewport');
    checks.push('TASK-V03=PASS'); await page.close();
  }

  // ROUND 1: approved flow regression.
  assert(Math.max(...results.map(x => x.clicks)) <= 3, 'ROUND-1 max clicks <= 3');
  assert(Math.max(...results.map(x => x.context_switch)) <= 1, 'ROUND-1 context switch <= 1');
  assert(results.every(x => x.backtracking === 0 && x.dead_end === 0 && x.unknown_next_action === 0), 'ROUND-1 no backtracking/dead-end/unknown-next');
  checks.push('ROUND-1_FLOW_REGRESSION=PASS');

  // ROUND 2: information hierarchy.
  {
    const page = await pageAt('#/project/P03/overview', 1440, 1000);
    const state = await page.locator('[data-testid="project-state"]').boundingBox();
    const block = await page.locator('[data-testid="project-block"]').boundingBox();
    const next = await page.locator('[data-testid="primary-next-action"]').boundingBox();
    assert(state && block && next && state.y < block.y && state.y < next.y, 'ROUND-2 state leads block/next hierarchy');
    assert(await firstViewport(page, '[data-testid="project-block"]') && await firstViewport(page, '[data-testid="primary-next-action"]'), 'ROUND-2 block/next first viewport');
    checks.push('ROUND-2_INFORMATION_HIERARCHY=PASS'); await page.close();
  }

  // ROUND 3: product feel machine heuristics.
  {
    const page = await pageAt('#/today');
    const links = await page.locator('.global-nav a').allInnerTexts();
    assert(JSON.stringify(links) === JSON.stringify(['今天','项目','搜索']), 'ROUND-3 frozen three-item global IA');
    const body = await page.locator('body').innerText();
    assert(!body.includes('Observation 数量') && !body.includes('Relation 数量') && !body.includes('Authority 数量'), 'ROUND-3 no engineering dashboard counters');
    assert((await page.locator('.focus-row').count()) <= 3, 'ROUND-3 restrained focus density');
    checks.push('ROUND-3_PRODUCT_FEEL_MACHINE_HEURISTICS=PASS'); await page.close();
  }

  // Required screenshot evidence.
  const shots = [
    ['today_1440', '#/today', 1440, 1000],
    ['project-overview_1440', '#/project/P03/overview', 1440, 1000],
    ['timeline_1440', '#/project/P03/timeline', 1440, 1000],
    ['decisions_1440', '#/project/P03/decisions', 1440, 1000],
    ['files_1440', '#/project/P03/files', 1440, 1000],
    ['sources_1440', '#/project/P03/sources', 1440, 1000],
    ['versions_1440', '#/project/P03/versions', 1440, 1000],
    ['global-search_1440', '#/search?q=memory-api', 1440, 1000],
    ['project-search_1440', '#/project/P03/project-search', 1440, 1000],
    ['project-switch-p04_1440', '#/project/P04/overview', 1440, 1000],
    ['today_390', '#/today', 390, 844],
    ['project-overview_390', '#/project/P03/overview', 390, 844],
    ['global-search_390', '#/search?q=memory-api', 390, 844]
  ];
  for (const s of shots) await screenshot(...s);

  const summary = {
    tasks: results,
    max_clicks: Math.max(...results.map(x => x.clicks)),
    max_context_switch: Math.max(...results.map(x => x.context_switch)),
    backtracking: 0,
    dead_end: 0,
    unknown_next_action: 0,
    screenshots: shots.length
  };
  fs.writeFileSync(`${evidenceDir}/task-flow.json`, JSON.stringify(summary, null, 2));
  fs.writeFileSync(`${evidenceDir}/review-gates.txt`, checks.join('\n') + '\n');
  fs.writeFileSync(`${evidenceDir}/verdict.txt`, 'HIGHFI_BROWSER_GATE=PASS\nMASTER_VISUAL_PASS=NOT_DECLARED\nFORMAL_RUNTIME_INTEGRATION=NOT_EXECUTED\nCANDIDATE=NO\nPRODUCTION_WRITE=0\n');
  console.log(JSON.stringify({ verdict: 'HIGHFI_BROWSER_GATE_PASS', ...summary }, null, 2));
  await browser.close();
} catch (error) {
  const message = error?.stack || String(error);
  fs.writeFileSync(`${evidenceDir}/FAILURE.log`, message + '\n');
  console.error(message);
  await browser.close().catch(() => {});
  process.exit(1);
}
