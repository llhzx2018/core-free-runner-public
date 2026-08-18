#!/usr/bin/env bash
set -Eeuo pipefail

: "${VF_RELEASE_WRITE_TOKEN:?VF_RELEASE_WRITE_TOKEN missing}"
: "${VF_PRIVATE_READ_TOKEN:?VF_PRIVATE_READ_TOKEN missing}"

SOURCE_REPO="llhzx2018/vf-forge"
SOURCE_BRANCH="maintenance/v1.36.1-backend-polish"
BASE_TAG="v1.36.0"
FROM_VERSION="1.36.0"
TARGET_VERSION="1.36.1"
SCHEMA="30"
RELEASE_TAG="v1.36.1"
ASSET_NAME="VF_Forge_V1.36.1_UPDATE.zip"
FIXTURE_PASS="Vf1361-Polish-Runner!"
PHP_IMAGE="vf-forge-php84-v1361"
WORK="${RUNNER_TEMP:-/tmp}/p03-v1361-polish"
SOURCE="$WORK/source"
RELEASE="$WORK/release"
EVIDENCE="${GITHUB_WORKSPACE:-$PWD}/p03-v1361-release-evidence"

rm -rf "$WORK" "$EVIDENCE"
mkdir -p "$WORK" "$EVIDENCE"

cleanup() {
  docker rm -f p03-v1361-ui p03-v1361-up p03-v1361-discovery >/dev/null 2>&1 || true
}
trap cleanup EXIT

log(){ printf '\n== %s ==\n' "$*"; }

log "Clone exact V1.36.0 maintenance baseline"
git clone -q "https://x-access-token:${VF_RELEASE_WRITE_TOKEN}@github.com/${SOURCE_REPO}.git" "$SOURCE"
cd "$SOURCE"
git checkout -q "$SOURCE_BRANCH"
git fetch -q origin main --tags
CURRENT="$(cat VERSION | tr -d '\r\n')"
case "$CURRENT" in
  1.36.0|1.36.1) ;;
  *) echo "UNEXPECTED_VERSION=$CURRENT" >&2; exit 1;;
esac
test "$(git show "$BASE_TAG":VERSION | tr -d '\r\n')" = "$FROM_VERSION"
test "$(git show "$BASE_TAG":database/schema/SCHEMA_VERSION | tr -d '\r\n')" = "$SCHEMA"

log "Apply V1.36.1 backend detail polish"
python3 - <<'PY'
from pathlib import Path
import json,re
root=Path('.')

def once(text, old, new, label):
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f'PATCH_ANCHOR_MISSING:{label}')
    return text.replace(old,new,1)

(root/'VERSION').write_text('1.36.1\n', encoding='utf-8')

p=root/'src/app/bootstrap.php'; s=p.read_text(encoding='utf-8')
s=once(s,"define('VFAB_VERSION', '1.36.0');","define('VFAB_VERSION', '1.36.1');",'bootstrap-version')
p.write_text(s,encoding='utf-8')

p=root/'src/app/Repository.php'; s=p.read_text(encoding='utf-8')
s=once(s,"'auto_update_check_enabled'];","'auto_update_check_enabled','display_currency'];",'settings-allow-currency')
old="if($key==='timezone'&&!in_array($value,DateTimeZone::listIdentifiers(),true)&&$value!=='UTC')$value='UTC';"
new=old+"if($key==='display_currency'&&!in_array($value,['CNY','USD','HKD','TWD','JPY','EUR','GBP','SGD'],true))$value='CNY';"
s=once(s,old,new,'settings-currency-validation')
p.write_text(s,encoding='utf-8')

p=root/'public/api.php'; s=p.read_text(encoding='utf-8')
anchor="        case 'dashboard':\n            vfab_require_admin();"
insert="""        case 'ui_preferences':
            vfab_require_admin();$pref=$repo->settings();vfab_json(['ok'=>true,'preferences'=>['timezone'=>(string)($pref['timezone']??'Asia/Shanghai'),'date_format'=>(string)($pref['date_format']??'ymd_hm'),'display_currency'=>(string)($pref['display_currency']??'CNY'),'default_density'=>(string)($pref['default_density']??'comfortable')]]);

        case 'dashboard':
            vfab_require_admin();"""
s=once(s,anchor,insert,'ui-preferences-api')
p.write_text(s,encoding='utf-8')

p=root/'public/assets/experience.js'; js=p.read_text(encoding='utf-8')
js=once(js,
"const S={csrf:'',projects:[],projectId:0,projectTab:'overview',settingsTab:'general',settings:null};",
"const S={csrf:'',projects:[],projectId:0,projectTab:'overview',settingsTab:'general',settings:null,timezone:'Asia/Shanghai',dateFormat:'ymd_hm',currency:'CNY',defaultDensity:'comfortable'};",
'js-state')
js=once(js,
"const when=v=>{if(!v)return'—';try{return new Intl.DateTimeFormat('zh-CN',{dateStyle:'medium',timeStyle:'short'}).format(new Date(v))}catch{return esc(v)}};",
"const when=v=>{if(!v)return'—';try{const d=new Date(v),withTime=S.dateFormat!=='ymd',f=new Intl.DateTimeFormat('en-US',{timeZone:S.timezone||'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',...(withTime?{hour:'2-digit',minute:'2-digit',hour12:false}:{})}),o={};f.formatToParts(d).forEach(x=>{if(x.type!=='literal')o[x.type]=x.value});const date=S.dateFormat==='mdy_hm'?`${o.month}/${o.day}/${o.year}`:`${o.year}-${o.month}-${o.day}`;return esc(date+(withTime?` ${o.hour}:${o.minute}`:''))}catch{return esc(v)}};",
'js-time-format')
js=once(js,
"function toast(m,bad=false){const n=$('#toast');n.textContent=m;n.className='toast show'+(bad?' error':'');clearTimeout(toast.t);toast.t=setTimeout(()=>n.className='toast',3200)}",
"function toast(m,bad=false){const n=$('#toast');n.textContent=m;n.className='toast show'+(bad?' error':'');n.setAttribute('role',bad?'alert':'status');n.setAttribute('aria-atomic','true');const old=$('#inlineFeedback');if(!bad&&old)old.remove();if(bad&&$('#view')){let b=old;if(!b){b=document.createElement('div');b.id='inlineFeedback';b.className='feedback-banner error';$('#view').prepend(b)}b.innerHTML=`<strong>操作未完成</strong><span>${esc(m)}</span>`}clearTimeout(toast.t);toast.t=setTimeout(()=>n.className='toast',bad?9000:4200)}",
'js-toast')
js=once(js,
"async function renderSettings(){active('settings');crumb('设置');const d=await api('settings');S.settings=d;const tab=S.settingsTab;",
"async function renderSettings(){active('settings');crumb('设置');const d=await api('settings');S.settings=d;const pref=d.settings||{};S.timezone=String(pref.timezone||S.timezone||'Asia/Shanghai');S.dateFormat=String(pref.date_format||S.dateFormat||'ymd_hm');S.currency=String(pref.display_currency||S.currency||'CNY');S.defaultDensity=String(pref.default_density||S.defaultDensity||'comfortable');document.body.dataset.density=S.defaultDensity;const tab=S.settingsTab;",
'js-render-settings-prefs')

