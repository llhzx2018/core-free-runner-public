from pathlib import Path
import re

ROOT = Path('p05')

# Retire the physically duplicated Classic UI/runtime shortcuts.
for rel in [
    'src/client/App.tsx',
    'src/client/ProductWorkspaceShortcut.tsx',
    'src/client/DemoDatasetShortcut.tsx',
    'tests/unit/classic-keyword-trend-coverage.test.ts',
    'tests/unit/classic-nullable-metric-truth.test.ts',
    'tests/unit/classic-overview-loading.test.ts',
    'tests/unit/classic-truth-states.test.ts',
]:
    path = ROOT / rel
    if not path.exists():
        raise SystemExit(f'missing retirement target: {rel}')
    path.unlink()

# Common System remains maintenance-only. Online update has one canonical owner surface: UpdateShortcut.
common = ROOT / 'src/client/CommonSystemCenter.tsx'
text = common.read_text(encoding='utf-8')
text = text.replace("type SystemTab = 'info' | 'baseline' | 'update' | 'backup' | 'health' | 'brand' | 'data';", "type SystemTab = 'info' | 'baseline' | 'backup' | 'health' | 'brand' | 'data';")
text = re.sub(r"\nfunction updateChannelLabel\(value: unknown\): string \{.*?\n\}\n", "\n", text, count=1, flags=re.S)
text = text.replace("  const [update, setUpdate] = useState<Json | null>(null);\n", "")
text = text.replace("  const [stepUpPassword, setStepUpPassword] = useState('');\n", "")
text = text.replace("  const loadUpdate = async () => { try { setUpdate(await api('/api/system/update/status')); } catch (e) { fail(e); } };\n", "")
text = text.replace("    else if (next === 'update') void loadUpdate();\n", "")
text = re.sub(r"\n  const canApply = useMemo\(\(\) => Boolean\(update\?\.updateAvailable && update\?\.channel === 'OK'\), \[update\]\);", "", text, count=1)
text = re.sub(r"\n  const stepUp = async \(\) => \{.*?\n  \};\n  const saveBrand", "\n  const saveBrand", text, count=1, flags=re.S)
text = re.sub(r"\n  const applyUpdate = async \(\) => \{.*?\n  \};\n  const exportData", "\n  const exportData", text, count=1, flags=re.S)
text = text.replace("          <button className={tab === 'update' ? 'active' : ''} onClick={() => loadTab('update')}>在线升级</button>\n", "")
text = re.sub(r"\n        \{tab === 'update' && <div className=\\\"vf-common-section\\\">.*?\n        \}\n\n        \{tab === 'backup'", "\n\n        {tab === 'backup'", text, count=1, flags=re.S)
# If JSX quote escaping differs, fall back to literal source form.
if "tab === 'update'" in text:
    start = text.find("        {tab === 'update' && <div className=\"vf-common-section\">")
    end = text.find("        {tab === 'backup'", start)
    if start < 0 or end < 0:
        raise SystemExit('could not isolate duplicate update section')
    text = text[:start] + text[end:]

for forbidden in ["tab === 'update'", 'setUpdate(', 'stepUpPassword', 'applyUpdate', 'loadUpdate()', '>在线升级</button>']:
    if forbidden in text:
        raise SystemExit(f'duplicate update surface still present: {forbidden}')
common.write_text(text, encoding='utf-8')

