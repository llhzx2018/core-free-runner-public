#!/usr/bin/env python3
from pathlib import Path
import json,hashlib,sys
root=Path(sys.argv[1] if len(sys.argv)>1 else 'p02')
app=root/'public/assets/app.js'
s=app.read_text(encoding='utf-8')
if 'async function refreshNavigationMetadata()' not in s:
    marker='async function loadBootstrap(options){'
    helper="""async function refreshNavigationMetadata(){\n  if(!state.site||!state.site.auth)return false;\n  try{\n    const response=await api('app_bootstrap',{progress:false});\n    state.categories=response.data.categories||[];\n    state.stats=response.data.stats||{};\n    renderSidebar();\n    return true;\n  }catch(error){\n    console.warn('VF Library navigation metadata refresh failed',error);\n    return false;\n  }\n}\n"""
    assert marker in s
    s=s.replace(marker,helper+marker,1)
    g="const saved=rememberItem(response.item||Object.assign({},item||{},d,{id:response.id,updated_at:new Date().toISOString()}));"
    assert s.count(g)==1
    s=s.replace(g,g+'\n      await refreshNavigationMetadata();',1)
    a="const fresh=rememberItem(saved.item||Object.assign({},item,d,{tags:articleTagList(d.tags),aliases:articleTagList(d.aliases),updated_at:new Date().toISOString()}));item=fresh;"
    assert s.count(a)==1
    s=s.replace(a,a.replace(';item=fresh;',';await refreshNavigationMetadata();item=fresh;'),1)
    app.write_text(s,encoding='utf-8')

e2e=root/'tests/e2e/maintenance_reverify.mjs'
t=e2e.read_text(encoding='utf-8').replace("session?.version !== '2.4.23'","session?.version !== '2.4.24'")
anchor="  const marker = 'BROWSER_E2E_' + Date.now();\n"
if 'LIVE_COUNT_' not in t:
    assert anchor in t
    block=r'''  const liveCountTitle = 'LIVE_COUNT_' + Date.now();
  const categoryCount = async () => page.evaluate(id => {
    const node = document.querySelector(`[data-category-row="${id}"] .side-count`);
    if (!node) return null;
    const value = Number((node.textContent || '').trim());
    return Number.isFinite(value) ? value : null;
  }, categoryId);
  const beforeLiveCount = await categoryCount();
  if (!Number.isInteger(beforeLiveCount)) throw new Error('live category count baseline missing');
  await page.evaluate(() => openEditor(null, { forceContentMode: 'quick', forceContentFormat: 'plain' }));
  await page.locator('#contentForm').waitFor({ state: 'visible' });
  await page.locator('#contentForm [name="title"]').fill(liveCountTitle);
  await page.locator('#contentForm [name="category_id"]').selectOption(String(categoryId));
  await page.locator('#contentForm [name="content"]').fill('live category count regression');
  await page.locator('#saveContent').click();
  await page.waitForFunction(({ id, expected }) => {
    const node = document.querySelector(`[data-category-row="${id}"] .side-count`);
    return node && Number((node.textContent || '').trim()) === expected;
  }, { id: categoryId, expected: beforeLiveCount + 1 }, { timeout: 10000 });
  const liveCountId = await page.evaluate(() => Number(state.editorItem?.id || 0));
  if (!liveCountId) throw new Error('live category count created item id missing');
  await page.locator('#editorMoreButton').click();
  await page.locator('[data-editor-action="trash"]').click();
  await page.locator('[data-dialog-confirm]').click();
  await page.waitForFunction(({ id, expected }) => {
    const node = document.querySelector(`[data-category-row="${id}"] .side-count`);
    return node && Number((node.textContent || '').trim()) === expected;
  }, { id: categoryId, expected: beforeLiveCount }, { timeout: 10000 });
  const restoreLiveCount = await post('content_restore', { id: liveCountId });
  if (!restoreLiveCount.json?.ok) throw new Error('live category count restore cleanup failed');
  await page.evaluate(async () => { await loadBootstrap({ view: viewSnapshot() }); });
  await page.waitForFunction(({ id, expected }) => {
    const node = document.querySelector(`[data-category-row="${id}"] .side-count`);
    return node && Number((node.textContent || '').trim()) === expected;
  }, { id: categoryId, expected: beforeLiveCount + 1 }, { timeout: 10000 });
'''
    t=t.replace(anchor,block+anchor,1)