general=r'''function settingsGeneral(d){const s=d.settings||{},tz=String(s.timezone||'Asia/Shanghai'),currency=String(s.display_currency||'CNY');const option=(value,label,current)=>`<option value="${esc(value)}" ${current===value?'selected':''}>${esc(label)}</option>`;const tzs=[['Asia/Shanghai','中国大陆 · Asia/Shanghai'],['UTC','UTC · 世界协调时间'],['Asia/Hong_Kong','香港 · Asia/Hong_Kong'],['Asia/Taipei','台北 · Asia/Taipei'],['Asia/Tokyo','东京 · Asia/Tokyo'],['America/Los_Angeles','美国西部 · America/Los_Angeles'],['America/New_York','美国东部 · America/New_York'],['Europe/London','伦敦 · Europe/London'],['Europe/Paris','巴黎 · Europe/Paris'],['Australia/Sydney','悉尼 · Australia/Sydney']];if(!tzs.some(x=>x[0]===tz))tzs.unshift([tz,'当前 · '+tz]);const cs=[['CNY','CNY · 人民币'],['USD','USD · 美元'],['HKD','HKD · 港币'],['TWD','TWD · 新台币'],['JPY','JPY · 日元'],['EUR','EUR · 欧元'],['GBP','GBP · 英镑'],['SGD','SGD · 新加坡元']];return`<div class="settings-panel-head"><h2>基础</h2><p>只保留与当前 Project-first 产品有关的站点设置；能选择的项目不要求手工猜格式。</p></div><form id="generalSettingsForm" class="panel settings-group"><div class="form-grid"><label>站点名称<input name="site_title" value="${esc(s.site_title||'VF Forge')}"><span class="field-help">显示在系统左上角与浏览器标题中。</span></label><label>站点副标题<input name="site_subtitle" value="${esc(s.site_subtitle||'个人项目状态中心')}"><span class="field-help">建议保持简短，用来说明产品定位。</span></label><label>正式主网址<input name="site_primary_url" type="url" inputmode="url" value="${esc(s.site_primary_url||'https://forge.kewaro.com/')}"><span class="field-help">必须使用 HTTPS；用于生成正式指针与回跳地址。</span></label><label>时区<select name="timezone">${tzs.map(x=>option(x[0],x[1],tz)).join('')}</select><span class="field-help">中国大陆建议选择 Asia/Shanghai；时间记录仍以 UTC 保存，界面按这里显示。</span></label><label>日期格式<select name="date_format"><option value="ymd_hm" ${String(s.date_format||'ymd_hm')==='ymd_hm'?'selected':''}>2026-08-18 12:25</option><option value="ymd" ${String(s.date_format)==='ymd'?'selected':''}>2026-08-18</option><option value="mdy_hm" ${String(s.date_format)==='mdy_hm'?'selected':''}>08/18/2026 12:25</option></select><span class="field-help">直接按示例选择，不需要记格式代码。</span></label><label>默认币种<select name="display_currency">${cs.map(x=>option(x[0],x[1],currency)).join('')}</select><span class="field-help">用于金额类元数据的默认显示；不会改写外部 Authority 原始值。</span></label><label>页面密度<select name="default_density"><option value="comfortable" ${String(s.default_density||'comfortable')==='comfortable'?'selected':''}>舒适 · 推荐</option><option value="compact" ${String(s.default_density)==='compact'?'selected':''}>紧凑</option></select><span class="field-help">个人日常使用建议保持“舒适”。</span></label></div><div class="settings-actions"><button class="button primary">保存设置</button></div></form><section class="panel settings-group"><h3>产品存储边界</h3><div class="callout"><b>PROJECT-ASSET STORAGE = NONE</b><br>Forge 保存索引、关系、观察与 Authority Pointer，不重新开启用户项目文件上传或本地资产仓库。</div></section>`}'''
js,n=re.subn(r"function settingsGeneral\(d\)\{.*?\}\nfunction settingsSecurity",general+"\nfunction settingsSecurity",js,count=1,flags=re.S)
if n!=1 and '默认币种<select' not in js: raise SystemExit('PATCH_FAILED:settingsGeneral')

