from pathlib import Path
import sys

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.')
app = root / 'public/assets/app.js'
text = app.read_text(encoding='utf-8')

new_nav = "function settingsNav(){return [{id:'basic',group:'日常偏好',label:'基础设置',desc:'品牌、主题与常用偏好'},{id:'content',group:'日常偏好',label:'内容与分类',desc:'目录和内容规则'},{id:'display',group:'日常偏好',label:'显示与排序',desc:'密度、排序与阅读呈现'},{id:'search',group:'日常偏好',label:'搜索与使用',desc:'搜索范围与使用行为'},{id:'transfer',group:'数据与迁移',label:'导入与导出',desc:'迁入、治理与搬出'},{id:'system-info',group:'系统维护',label:'系统信息',desc:'查看当前运行事实',href:'/system-info.php'},{id:'system-baseline',group:'系统维护',label:'系统基线',desc:'查看公共运行规则与当前状态',href:'/system-baseline.php'},{id:'updates',group:'系统维护',label:'在线升级',desc:'检查并安装正式版本'},{id:'backup',group:'系统维护',label:'备份与恢复',desc:'自动备份、快照与恢复'},{id:'runtime-health',group:'系统维护',label:'运行健康',desc:'查看环境、数据库与存储健康',href:'/diagnose.php'},{id:'security',group:'系统维护',label:'安全与隐私',desc:'隐私合同和维护'}];}"
nav_start = text.find('function settingsNav(){')
nav_end = text.find('\nfunction settingsNavMarkup(nav){', nav_start)
if nav_start < 0 or nav_end < 0 or text.find('function settingsNav(){', nav_start + 1) >= 0:
    raise SystemExit('settingsNav function boundary mismatch')
text = text[:nav_start] + new_nav + text[nav_end:]

new_markup = "function settingsNavMarkup(nav){let group='';return nav.map(x=>{const label=x.group!==group?'<div class=\"settings-nav-label\">'+esc(x.group)+'</div>':'';group=x.group;const action=x.href?' data-settings-href=\"'+x.href+'\"':' data-settings-section=\"'+x.id+'\"';return label+'<button'+action+' class=\"'+(!x.href&&state.settingsSection===x.id?'active':'')+'\"><span>'+esc(x.label)+'</span></button>';}).join('');}"
markup_start = text.find('function settingsNavMarkup(nav){')
markup_end = text.find('\nfunction selectOptions', markup_start)
if markup_start < 0 or markup_end < 0 or text.find('function settingsNavMarkup(nav){', markup_start + 1) >= 0:
    raise SystemExit('settingsNavMarkup function boundary mismatch')
text = text[:markup_start] + new_markup + text[markup_end:]

old_wire = "$$('[data-settings-section]').forEach(button=>button.onclick=()=>{state.settingsSection=button.dataset.settingsSection;renderSettings({scrollTop:0});});const back=$('#settingsBack');"
new_wire = "$$('[data-settings-section]').forEach(button=>button.onclick=()=>{state.settingsSection=button.dataset.settingsSection;renderSettings({scrollTop:0});});$$('[data-settings-href]').forEach(button=>button.onclick=()=>window.location.assign(button.dataset.settingsHref));const back=$('#settingsBack');"
if text.count(old_wire) != 1:
    raise SystemExit(f'settings wiring anchor mismatch: {text.count(old_wire)}')
text = text.replace(old_wire, new_wire, 1)
app.write_text(text, encoding='utf-8')

test = root / 'tests/unit/common_baseline_ui_exposure_contract.mjs'
test.parent.mkdir(parents=True, exist_ok=True)
test.write_text("""import fs from 'node:fs';
import assert from 'node:assert/strict';

const app = fs.readFileSync('public/assets/app.js','utf8');
const diagnose = fs.readFileSync('public/diagnose.php','utf8');
const info = fs.readFileSync('public/system-info.php','utf8');
const baseline = fs.readFileSync('public/system-baseline.php','utf8');
for (const label of ['系统信息','系统基线','在线升级','备份与恢复','运行健康']) {
  assert.ok(app.includes(`label:'${label}'`), `missing visible maintenance label: ${label}`);
}
assert.ok(app.includes("href:'/system-info.php'"));
assert.ok(app.includes("href:'/system-baseline.php'"));
assert.ok(app.includes("href:'/diagnose.php'"));
assert.ok(app.includes('data-settings-href'));
assert.ok(app.includes('window.location.assign(button.dataset.settingsHref)'));
assert.ok(diagnose.includes('<title>运行健康 · VF Library</title>'));
assert.ok(diagnose.includes('<h1>运行健康</h1>'));
assert.ok(info.includes('系统信息'));
assert.ok(info.includes('href=\"/diagnose.php\">运行健康'));
assert.ok(baseline.includes('系统关键规则正常'));
assert.ok(baseline.includes('你需要关注'));
assert.ok(baseline.includes('技术详情（给开发 / 排障使用）'));
assert.ok(baseline.includes("'PASS'=>'正常'"));
assert.ok(baseline.includes("'DRIFT'=>'需要处理'"));
assert.ok(baseline.includes("'UNKNOWN'=>'暂时无法确认'"));
assert.ok(!app.includes("label:'公共规范'"), 'do not create a duplicate public-spec center');
console.log('P02_COMMON_BASELINE_HUMAN_UI_CONTRACT=PASS');
""", encoding='utf-8')
print('P02_COMMON_BASELINE_HUMAN_UI_V2_PATCH=APPLIED')