e2e.write_text(t,encoding='utf-8')

m=root/'scripts/maintenance-reverify.sh'
m.write_text(m.read_text(encoding='utf-8').replace('2.4.23','2.4.24'),encoding='utf-8')

b=root/'scripts/build-release.py'
x=b.read_text(encoding='utf-8')
x=x.replace("SRCVER='2.4.22'; VER='2.4.23'; SCHEMA=2401; DT=(2026,8,15,0,0,0)","SRCVER='2.4.23'; VER='2.4.24'; SCHEMA=2401; DT=(2026,8,15,14,40,0)")
x=x.replace("notes.write_text(f'# VF Library V{VER}\\n\\nUpdate Core V1 integration release. Schema remains {SCHEMA}. Existing 2.4.22 sites use the formal UPDATE package; FULL is clean install only.\\n')","notes.write_text(f'# VF Library V{VER}\\n\\nMaintenance bugfix: category/sidebar counts refresh immediately after content save; trash/restore behavior is regression-verified. Schema remains {SCHEMA}. Existing {SRCVER} sites use the formal UPDATE package; FULL is clean install only.\\n')")
b.write_text(x,encoding='utf-8')

v=root/'scripts/verify-release-artifacts.sh'
x=v.read_text(encoding='utf-8')
x=x.replace('VF_RELEASE_OLD_COMMIT:-17f2d3256dbe6d47c141b01e11e1d95c4ac92720','VF_RELEASE_OLD_COMMIT:-333d4fd52150f1c15e9911bce312bb2b6775f856')
x=x.replace('release/2.4.23','release/2.4.24')
x=x.replace('repair-v2.4.23.php','repair-v2.4.24.php')
x=x.replace("ver='2.4.23'","ver='2.4.24'")
x=x.replace("m['source_version']=='2.4.22' and m['target_version']==ver","m['source_version']=='2.4.23' and m['target_version']==ver")
x=x.replace('VF_Library_V2.4.23_FULL.zip','VF_Library_V2.4.24_FULL.zip')
x=x.replace('== 2.4.23','== 2.4.24')
x=x.replace('2.4.22 -> 2.4.23','2.4.23 -> 2.4.24')
x=x.replace("out/'VF_Library_V2.4.23_RELEASE_MANIFEST.json'","out/'VF_Library_V2.4.24_RELEASE_MANIFEST.json'")
x=x.replace('VF LIBRARY V2.4.23 FORMAL ARTIFACT GATES PASS','VF LIBRARY V2.4.24 FORMAL ARTIFACT GATES PASS')
v.write_text(x,encoding='utf-8')

(root/'VERSION').write_text('2.4.24\n',encoding='utf-8')

readme=root/'README.md'; r=readme.read_text(encoding='utf-8')
r=r.replace('正式生产版本：`2.4.22`','正式生产版本：`2.4.23`')
r=r.replace('没有真实新 Bug 或批准的新需求，不开启 `2.4.23`。','当前已确认“内容新增后分类计数不实时刷新”真实 Bug，V2.4.24 为维护修复 Candidate。')
r=r.replace('当前下一步：`STOP`','当前下一步：`验证 V2.4.24 分类计数实时刷新修复并完成正式在线更新`')
readme.write_text(r,encoding='utf-8')