backup=r'''function settingsBackup(d){const s=d.settings||{},bs=(d.backups||[]).filter(x=>['metadata','metadata_auto','metadata_imported'].includes(String(x.backup_type||'')));const opts=(items,current)=>{current=String(current);const rows=items.map(([v,n])=>[String(v),n]);if(!rows.some(x=>x[0]===current))rows.unshift([current,`当前 · ${current}`]);return rows.map(([v,n])=>`<option value="${esc(v)}" ${current===v?'selected':''}>${esc(n)}</option>`).join('')};return`<div class="settings-panel-head"><h2>备份与恢复</h2><p>这里保护 VF Forge 自身元数据与运行状态，不是项目资产仓库。</p></div><section class="panel settings-group"><div class="settings-group-title"><div><strong>SQLite 元数据备份</strong><span>Current Truth / Pointer / Relation / Observation</span></div><button class="button primary" data-action="backup-create">立即备份</button></div><form id="backupSettingsForm"><div class="form-grid"><label>自动备份<select name="auto_sqlite_backup_enabled"><option value="1" ${String(s.auto_sqlite_backup_enabled??'1')==='1'?'selected':''}>开启 · 推荐</option><option value="0" ${String(s.auto_sqlite_backup_enabled)==='0'?'selected':''}>关闭</option></select><span class="field-help">只备份 Forge 元数据，不复制项目源码或 Release Asset。</span></label><label>备份间隔<select name="auto_sqlite_backup_interval_hours">${opts([[6,'每 6 小时'],[12,'每 12 小时'],[24,'每 24 小时 · 推荐'],[48,'每 48 小时'],[168,'每周一次'],[336,'每两周一次']],s.auto_sqlite_backup_interval_hours||24)}</select><span class="field-help">个人日常使用建议每 24 小时一次。</span></label><label>保留时长<select name="sqlite_backup_retention_days">${opts([[7,'7 天'],[15,'15 天'],[30,'30 天 · 推荐'],[60,'60 天'],[90,'90 天'],[180,'180 天'],[365,'365 天']],s.sqlite_backup_retention_days||30)}</select><span class="field-help">超过时长的旧备份可被清理，但仍受“至少保留份数”保护。</span></label><label>至少保留<select name="sqlite_backup_keep_recent">${opts([[3,'最近 3 份'],[5,'最近 5 份'],[10,'最近 10 份 · 推荐'],[20,'最近 20 份'],[30,'最近 30 份'],[50,'最近 50 份']],s.sqlite_backup_keep_recent||10)}</select><span class="field-help">即使超过保留时长，也至少留下这里指定的最近备份。</span></label></div><div class="settings-actions"><button class="button" data-action="backup-retention" type="button">执行保留策略</button><button class="button primary">保存备份策略</button></div></form></section><section class="panel settings-group"><div class="settings-group-title"><div><strong>备份历史</strong><span>先验证，再恢复；恢复不会静默执行。</span></div></div>${bs.slice(0,15).map(x=>`<div class="backup-row"><div><strong>${esc(x.filename||x.name||'SQLite Backup')}</strong><small>${when(x.created_at)} · ${bytes(x.size_bytes||x.bytes||0)} · ${esc(x.status||'')}</small></div><div class="row-actions"><button class="button small" data-action="backup-verify" data-id="${Number(x.id)}">验证</button><button class="button small" data-action="backup-preflight" data-id="${Number(x.id)}">预检恢复</button></div></div>`).join('')||empty('还没有 SQLite 元数据备份')}</section>`}'''
js,n=re.subn(r"function settingsBackup\(d\)\{.*?\}\nfunction settingsUpdate",backup+"\nfunction settingsUpdate",js,count=1,flags=re.S)
if n!=1 and '备份间隔<select' not in js: raise SystemExit('PATCH_FAILED:settingsBackup')

update=r'''function settingsUpdate(d){const s=d.settings||{},u=d.update||{},yes=Boolean(u.has_update),target=u.latest_version||'—',failed=String(u.last_error_message||'').trim()!=='';return`<div class="settings-panel-head"><h2>更新与维护</h2><p>正式更新是 VF Forge 内部维护能力；发现、验证、Atomic 与失败原因都在同一页完成。</p></div><div class="setting-status"><div class="panel status-card"><span>当前版本</span><strong>${esc(u.current_version||'V'+document.body.dataset.version)}</strong></div><div class="panel status-card"><span>Schema</span><strong>${esc(u.current_schema??document.body.dataset.schema)}</strong></div><div class="panel status-card"><span>更新通道</span><strong>core-updates</strong></div><div class="panel status-card"><span>最近检查</span><strong>${u.last_check_at?when(u.last_check_at):'尚未检查'}</strong></div></div><section class="panel settings-group"><div class="settings-group-title"><div><strong>在线更新</strong><span>Manifest → Release identity → bytes / SHA-256 → Atomic。</span></div><button class="button" data-action="update-check">检查更新</button></div><form id="updateSettingsForm"><div class="toggle-row"><div><strong>自动检查正式版本</strong><small>只检查，不静默安装。个人系统建议保持开启。</small></div><select name="auto_update_check_enabled"><option value="1" ${String(s.auto_update_check_enabled??'1')==='1'?'selected':''}>开启 · 推荐</option><option value="0" ${String(s.auto_update_check_enabled)==='0'?'selected':''}>关闭</option></select></div><div class="settings-actions"><button class="button">保存更新策略</button></div></form>${failed?`<div class="feedback-banner error"><strong>更新检查未完成</strong><span>${esc(u.last_error_message)}</span></div>`:''}<div class="maintenance-box ${yes?'is-ready':''}"><h3>${yes?`发现正式更新 ${esc(target)}`:'当前没有可安装的正式更新'}</h3><p>${yes?esc(u.release_notes?.summary||'正式更新已通过统一发现。'):esc(failed?'修正上方问题后重新检查。':'Working / Candidate 不会作为 Production 更新显示。')}</p>${yes?`<button class="button primary" data-action="update-install">更新到 ${esc(target)}</button>`:''}</div></section><section class="panel settings-group"><h3>高级手工 Atomic</h3><p class="muted">仅作为在线发现不可用时的受控维护入口。这里处理的是软件更新运输，不是项目文件上传。</p><a class="button" href="maintenance.php">打开受控 Atomic 入口</a></section>`}'''
js,n=re.subn(r"function settingsUpdate\(d\)\{.*?\}\nfunction flat",update+"\nfunction flat",js,count=1,flags=re.S)
if n!=1 and '最近检查</span>' not in js: raise SystemExit('PATCH_FAILED:settingsUpdate')