# Phase-2 shell contract: Classic is physically retired.
shell = ROOT / 'tests/contract/single-product-shell.test.ts'
shell.write_text("""import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import test from 'node:test';

const main = readFileSync(new URL('../../src/client/main.tsx', import.meta.url), 'utf8');
const product = readFileSync(new URL('../../src/client/ProductApp.tsx', import.meta.url), 'utf8');
const common = readFileSync(new URL('../../src/client/CommonSystemCenter.tsx', import.meta.url), 'utf8');
const update = readFileSync(new URL('../../src/client/UpdateShortcut.tsx', import.meta.url), 'utf8');

test('ProductApp is the only runtime root workspace', () => {
  assert.ok(main.includes('<ProductApp />'));
  assert.equal(main.includes("from './App'"), false);
  assert.equal(main.includes('productPreview'), false);
  assert.equal(main.includes('ProductWorkspaceShortcut'), false);
  assert.equal(main.includes('DemoDatasetShortcut'), false);
});

test('Classic workspace and migration shortcuts are physically retired in phase 2', () => {
  for (const path of ['../../src/client/App.tsx', '../../src/client/ProductWorkspaceShortcut.tsx', '../../src/client/DemoDatasetShortcut.tsx']) {
    assert.equal(existsSync(new URL(path, import.meta.url)), false, `legacy runtime file still exists: ${path}`);
  }
});

test('formal Product shell contains no preview or classic-toggle copy', () => {
  assert.equal(product.includes('Product Optimization Preview'), false);
  assert.ok(product.includes('这里是 P05 唯一正式工作区'));
  assert.equal(main.includes('返回经典工作区'), false);
  assert.equal(main.includes('新版工作区 Preview'), false);
});

test('system maintenance and system update are separate canonical Global actions', () => {
  assert.ok(common.includes("document.querySelector('.p05v2-secondary')"));
  assert.ok(common.includes('>系统维护</button>'));
  assert.ok(update.includes("document.querySelector('.secondary-nav, .p05v2-secondary')"));
  assert.ok(update.includes('系统与更新'));
  assert.equal(common.includes(">在线升级</button>"), false);
  assert.equal(common.includes("tab === 'update'"), false);
  assert.equal(common.includes("/api/system/update/apply"), false);
});
""", encoding='utf-8')

# Common-system contract now describes maintenance only; UpdateShortcut is the sole update surface.
human = ROOT / 'tests/contract/common-system-human-ui.test.ts'
human.write_text("""import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const source = readFileSync(new URL('../../src/client/CommonSystemCenter.tsx', import.meta.url), 'utf8');
const update = readFileSync(new URL('../../src/client/UpdateShortcut.tsx', import.meta.url), 'utf8');

test('system maintenance exposes canonical maintenance entries without duplicating update', () => {
  for (const label of ['系统信息', '系统基线', '备份与恢复', '运行健康']) {
    assert.ok(source.includes(`>${label}</button>`), `missing canonical maintenance entry: ${label}`);
  }
  assert.equal(source.includes('>在线升级</button>'), false);
  assert.equal(source.includes("tab === 'update'"), false);
  assert.ok(update.includes('系统与更新'));
});

test('baseline UI still translates all 15 runtime domains including UPDATE state', () => {
  const labels = [
    '时间与时区', '登录与会话', '在线升级', '备份与恢复', '数据导入导出',
    '外部请求安全', '后台任务', '通知', '日志与脱敏', '页面状态',
    '文件上传', '运行健康', '版本与数据结构', '缓存', '语言与显示',
  ];
  for (const label of labels) assert.ok(source.includes(`label: '${label}'`), `missing domain label: ${label}`);
});

test('owner conclusion and attention appear before raw machine evidence', () => {
  assert.ok(source.includes('管理员结论'));
  assert.ok(source.includes('你需要关注'));
  assert.ok(source.includes('技术详情（给开发 / 排障使用）'));
  assert.ok(source.includes('<details className=\"vf-common-tech\">'));
});

test('machine states are translated without deleting underlying runtime evidence', () => {
  for (const label of ['正常', '有例外，需要注意', '需要处理', '暂时无法确认', '本项目不适用']) {
    assert.ok(source.includes(`label: '${label}'`));
  }
  assert.ok(source.includes('JSON.stringify(value ?? {}, null, 2)'));
  assert.ok(source.includes("api('/api/system/baseline')"));
});

test('common numeric values are formatted for human reading', () => {
  assert.ok(source.includes("[86400, '天']"));
  assert.ok(source.includes("const units = ['KB', 'MB', 'GB', 'TB']"));
  assert.ok(source.includes("if (value === true) return '是'"));
  assert.ok(source.includes("if (value === false) return '否'"));
});
""", encoding='utf-8')