ch=root/'CHANGELOG.md'; c=ch.read_text(encoding='utf-8')
entry='''# VF Library V2.4.24\n\n- 修复文章/便签新增或保存后，左侧分类数量不会立即更新、必须刷新页面才同步的问题。\n- 保存完成后仅刷新导航分类与统计元数据，不重载当前编辑工作区。\n- 回归验证移入回收站后分类计数立即减少，恢复后立即增加。\n- Schema 保持 2401。\n\n'''
if not c.startswith('# VF Library V2.4.24'): c=entry+c
ch.write_text(c,encoding='utf-8')

proj=json.loads((root/'VF_PROJECT.json').read_text(encoding='utf-8'))
proj.update(status='MAINTENANCE_BUGFIX_CANDIDATE_IN_VERIFICATION',lifecycle='STABLE_OPERATIONS_WITH_APPROVED_CHANGE',production_version='2.4.23',working_version='2.4.24',candidate_version='2.4.24',task_branch='task/v2.4.24-live-category-counts',current_phase='MAINTENANCE_BUGFIX_CANDIDATE_VERIFICATION',deployment_status='PRODUCTION_V2.4.23_UNCHANGED',main_alignment_status='PRODUCTION_V2.4.23_CURRENT',final_online_pass=False,product_failure='LIVE_CATEGORY_COUNT_REFRESH_BUG_CONFIRMED_FIX_IN_VERIFICATION',project_block='NONE')
proj['block']=[]
proj.setdefault('source_baseline',{})['production_commit']='333d4fd52150f1c15e9911bce312bb2b6775f856'
proj['candidate_source']={'branch':'task/v2.4.24-live-category-counts','version':'2.4.24','schema':2401,'scope':'LIVE_CATEGORY_COUNT_REFRESH_BUGFIX','runtime_regression':'PENDING','formal_candidate_reverse_verification':'PENDING'}
proj['approved_change']={'id':'P02-BUGFIX-LIVE-CATEGORY-COUNTS','status':'APPROVED_IN_PROGRESS','summary':'修复文章/便签新增或保存后分类数量不实时刷新，并回归锁定删除/恢复计数同步。','version_rationale':'真实 Production Bug 的维护修复，因此使用 V2.4.24。','schema_change':False,'ui_rebuild':False}
if isinstance(proj.get('update_core_integration'),dict): proj['update_core_integration']['production_read_secret_name']='VF_PRIVATE_READ_TOKEN'
proj['evidence_gap']=['V2.4.24 browser regression must prove create +1 / trash -1 / restore +1 without page refresh','Formal V2.4.23 -> V2.4.24 UPDATE asset must pass reverse verification before release']
proj['next_action']='Run full maintenance regression and formal artifact reverse verification for V2.4.24; if PASS, merge to develop and publish formal online update.'
(root/'VF_PROJECT.json').write_text(json.dumps(proj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

mp=root/'SOURCE_MANIFEST.json'; current=json.loads(mp.read_text(encoding='utf-8')); entries=[]
for e in current['entries']:
    p=root/e['repo_path']; assert p.is_file() and not p.is_symlink(),e['repo_path']
    data=p.read_bytes(); h=hashlib.sha256(data).hexdigest()
    entries.append({'full_path':e['full_path'],'repo_path':e['repo_path'],'bytes':len(data),'sha256':h,'repo_sha256':h})
entries.sort(key=lambda z:z['full_path']); current['version']='2.4.24'; current['schema']=2401; current['runtime_source_file_count']=len(entries); current['entries']=entries
mp.write_text(json.dumps(current,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
mt=root/'SOURCE_MANIFEST.txt'; lines=['VF Library V2.4.24 CANDIDATE SOURCE_MANIFEST','FULL_SHA256  PENDING_FORMAL_RELEASE',f'RUNTIME_SOURCE_FILES  {len(entries)}','MAPPING_STATUS  CURRENT_GIT_CANDIDATE','']+[f"{e['sha256']}  {e['repo_path']}  <=  {e['full_path']}" for e in entries]
mt.write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('P02_V2424_PATCH_PREPARED')