js=once(js,
"S.csrf=s.csrf||'';document.body.dataset.version",
"S.csrf=s.csrf||'';try{const u=await api('ui_preferences');const q=u.preferences||{};S.timezone=String(q.timezone||S.timezone);S.dateFormat=String(q.date_format||S.dateFormat);S.currency=String(q.display_currency||S.currency);S.defaultDensity=String(q.default_density||S.defaultDensity);document.body.dataset.density=S.defaultDensity}catch{}document.body.dataset.version",
'init-ui-preferences')
js=once(js,
"}catch(z){a.disabled=false;toast(z.message,true)}});",
"}catch(z){a.disabled=false;toast(z.message,true);if(a.dataset.action==='update-check'){try{await renderSettings()}catch{}}}});",
'update-check-persistent-error')
if '/* V1.36.1 BACKEND POLISH */' not in js:
    js='/* V1.36.1 BACKEND POLISH */\n'+js
p.write_text(js,encoding='utf-8')

p=root/'public/assets/experience.css'; css=p.read_text(encoding='utf-8')
marker='/* V1.36.1 BACKEND POLISH */'
if marker not in css:
    css += r'''

/* V1.36.1 BACKEND POLISH */
:root{--font-page:26px;--font-section:18px;--font-card:15px;--font-body:14px;--font-label:13px;--font-meta:12px}
html,body{font-size:var(--font-body);line-height:1.5}button,input,select,textarea{font-size:var(--font-body);line-height:1.4}
.page-head h1{font-size:var(--font-page);line-height:1.25;margin:3px 0 6px}.page-head p{font-size:var(--font-body);line-height:1.6}.eyebrow{font-size:var(--font-meta)}
.brand strong{font-size:15px}.brand small{font-size:var(--font-meta)}.nav-item{font-size:var(--font-body)}.nav-item b,.warn-count,.sidebar-label{font-size:var(--font-meta)}
.runtime-card span,.runtime-card small{font-size:var(--font-meta)}.runtime-card strong{font-size:var(--font-body)}.breadcrumb{font-size:var(--font-label)}
.settings-nav button{font-size:var(--font-body);line-height:1.45;padding:10px 11px}.settings-panel-head h2{font-size:var(--font-section);line-height:1.35;margin-bottom:4px}.settings-panel-head p{font-size:var(--font-body);line-height:1.55}
.section h2,.side-card h3,.settings-group h3,.settings-group-title strong,.list-card h3,.event h3{font-size:var(--font-card);line-height:1.45}.settings-group-title span{font-size:var(--font-meta);line-height:1.5}
.form-grid{gap:16px 14px}.form-grid label{font-size:var(--font-label);line-height:1.45;color:#46514d;font-weight:560}.form-grid input,.form-grid select{height:43px;font-size:var(--font-body);margin-top:7px;padding:0 11px;border-color:#d9dfdc;box-shadow:0 1px 0 rgba(20,28,26,.02)}
.form-grid input:focus,.form-grid select:focus,.toggle-row select:focus,.search-box input:focus{outline:3px solid rgba(22,140,130,.12);border-color:#55a99f}
.field-help{display:block;margin-top:6px;color:#77817d;font-size:var(--font-meta);line-height:1.5;font-weight:400}.button{font-size:var(--font-label);min-height:36px}.button.small{font-size:var(--font-meta);min-height:30px}
.table-row{font-size:var(--font-label)}.table-row.header,.project-cell small,.version-sub,.event-time,.pointer-row small,.backup-row small,.session-row small{font-size:var(--font-meta)}.muted,.mini,.callout,.why,.node,.maintenance-box p,.system-row span,.system-row b{font-size:var(--font-meta);line-height:1.55}
.summary-card label,.metric label,.next-action label,.status-card span{font-size:var(--font-meta)}.summary-card strong{font-size:16px}.metric strong,.next-action strong,.status-card strong{font-size:var(--font-body)}
.setting-status{grid-template-columns:repeat(4,minmax(0,1fr))}.status-card{min-height:78px}.toggle-row strong{font-size:var(--font-body)}.toggle-row small{font-size:var(--font-meta);line-height:1.5}.toggle-row select{font-size:var(--font-body);min-width:132px}
.feedback-banner{display:flex;gap:10px;align-items:flex-start;margin:14px 0;padding:12px 14px;border-radius:10px;border:1px solid #e7c0bd;background:#fff5f4;color:#742c28;font-size:var(--font-label);line-height:1.5}.feedback-banner strong{flex:none}.feedback-banner span{min-width:0}.maintenance-box.is-ready{border-color:#b9ded6;background:#f2faf8}
.toast{right:22px;bottom:22px;min-width:320px;max-width:min(480px,calc(100vw - 32px));padding:14px 16px;border:1px solid rgba(255,255,255,.18);border-radius:11px;font-size:var(--font-body);font-weight:650;line-height:1.5;box-shadow:0 14px 38px rgba(16,24,22,.18)}.toast.error{background:#9f332d;color:#fff;border-color:#7f2622}
.settings-group{padding:20px 21px}.settings-actions{margin-top:18px}.maintenance-box{padding:16px}.backup-row,.session-row,.system-row{padding:13px 0}
body[data-density="compact"] .table-row{padding-top:9px;padding-bottom:9px}body[data-density="compact"] .settings-group{padding:16px 18px}body[data-density="compact"] .form-grid{gap:11px 12px}
@media(max-width:900px){.setting-status{grid-template-columns:repeat(2,minmax(0,1fr))}.settings-nav button{font-size:13px}.toast{right:12px;bottom:72px}}
@media(max-width:520px){.page-head h1{font-size:24px}.settings-panel-head h2{font-size:18px}.form-grid label{font-size:13px}.setting-status{grid-template-columns:1fr 1fr}.toast{left:11px;right:11px;min-width:0;max-width:none}.feedback-banner{display:block}.feedback-banner strong,.feedback-banner span{display:block}.feedback-banner span{margin-top:3px}}
'''
p.write_text(css,encoding='utf-8')

