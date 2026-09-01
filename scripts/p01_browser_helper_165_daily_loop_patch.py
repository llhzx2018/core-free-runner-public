from pathlib import Path
import json


def replace_once(path, old, new, label):
    p = Path(path)
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(f'{label}: expected 1 match, got {n}')
    p.write_text(s.replace(old, new, 1))

# Component version.
p = Path('src/browser-extension/manifest.json')
data = json.loads(p.read_text())
if data.get('version') != '1.6.4':
    raise SystemExit(f"manifest version drift: {data.get('version')}")
data['version'] = '1.6.5'
p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

replace_once(
    'src/browser-extension/README.md',
    '# VF Start 保存助手 V1.6.4\n',
    '# VF Start 保存助手 V1.6.5\n',
    'README title version',
)
replace_once(
    'src/browser-extension/README.md',
    '## V1.6.4 保存模型\n',
    '## V1.6.5 保存模型\n',
    'README model version',
)
p = Path('src/browser-extension/README.md')
s = p.read_text()
anchor = '- 保存成功的离线队列项会立即从本机删除。\n'
addition = anchor + '- 首次安装会自动打开连接设置；未连接或令牌失效时，弹窗主按钮直接引导连接，不先制造一次失败；\n- “打开待整理”使用当前 `links-admin.php?view=pending` 路由。\n'
if s.count(anchor) != 1:
    raise SystemExit('README behavior anchor drift')
p.write_text(s.replace(anchor, addition, 1))

# Background: status should expose setup state; first install opens setup; pending route follows current app.
p = Path('src/browser-extension/background.js')
s = p.read_text()
old = "chrome.runtime.onInstalled.addListener(()=>{buildMenus();cleanupLegacyPrivacyData().catch(()=>{});chrome.alarms.create(ALARM,{periodInMinutes:5});restoreQueueBadge().catch(()=>{})});"
new = "chrome.runtime.onInstalled.addListener(details=>{buildMenus();cleanupLegacyPrivacyData().catch(()=>{});chrome.alarms.create(ALARM,{periodInMinutes:5});restoreQueueBadge().catch(()=>{});if(details&&details.reason==='install')chrome.runtime.openOptionsPage()});"
if s.count(old) != 1:
    raise SystemExit('onInstalled anchor drift')
s = s.replace(old, new, 1)
old = "if(msg&&msg.type==='vfnav-status'){const c=await settings();return {ok:true,pendingCount:await queueCount(),tokenInvalidAt:c.tokenInvalidAt||''}}"
new = "if(msg&&msg.type==='vfnav-status'){const c=await settings();return {ok:true,configured:!!(c.siteUrl&&c.token),pendingCount:await queueCount(),tokenInvalidAt:c.tokenInvalidAt||''}}"
if s.count(old) != 1:
    raise SystemExit('status anchor drift')
s = s.replace(old, new, 1)
old = "await chrome.tabs.create({url:normalizeConfiguredSite(c.siteUrl)+'/#/pending'});"
new = "await chrome.tabs.create({url:normalizeConfiguredSite(c.siteUrl)+'/links-admin.php?view=pending'});"
if s.count(old) != 1:
    raise SystemExit('pending route anchor drift')
s = s.replace(old, new, 1)
p.write_text(s)

# Popup: setup failure becomes a primary next action, not a misleading save failure.
p = Path('src/browser-extension/popup.js')
s = p.read_text()
s = s.replace('let currentTab=null;\n', 'let currentTab=null;\nlet connectionReady=false;\n', 1)
anchor = "function safeHost(url){\n  try{return new URL(url).hostname}catch(e){return ''}\n}\n\n"
insert = anchor + "async function loadConnectionState(){\n  const state=await chrome.runtime.sendMessage({type:'vfnav-status'});\n  const configured=!!(state&&state.ok&&state.configured);\n  const invalid=!!(state&&state.tokenInvalidAt);\n  connectionReady=configured&&!invalid;\n  if(connectionReady)return true;\n  saveButton.disabled=false;\n  saveButton.textContent=invalid?'重新连接 VF Start':'连接 VF Start';\n  setStatus(invalid?'连接已失效，请重新连接。':'首次使用先连接 VF Start。','queued');\n  return false;\n}\n\n"
if s.count(anchor) != 1:
    raise SystemExit('popup safeHost anchor drift')
s = s.replace(anchor, insert, 1)
old = "  saveButton.disabled=false;\n  setStatus('');\n}"
new = "  if(!connectionReady){saveButton.disabled=false;return;}\n  saveButton.disabled=false;\n  saveButton.textContent='保存到待整理';\n  setStatus('');\n}"
if s.count(old) != 1:
    raise SystemExit('popup load state anchor drift')
s = s.replace(old, new, 1)
old = "saveButton.addEventListener('click',async()=>{\n  if(!currentTab||saveButton.disabled)return;"
new = "saveButton.addEventListener('click',async()=>{\n  if(!connectionReady){chrome.runtime.openOptionsPage();window.close();return;}\n  if(!currentTab||saveButton.disabled)return;"
if s.count(old) != 1:
    raise SystemExit('popup click anchor drift')
s = s.replace(old, new, 1)
old = "loadCurrentTab().catch(e=>{"
new = "loadConnectionState().then(loadCurrentTab).catch(e=>{"
if s.count(old) != 1:
    raise SystemExit('popup init anchor drift')
s = s.replace(old, new, 1)
p.write_text(s)

# Options copy reflects that Save already validates the connection.
replace_once(
    'src/browser-extension/options.html',
    '<button id="save" class="primary">保存连接设置</button>',
    '<button id="save" class="primary">连接并保存</button>',
    'options primary action',
)
replace_once(
    'src/browser-extension/options.html',
    '<footer>VF Start 浏览器助手 · V1.6.4</footer>',
    '<footer>VF Start 浏览器助手 · V1.6.5</footer>',
    'options footer version',
)

# Only component version authority changes; do not reconcile stale develop production fields.
p = Path('VF_PROJECT.json')
data = json.loads(p.read_text())
components = data.setdefault('component_versions', {})
if components.get('browser_helper') != '1.6.4':
    raise SystemExit(f"VF_PROJECT browser_helper drift: {components.get('browser_helper')}")
components['browser_helper'] = '1.6.5'
p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