# Machine-readable owner capability parity map.
parity = ROOT / 'tests/contract/single-product-parity.test.ts'
parity.write_text("""import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const app = readFileSync(new URL('../../src/client/ProductApp.tsx', import.meta.url), 'utf8');
const views = readFileSync(new URL('../../src/client/ProductSiteViews.tsx', import.meta.url), 'utf8');
const changes = readFileSync(new URL('../../src/client/ProductChangesWorkspace.tsx', import.meta.url), 'utf8');
const common = readFileSync(new URL('../../src/client/CommonSystemCenter.tsx', import.meta.url), 'utf8');
const update = readFileSync(new URL('../../src/client/UpdateShortcut.tsx', import.meta.url), 'utf8');

test('all former Classic SEO capabilities have canonical Product destinations', () => {
  const labels = ['Site Portfolio', '概览', '网站检查', '关键词', '页面', 'AI / AEO', '变更', '设置', '全局搜索'];
  for (const label of labels) assert.ok(app.includes(label) || views.includes(label) || changes.includes(label), `missing canonical Product capability: ${label}`);
  assert.ok(app.includes("{ key: 'Search', label: '搜索表现'"));
  assert.ok(app.includes("{ key: 'DataSources', label: '数据源'"));
  assert.ok(app.includes("{ key: 'Opportunities', label: '机会'"));
});

test('former Classic global maintenance capabilities have one canonical destination each', () => {
  assert.ok(common.includes('>备份与恢复</button>'));
  assert.ok(common.includes('>运行健康</button>'));
  assert.ok(common.includes('>系统信息</button>'));
  assert.ok(update.includes('系统与更新'));
  assert.equal(common.includes('>在线升级</button>'), false);
});

test('Demo Dataset and authentication are owned by the canonical Product shell', () => {
  assert.ok(app.includes('DEMO_DATASET_AUTHORITY'));
  assert.ok(app.includes("api('/api/system/demo-dataset')"));
  assert.ok(app.includes("api('/api/auth/me')"));
  assert.ok(app.includes("api('/api/auth/logout'"));
});

test('Product errors remain explicit instead of silently becoming empty truth', () => {
  assert.ok(app.includes("setError(String((e as Error).message))"));
  assert.ok(app.includes('{error && <div className=\"p05v2-error\">{error}</div>}'));
  assert.ok(changes.includes(".catch(err => { if (alive) setError(String((err as Error).message)); });"));
  assert.ok(changes.includes('if (error) return <div className=\"p05v2-error\">{error}</div>;'));
  assert.ok(views.includes('Runtime capability 读取失败：{runtimeError}'));
  assert.ok(common.includes("const loadBackups = async () => { try { setBackups(await api('/api/backups')); } catch (e) { fail(e); } };"));
  assert.ok(common.includes("const loadHealth = async () => { try { setHealth(await api('/api/system/health')); } catch (e) { fail(e); } };"));
  assert.ok(common.includes('{error && <p className=\"vf-common-error\">{error}</p>}'));
});

test('missing Product observations stay unknown instead of coercing to zero', () => {
  assert.ok(app.includes("function numberOrNull(value: unknown): number | null { if (value === null || value === undefined || value === '') return null;"));
  assert.ok(app.includes("return n == null ? '—'"));
  assert.ok(views.includes("function num(value: unknown): number | null { if (value === null || value === undefined || value === '') return null;"));
  assert.ok(views.includes("return n == null ? '—'"));
  assert.ok(changes.includes("function num(value: unknown): number | null { if (value === null || value === undefined || value === '') return null;"));
});
""", encoding='utf-8')

print('P05_SINGLE_PRODUCT_PHASE2_WRITER=PASS')