p=root/'VF_PROJECT.json'; d=json.loads(p.read_text(encoding='utf-8'))
d['status']='V1.36.1 BACKEND DETAIL POLISH / FORMAL RELEASE GATE'
d['production_version']='1.36.0';d['working_version']='1.36.1';d['candidate_version']='1.36.1';d['schema_version']=30
d['working_branch']='maintenance/v1.36.1-backend-polish'
d['current_phase']='V1.36.1 BACKEND DETAIL POLISH / FORMAL RELEASE GATE'
d['current_verdict']='POLISH_IMPLEMENTED / RELEASE_GATE_PENDING'
d['version_change']='1.36.1 WORKING';d['production_write']='NO'
d['next_action']='FORMAL GATE -> RELEASE -> core-updates PUBLISH -> OWNER BACKEND UPDATE'
d['v1_36_1_backend_polish']={'scope':['GLOBAL TYPOGRAPHY SYSTEM','SETTINGS INPUT NORMALIZATION','TIMEZONE SELECT','DATE FORMAT SELECT','DISPLAY CURRENCY SELECT','BACKUP POLICY PRESETS','FEEDBACK VISIBILITY','UPDATE STATUS DETAIL','RESPONSIVE CONSISTENCY'],'schema':30,'migration':'NONE','project_asset_storage':'NONE','production_write':'NO'}
if isinstance(d.get('release'),dict):
    d['release']['production_version']='1.36.0';d['release']['production_tag']='v1.36.0';d['release']['candidate_version']='1.36.1';d['release']['candidate_release']='FORMAL RELEASE GATE PENDING';d['release']['production_write']=False
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

(root/'docs/product/V1361_BACKEND_DETAIL_POLISH.md').write_text('''# P03 · VF Forge V1.36.1 Backend Detail Polish

- Production baseline: V1.36.0 / Schema 30
- Target: V1.36.1 / Schema 30
- Migration: NONE
- Product storage boundary: PROJECT-ASSET STORAGE = NONE

## Scope

1. Global typography reduced to six stable levels.
2. Form labels, controls, helper text and buttons normalized.
3. Timezone becomes a curated select; date format becomes example-first select.
4. Default display currency becomes a validated select setting.
5. Backup interval / retention days / minimum recent copies become presets.
6. Error feedback becomes high-contrast and persistent in-page for update failures.
7. Update page adds last-check visibility and clearer current state.
8. Desktop 1440 and mobile 390 remain one unified product shell.

No project file upload or local project asset storage is reintroduced.
''',encoding='utf-8')
PY

node --check public/assets/experience.js
python3 scripts/repo_health.py .
git diff --exit-code "$BASE_TAG" -- database/schema database/migrations

git config user.name 'VF Agent'
git config user.email 'vf-agent@users.noreply.github.com'
git add VERSION VF_PROJECT.json src/app/bootstrap.php src/app/Repository.php public/api.php public/assets/experience.js public/assets/experience.css docs/product/V1361_BACKEND_DETAIL_POLISH.md
if ! git diff --cached --quiet; then
  git commit -m 'fix(ui): polish backend details for v1.36.1'
  git push -q origin HEAD:"$SOURCE_BRANCH"
fi
SOURCE_SHA="$(git rev-parse HEAD)"
echo "SOURCE_SHA=$SOURCE_SHA"
test "$(cat VERSION | tr -d '\r\n')" = "$TARGET_VERSION"
test "$(cat database/schema/SCHEMA_VERSION | tr -d '\r\n')" = "$SCHEMA"
grep -Fq "define('VFAB_VERSION', '1.36.1');" src/app/bootstrap.php
grep -Fq 'V1.36.1 BACKEND POLISH' public/assets/experience.css
grep -Fq '默认币种<select' public/assets/experience.js
grep -Fq 'PROJECT_ASSET_STORAGE_RETIRED' public/api.php

log "Build PHP 8.4.24 supported runtime"
cat > "$WORK/Dockerfile" <<'EOF'
FROM php:8.4.24-cli-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends libzip-dev sqlite3 curl git && docker-php-ext-install zip && rm -rf /var/lib/apt/lists/*
EOF
docker build -q -t "$PHP_IMAGE" -f "$WORK/Dockerfile" "$WORK" >/dev/null
docker run --rm "$PHP_IMAGE" php -r 'foreach(["pdo_sqlite","sqlite3","zip","fileinfo","sodium"] as $x){if(!extension_loaded($x)){fwrite(STDERR,"missing:$x\n");exit(1);}}echo PHP_VERSION," EXTENSIONS_PASS\n";'
docker run --rm -v "$SOURCE:/app:ro" -w /app "$PHP_IMAGE" sh -lc 'set -e; find src public -type f -name "*.php" -print0 | xargs -0 -n1 php -l >/dev/null; php -r '\''require "src/app/bootstrap.php";$x=vfab_php_security_baseline();if(empty($x["ok"]))exit(1);echo "PHP_SECURITY_PASS\n";'\'''

log "Browser regression: settings, typography, responsive"
ROOT="$WORK/ui-runtime"; DATA="$WORK/ui-private"; URL="http://127.0.0.1:18101"; C="p03-v1361-ui"
python3 scripts/build_runtime.py "$ROOT" >/dev/null
mkdir -p "$DATA"
docker run -d --rm --name "$C" -e VF_PRIVATE_READ_TOKEN="$VF_PRIVATE_READ_TOKEN" -p 18101:18101 -v "$ROOT:/app" -v "$DATA:$DATA" -w /app "$PHP_IMAGE" php -S 0.0.0.0:18101 -t /app >/dev/null
READY=0;for _ in $(seq 1 80);do curl -fsS "$URL/setup.php" >/dev/null 2>&1&&{ READY=1;break;};sleep .25;done;test "$READY" = 1
COOKIE="$WORK/ui-cookie";curl -fsS -c "$COOKIE" "$URL/setup.php" -o "$WORK/ui-setup.html"
CSRF=$(python3 - "$WORK/ui-setup.html" <<'PY'
import re,sys
print(re.search(r'name="setup_csrf" value="([^"]+)"',open(sys.argv[1],encoding='utf-8').read()).group(1))
PY
)
curl -fsS -i -b "$COOKIE" -c "$COOKIE" -H "Origin: $URL" --data-urlencode "setup_csrf=$CSRF" --data-urlencode 'site_title=VF Forge Polish Gate' --data-urlencode "data_root=$DATA" --data-urlencode "password=$FIXTURE_PASS" --data-urlencode "password_confirm=$FIXTURE_PASS" "$URL/setup.php" >/dev/null
mkdir -p "$WORK/node";cd "$WORK/node";npm init -y >/dev/null 2>&1;npm install --no-save playwright@1.55.0 >/dev/null;npx playwright install --with-deps chromium >/dev/null
cat > gate.mjs <<'JS'
import{chromium}from'playwright';
const b=await chromium.launch({headless:true}),p=await b.newPage({viewport:{width:1440,height:900}}),errs=[];
p.on('pageerror',e=>errs.push('PAGE:'+e.message));p.on('console',m=>{if(m.type()==='error')errs.push('CONSOLE:'+m.text())});
await p.goto('http://127.0.0.1:18101/',{waitUntil:'domcontentloaded'});await p.fill('#loginPassword',process.env.FIXTURE_PASS);await p.click('#loginForm button[type=submit]');await p.waitForSelector('#app:not([hidden])');
await p.click('[data-route="settings"]');await p.waitForSelector('#generalSettingsForm');
for(const s of ['select[name="timezone"]','select[name="date_format"]','select[name="display_currency"]','select[name="default_density"]'])if(await p.locator(s).count()!==1)throw Error('missing '+s);
for(const v of ['Asia/Shanghai','UTC','America/New_York'])if(!await p.locator(`select[name="timezone"] option[value="${v}"]`).count())throw Error('timezone '+v);
for(const v of ['CNY','USD','HKD'])if(!await p.locator(`select[name="display_currency"] option[value="${v}"]`).count())throw Error('currency '+v);
await p.selectOption('select[name="timezone"]','Asia/Shanghai');await p.selectOption('select[name="date_format"]','ymd_hm');await p.selectOption('select[name="display_currency"]','CNY');await p.selectOption('select[name="default_density"]','comfortable');await p.click('#generalSettingsForm button[type="submit"]');await p.waitForTimeout(300);
await p.click('[data-settings-tab="backup"]');await p.waitForSelector('#backupSettingsForm');
for(const s of ['select[name="auto_sqlite_backup_interval_hours"]','select[name="sqlite_backup_retention_days"]','select[name="sqlite_backup_keep_recent"]'])if(await p.locator(s).count()!==1)throw Error('backup select '+s);
await p.selectOption('select[name="auto_sqlite_backup_interval_hours"]','48');await p.selectOption('select[name="sqlite_backup_retention_days"]','60');await p.selectOption('select[name="sqlite_backup_keep_recent"]','20');await p.click('#backupSettingsForm button[type="submit"]');await p.waitForTimeout(300);
await p.click('[data-settings-tab="general"]');await p.waitForSelector('#generalSettingsForm');if(await p.inputValue('select[name="timezone"]')!=='Asia/Shanghai')throw Error('timezone not saved');if(await p.inputValue('select[name="display_currency"]')!=='CNY')throw Error('currency not saved');
const font=await p.evaluate(()=>({page:getComputedStyle(document.querySelector('.page-head h1')).fontSize,section:getComputedStyle(document.querySelector('.settings-panel-head h2')).fontSize,label:getComputedStyle(document.querySelector('.form-grid label')).fontSize,control:getComputedStyle(document.querySelector('.form-grid select')).fontSize,nav:getComputedStyle(document.querySelector('.settings-nav button')).fontSize}));
if(JSON.stringify(font)!==JSON.stringify({page:'26px',section:'18px',label:'13px',control:'14px',nav:'14px'}))throw Error('typography '+JSON.stringify(font));
for(const tab of ['security','backup','update','system']){await p.click(`[data-settings-tab="${tab}"]`);await p.waitForTimeout(100)}
for(const vp of [{width:1440,height:900},{width:390,height:844}]){await p.setViewportSize(vp);for(const route of ['projects','settings']){await p.click(`[data-route="${route}"]`);await p.waitForTimeout(120);const [sw,cw]=await p.evaluate(()=>[document.documentElement.scrollWidth,document.documentElement.clientWidth]);if(sw>cw+2)throw Error('overflow '+route+' '+vp.width)}}
if(errs.length)throw Error(errs.join('\n'));console.log('V1361_BROWSER_SETTINGS_PASS typography=6-level selects=PASS responsive=1440,390 errors=0');await b.close();
JS
FIXTURE_PASS="$FIXTURE_PASS" node gate.mjs
cd "$SOURCE";docker rm -f "$C" >/dev/null

log "Build exact V1.36.1 UPDATE Asset"
TARGET="$WORK/target"; BASE="$WORK/base"; WT="$WORK/base-wt"
python3 scripts/build_runtime.py "$TARGET" >/dev/null
git worktree add --detach "$WT" "$BASE_TAG" >/dev/null
python3 "$WT/scripts/build_runtime.py" "$BASE" >/dev/null
git worktree remove --force "$WT" >/dev/null
cp scripts/build_atomic.py "$WORK/builder.py"
python3 - "$WORK/builder.py" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text(encoding='utf-8')
s=s.replace('1.35.3','1.36.1').replace('1.35.2','1.36.0')
s=s.replace('TARGET_SCHEMA=29','TARGET_SCHEMA=30').replace('VFF_ATOMIC_SCHEMA=29','VFF_ATOMIC_SCHEMA=30')
s=s.replace("'maintenance.php','robots.txt'","'maintenance.php','memory-api.php','robots.txt'")
p.write_text(s,encoding='utf-8')
PY
python3 "$WORK/builder.py" --base-runtime "$BASE" --target-runtime "$TARGET" --output "$RELEASE" >/dev/null
GENERATED=$(find "$RELEASE" -maxdepth 1 -type f -name 'VF_Forge_V1.36.1_*Upgrade.zip' -printf '%f\n' | head -1);test -n "$GENERATED";mv "$RELEASE/$GENERATED" "$RELEASE/$ASSET_NAME"
ZIP="$RELEASE/$ASSET_NAME";unzip -t "$ZIP" >/dev/null;test "$(unzip -Z1 "$ZIP")" = 'repair-v1.36.1.php'
unzip -p "$ZIP" repair-v1.36.1.php > "$WORK/repair.php"
grep -Fq "const VFF_ATOMIC_TARGET='1.36.1';" "$WORK/repair.php";grep -Fq 'const VFF_ATOMIC_SCHEMA=30;' "$WORK/repair.php";grep -Fq 'const VFF_ATOMIC_ALLOWED=["1.36.0"];' "$WORK/repair.php"
! unzip -Z1 "$ZIP" | grep -E '(^|/)(database|PRIVATE_DATA|uploads|backup|cache|session|logs|tmp)(/|$)|\.sqlite3?$|\.db$|(^|/)\.env$'
ASSET_SHA=$(sha256sum "$ZIP"|awk '{print $1}');ASSET_BYTES=$(stat -c '%s' "$ZIP")

log "Real Atomic upgrade V1.36.0 -> V1.36.1"
ROOT="$WORK/up-runtime";DATA="$WORK/up-private";COOKIE="$WORK/up-cookie";URL="http://127.0.0.1:18102";C="p03-v1361-up"
git worktree add --detach "$WORK/up-wt" "$BASE_TAG" >/dev/null;python3 "$WORK/up-wt/scripts/build_runtime.py" "$ROOT" >/dev/null;git worktree remove --force "$WORK/up-wt" >/dev/null
mkdir -p "$DATA";docker run -d --rm --name "$C" -p 18102:18102 -v "$ROOT:/app" -v "$DATA:$DATA" -w /app "$PHP_IMAGE" php -S 0.0.0.0:18102 -t /app >/dev/null
READY=0;for _ in $(seq 1 80);do curl -fsS "$URL/setup.php" >/dev/null 2>&1&&{ READY=1;break;};sleep .25;done;test "$READY" = 1
curl -fsS -c "$COOKIE" "$URL/setup.php" -o "$WORK/up-setup.html";CSRF=$(python3 - "$WORK/up-setup.html" <<'PY'
import re,sys;print(re.search(r'name="setup_csrf" value="([^"]+)"',open(sys.argv[1],encoding='utf-8').read()).group(1))
PY
)
curl -fsS -i -b "$COOKIE" -c "$COOKIE" -H "Origin: $URL" --data-urlencode "setup_csrf=$CSRF" --data-urlencode 'site_title=VF Forge Upgrade Gate' --data-urlencode "data_root=$DATA" --data-urlencode "password=$FIXTURE_PASS" --data-urlencode "password_confirm=$FIXTURE_PASS" "$URL/setup.php" >/dev/null
curl -fsS -b "$COOKIE" -c "$COOKIE" -H "Origin: $URL" -H 'Content-Type: application/json' --data "{\"password\":\"$FIXTURE_PASS\"}" "$URL/api.php?action=login" -o "$WORK/up-login.json"
python3 - "$WORK/up-login.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]));assert d['ok'] and d['version']=='1.36.0'
PY
unzip -p "$ZIP" repair-v1.36.1.php > "$ROOT/repair-v1.36.1.php";curl -fsS -b "$COOKIE" "$URL/repair-v1.36.1.php" -o "$WORK/repair-form.html";RCSRF=$(python3 - "$WORK/repair-form.html" <<'PY'
import re,sys;print(re.search(r'name="_csrf" value="([^"]+)"',open(sys.argv[1],encoding='utf-8').read()).group(1))
PY
)
curl -fsS -b "$COOKIE" -H "Origin: $URL" --data-urlencode "_csrf=$RCSRF" --data-urlencode confirmation=UPGRADE "$URL/repair-v1.36.1.php" -o "$WORK/result.html"
grep -q '升级完成' "$WORK/result.html";grep -Fq "define('VFAB_VERSION', '1.36.1');" "$ROOT/app/bootstrap.php";grep -Fq 'V1.36.1 BACKEND POLISH' "$ROOT/assets/experience.css";test ! -e "$ROOT/repair-v1.36.1.php"
DB=$(docker exec "$C" sh -lc "find '$DATA/database' -maxdepth 1 -type f -name '*.sqlite' | head -1");test -n "$DB";test "$(docker exec "$C" sqlite3 "$DB" 'pragma integrity_check;')" = ok;test -z "$(docker exec "$C" sqlite3 "$DB" 'pragma foreign_key_check;')";docker rm -f "$C" >/dev/null

echo 'ATOMIC_1360_TO_1361_PASS'

log "Publish GitHub Release and core-updates"
export GH_TOKEN="$VF_RELEASE_WRITE_TOKEN"
printf '%s\n' 'P03 · VF Forge V1.36.1' 'Backend detail polish: unified typography, selectable timezone/date/currency, backup presets, stronger feedback, consistent settings. Schema 30 unchanged. PROJECT-ASSET STORAGE = NONE.' > "$WORK/notes.md"
if gh release view "$RELEASE_TAG" --repo "$SOURCE_REPO" >/dev/null 2>&1; then
  REF=$(gh api "repos/$SOURCE_REPO/git/ref/tags/$RELEASE_TAG" --jq '.object.sha');test "$REF" = "$SOURCE_SHA";gh release upload "$RELEASE_TAG" "$ZIP" --repo "$SOURCE_REPO" --clobber
else
  gh release create "$RELEASE_TAG" "$ZIP" --repo "$SOURCE_REPO" --target "$SOURCE_SHA" --title 'VF Forge V1.36.1' --notes-file "$WORK/notes.md"
fi
REL=$(gh api "repos/$SOURCE_REPO/releases/tags/$RELEASE_TAG");RID=$(jq -r '.id'<<<"$REL");AID=$(jq -r --arg n "$ASSET_NAME" '.assets[]|select(.name==$n)|.id'<<<"$REL");RBYTES=$(jq -r --arg n "$ASSET_NAME" '.assets[]|select(.name==$n)|.size'<<<"$REL");test "$RBYTES" = "$ASSET_BYTES";test -n "$AID"
RELEASED=$(date -u +%Y-%m-%dT%H:%M:%SZ);MANIFEST="$WORK/P03.json"
cat > "$MANIFEST" <<JSON
{
  "schema_version":"1.0",
  "project_id":"P03",
  "component_id":"APP",
  "enabled":true,
  "target_version":"1.36.1",
  "update_type":"ATOMIC",
  "from_versions":["1.36.0"],
  "schema_from":"30",
  "schema_to":"30",
  "repository":"llhzx2018/vf-forge",
  "release_tag":"v1.36.1",
  "release_id":$RID,
  "product_identity":"$SOURCE_SHA",
  "asset_name":"$ASSET_NAME",
  "asset_bytes":$ASSET_BYTES,
  "asset_sha256":"$ASSET_SHA",
  "backup_required":true,
  "rollback_supported":true,
  "released_at":"$RELEASED",
  "release_notes":{"summary":"V1.36.1：后台细节统一优化；字体层级、设置选择、备份策略、反馈可见性与响应式一致性完成收口。"},
  "notes":"Schema 30 unchanged. Upgrade from V1.36.0. PROJECT-ASSET STORAGE = NONE."
}
JSON
CREF=$(gh api repos/llhzx2018/core-updates/contents/projects/P03.json?ref=main);CSHA=$(jq -r '.sha'<<<"$CREF");ENC=$(base64 -w0 "$MANIFEST");gh api --method PUT repos/llhzx2018/core-updates/contents/projects/P03.json -f message='release(P03): publish VF Forge V1.36.1' -f content="$ENC" -f sha="$CSHA" -f branch=main >/dev/null
REMOTE=$(gh api repos/llhzx2018/core-updates/contents/projects/P03.json?ref=main --jq .content|base64 -d)
jq -e --arg sha "$SOURCE_SHA" --arg an "$ASSET_NAME" --arg ah "$ASSET_SHA" --argjson b "$ASSET_BYTES" '.target_version=="1.36.1" and .from_versions==["1.36.0"] and .product_identity==$sha and .asset_name==$an and .asset_sha256==$ah and .asset_bytes==$b and .schema_to=="30"'<<<"$REMOTE" >/dev/null

log "Exact V1.36.0 backend discovery of V1.36.1"
ROOT="$WORK/discovery-runtime";DATA="$WORK/discovery-private";COOKIE="$WORK/discovery-cookie";URL="http://127.0.0.1:18103";C="p03-v1361-discovery"
git worktree add --detach "$WORK/discovery-wt" "$BASE_TAG" >/dev/null;python3 "$WORK/discovery-wt/scripts/build_runtime.py" "$ROOT" >/dev/null;git worktree remove --force "$WORK/discovery-wt" >/dev/null;mkdir -p "$DATA"
docker run -d --rm --name "$C" -e VF_PRIVATE_READ_TOKEN="$VF_PRIVATE_READ_TOKEN" -p 18103:18103 -v "$ROOT:/app" -v "$DATA:$DATA" -w /app "$PHP_IMAGE" php -S 0.0.0.0:18103 -t /app >/dev/null
READY=0;for _ in $(seq 1 80);do curl -fsS "$URL/setup.php" >/dev/null 2>&1&&{ READY=1;break;};sleep .25;done;test "$READY" = 1
curl -fsS -c "$COOKIE" "$URL/setup.php" -o "$WORK/d-setup.html";CSRF=$(python3 - "$WORK/d-setup.html" <<'PY'
import re,sys;print(re.search(r'name="setup_csrf" value="([^"]+)"',open(sys.argv[1],encoding='utf-8').read()).group(1))
PY
)
curl -fsS -i -b "$COOKIE" -c "$COOKIE" -H "Origin: $URL" --data-urlencode "setup_csrf=$CSRF" --data-urlencode 'site_title=VF Forge Discovery' --data-urlencode "data_root=$DATA" --data-urlencode "password=$FIXTURE_PASS" --data-urlencode "password_confirm=$FIXTURE_PASS" "$URL/setup.php" >/dev/null
curl -fsS -b "$COOKIE" -c "$COOKIE" -H "Origin: $URL" -H 'Content-Type: application/json' --data "{\"password\":\"$FIXTURE_PASS\"}" "$URL/api.php?action=login" -o "$WORK/d-login.json";CSRF2=$(python3 - "$WORK/d-login.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]));assert d['ok'] and d['version']=='1.36.0';print(d['csrf'])
PY
)
curl -fsS -b "$COOKIE" -H "Origin: $URL" -H "X-CSRF-Token: $CSRF2" -H 'Content-Type: application/json' --data '{}' "$URL/api.php?action=system_update_check" -o "$WORK/check.json"
python3 - "$WORK/check.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]));u=d.get('update') or {};assert d.get('ok') is True;assert u.get('has_update') is True;assert u.get('latest_version')=='1.36.1';assert u.get('asset_name')=='VF_Forge_V1.36.1_UPDATE.zip';assert not u.get('last_error_message');print('BACKEND_DISCOVERY_1360_TO_1361_PASS')
PY
docker rm -f "$C" >/dev/null

cat > "$EVIDENCE/release-readback.json" <<JSON
{
  "project":"P03 · VF Forge",
  "source_sha":"$SOURCE_SHA",
  "from":"1.36.0",
  "target":"1.36.1",
  "schema":30,
  "release_id":$RID,
  "asset_id":$AID,
  "asset_name":"$ASSET_NAME",
  "asset_bytes":$ASSET_BYTES,
  "asset_sha256":"$ASSET_SHA",
  "atomic_1360_to_1361":"PASS",
  "browser_settings":"PASS",
  "backend_discovery_1360_to_1361":"PASS",
  "project_asset_storage":"NONE"
}
JSON
printf '%s  %s\n' "$ASSET_SHA" "$ASSET_NAME" > "$EVIDENCE/SHA256SUMS.txt"

echo "P03_V1361_BACKEND_POLISH_RELEASE_PASS source=$SOURCE_SHA release=$RID asset=$AID bytes=$ASSET_BYTES sha=$ASSET_SHA"
