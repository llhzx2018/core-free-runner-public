#!/usr/bin/env python3
from pathlib import Path
import re, sys

root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path.cwd()

def read(rel): return (root/rel).read_text(encoding='utf-8')
def write(rel,s): (root/rel).write_text(s,encoding='utf-8')
def one(rel,old,new):
    s=read(rel); n=s.count(old)
    if n!=1: raise SystemExit(f'{rel}: expected one sentinel, got {n}: {old[:90]!r}')
    write(rel,s.replace(old,new,1))

write('VERSION','2.5.3\n')

# Production regression: settings still referenced removed UpdateContract::PRIMARY_KEY_ID.
s=read('public/api.php')
pat=re.compile(r"(?P<indent>[ \t]*)'update_trust'\s*=>\s*\(function\s*\(\):\s*array\s*\{.*?UpdateContract::PRIMARY_KEY_ID;.*?\}\)\(\),",re.S)
m=pat.search(s)
if not m: raise SystemExit('public/api.php: obsolete update_trust block not found')
i=m.group('indent')
block=(i+"'update_trust' => (function (): array {\n"
       +i+"    $label = 'core-updates + GitHub Release';\n"
       +i+"    $env = \\VFInfra\\Core\\Update\\UpdateContract::READ_TOKEN_ENV;\n"
       +i+"    $value = getenv($env);\n"
       +i+"    if ($value === false || trim((string) $value) === '') {\n"
       +i+"        $value = $_ENV[$env] ?? ($_SERVER[$env] ?? '');\n"
       +i+"    }\n"
       +i+"    $ready = trim((string) $value) !== '';\n"
       +i+"    return ['mode' => $label, 'key_ids' => $ready ? [$label] : [], 'required_key_id' => $label, 'ready' => $ready];\n"
       +i+"})(),")
s=s[:m.start()]+block+s[m.end():]
write('public/api.php',s)

# Update page semantics must describe the unified release source, not the retired static signing key.
one('public/assets/app.js',
    "const updateTrust = payload.update_trust || { key_ids: [], required_key_id: 'vf-release-2026-01', ready: false };",
    "const updateTrust = payload.update_trust || { mode: 'core-updates + GitHub Release', key_ids: [], required_key_id: 'core-updates + GitHub Release', ready: false };")
one('public/assets/app.js',
    "const trustReady = (updateTrust.key_ids || []).includes(updateTrust.required_key_id);",
    "const trustReady = updateTrust.ready === true || (updateTrust.key_ids || []).includes(updateTrust.required_key_id);")
one('public/assets/app.js',
    "${trustReady ? '数字签名验证已就绪' : '发布公钥尚未绑定'}",
    "${trustReady ? '统一发布源验证已就绪' : '统一私有读取凭据未就绪'}")
one('public/assets/app.js',
    "${trustReady ? `${escapeHtml(updateTrust.required_key_id || 'VF Release Key')} 已绑定。` : `缺少 ${escapeHtml(updateTrust.required_key_id || 'VF Release Key')} 时更新会安全阻断。`}",
    "${trustReady ? `更新源 ${escapeHtml(updateTrust.mode || updateTrust.required_key_id || 'core-updates + GitHub Release')} 已就绪。` : `统一更新源私有读取凭据未就绪时，更新会安全阻断；不会影响现有业务。`}")

# Maintenance CSP/UI: nonce the existing stylesheet and remove inline style attributes.
one('public/maintenance.php',"require_once __DIR__ . '/bootstrap.php';\nWeb::headers();",
    "require_once __DIR__ . '/bootstrap.php';\n$nonce = rtrim(strtr(base64_encode(random_bytes(24)), '+/', '-_'), '=');\nWeb::headers($nonce);")
one('public/maintenance.php','<title>VF Infra · 系统维护</title><style>',
    '<title>VF Infra · 系统维护</title><style nonce="<?=htmlspecialchars($nonce, ENT_QUOTES, \'UTF-8\')?>">')
one('public/maintenance.php','@media(max-width:640px){body{padding:22px 10px}.head{display:block}.back{margin-top:14px}.card{padding:18px}.button{width:100%}}',
    '.footer{padding:18px;text-align:center;color:#91a0a7;font-size:12px}@media(max-width:640px){body{padding:22px 10px}.head{display:block}.back{margin-top:14px}.card{padding:18px}.button{width:100%}}')
one('public/maintenance.php','<footer style="padding:18px;text-align:center;color:#91a0a7;font-size:12px">','<footer class="footer">')

# Fail-safe update errors must not require undeclared mbstring.
one('src/app/Core/Update/UpdateManifestService.php','return mb_substr($m,0,180);','return substr($m,0,180);')
one('src/app/Core/Update/UpdateRepositoryClient.php','return mb_substr($v,0,120);','return substr($v,0,120);')

# Atomic template: preserve engine, fix error fallback and make CSP/UI actually render.
one('scripts/build-v251-maintenance-release.py',"return $m!==''?mb_substr($m,0,300):'未知错误';","return $m!==''?substr($m,0,300):'未知错误';")
one('scripts/build-v251-maintenance-release.py',"$cls='state-'.$state;?><!doctype html>",
    "$cspNonce=rtrim(strtr(base64_encode(random_bytes(24)),'+/','-_'),'=');if(class_exists('Web')){Web::headers($cspNonce);}else{header(\"Content-Security-Policy: default-src 'self'; style-src 'nonce-\".$cspNonce.\"'; script-src 'none'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'\");header('Cache-Control: no-store, private');}$cls='state-'.$state;?><!doctype html>")
one('scripts/build-v251-maintenance-release.py','<title>VF Infra V2.5.1 原子升级</title><style>',
    '<title>VF Infra V2.5.1 原子升级</title><style nonce="<?=vfi251_e($cspNonce)?>">')
one('scripts/build-v251-maintenance-release.py','<body><main>','<body class="<?=vfi251_e($cls)?>"><main>')
one('scripts/build-v251-maintenance-release.py',
    'body{{font-family:system-ui,"Microsoft YaHei",sans-serif;background:#f3f7f5;color:#17211d;margin:0}}main{{max-width:780px;margin:50px auto;padding:28px;background:#fff;border:1px solid #dbe6e1;border-radius:16px}}.button{{display:inline-block;padding:12px 18px;border:0;border-radius:10px;background:#079a75;color:#fff;text-decoration:none;font-weight:700}}p,li{{color:#65756d}}.err{{color:#b62c25}}',
    ':root{{font-family:"Segoe UI Variable Text","Segoe UI","Microsoft YaHei UI","Microsoft YaHei",system-ui,sans-serif;color:#173029;background:#f4f8f6;--brand:#079a75;--muted:#667c74;--line:#dce8e2;--soft:#edf8f3;--danger:#b62c25}}*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;padding:44px 18px;background:linear-gradient(180deg,#eef7f3 0,#f7faf8 45%,#f4f8f6 100%);font-size:15px;line-height:1.65}}main{{max-width:760px;margin:0 auto;padding:32px;background:#fff;border:1px solid var(--line);border-radius:20px;box-shadow:0 18px 50px rgba(31,72,57,.08)}}main:before{{content:"VF";display:grid;place-items:center;width:42px;height:42px;margin-bottom:22px;border-radius:12px;background:var(--brand);color:#fff;font-weight:800}}small{{display:inline-flex;padding:5px 10px;border-radius:999px;background:var(--soft);color:#26715d;font-weight:700}}h1{{margin:14px 0 8px;font-size:30px;line-height:1.2}}p{{color:var(--muted)}}ul{{margin:22px 0;padding:0;list-style:none;border-top:1px solid var(--line)}}li{{padding:11px 4px;border-bottom:1px solid var(--line);color:#425a52}}.button{{display:inline-flex;min-height:44px;align-items:center;justify-content:center;padding:0 18px;border:0;border-radius:11px;background:var(--brand);color:#fff;text-decoration:none;font-weight:750;cursor:pointer}}.button:hover{{filter:brightness(.94)}}.err{{padding:12px 14px;border-radius:10px;background:#fff1f0;color:var(--danger)}}.state-success main{{border-top:4px solid var(--brand)}}.state-failed main{{border-top:4px solid var(--danger)}}@media(max-width:640px){{body{{padding:22px 10px}}main{{padding:22px;border-radius:16px}}h1{{font-size:25px}}.button{{width:100%}}}}')

# Release tree metadata.
one('scripts/build-release-tree.py',"maintenance_versions={'2.5.1','2.5.2'}","maintenance_versions={'2.5.1','2.5.2','2.5.3'}")
one('scripts/build-release-tree.py',
    "'V2.5.2 replaces the legacy online discovery source with core-updates + GitHub Release while preserving the proven Backup/Atomic/Rollback/Maintenance execution layer.' if version=='2.5.2' else 'Adds authenticated manual Atomic upload and Production Source Manifest export through /maintenance.php.',",
    "('V2.5.3 hotfixes the Settings unified-update trust contract, update error fallback, and Maintenance/Atomic CSP rendering without changing Schema or business authority.' if version=='2.5.3' else ('V2.5.2 replaces the legacy online discovery source with core-updates + GitHub Release while preserving the proven Backup/Atomic/Rollback/Maintenance execution layer.' if version=='2.5.2' else 'Adds authenticated manual Atomic upload and Production Source Manifest export through /maintenance.php.')),")

# Create V2.5.3 builder from V2.5.2 builder pattern.
s=read('scripts/build-v252-update-release.py')
if "TARGET='2.5.2'\nSOURCE='2.5.1'" not in s: raise SystemExit('V252 builder identity sentinel missing')
s=s.replace("TARGET='2.5.2'\nSOURCE='2.5.1'","TARGET='2.5.3'\nSOURCE='2.5.2'",1)
old="""PAYLOAD_PATHS=[
    'VERSION.txt',
    'app/Core/Update/UpdateSourceInterface.php',
    'app/Core/Update/UpdateContract.php',
    'app/Core/Update/UpdateRepositoryClient.php',
    'app/Core/Update/UpdateManifestService.php',
    'release-manifest.json',
]"""
new="""PAYLOAD_PATHS=[
    'VERSION.txt',
    'api.php',
    'assets/app.js',
    'maintenance.php',
    'app/Core/Update/UpdateRepositoryClient.php',
    'app/Core/Update/UpdateManifestService.php',
    'release-manifest.json',
]"""
if old not in s: raise SystemExit('V252 builder payload sentinel missing')
s=s.replace(old,new,1)
s=s.replace("source=source.replace('vfi251','vfi252').replace('atomic_251','atomic_252')","source=source.replace('vfi251','vfi253').replace('atomic_251','atomic_253')",1)
s=s.replace('build-v252-generated.py','build-v253-generated.py').replace('p04-v252-builder-','p04-v253-builder-')
# Once generic target replacement runs, rewrite only the release description.
needle="source=source.replace('__P04_TARGET__',TARGET).replace('__P04_SOURCE__',SOURCE)"
if needle not in s: raise SystemExit('V252 generated-source sentinel missing')
s=s.replace(needle,needle+"\nsource=source.replace('V2.5.3 只增加正式维护通道，Schema 与业务模型保持不变。','V2.5.3 修复统一更新设置与维护体验；Schema 与业务模型保持不变。')",1)
write('scripts/build-v253-update-release.py',s)

# Changelog.
s=read('CHANGELOG.md'); marker='# 变更记录\n'
if marker not in s: raise SystemExit('CHANGELOG marker missing')
entry="""

## [2.5.3] - Hotfix · Settings / Maintenance UI

- 修复 V2.5.2 设置工作区仍引用已移除 `UpdateContract::PRIMARY_KEY_ID` 导致的 Production 500。
- 设置页发布信任语义改为 `core-updates + GitHub Release`，只显示统一私有读取凭据是否就绪，不暴露 Token。
- 修复 `/maintenance.php` 与 Atomic repair 内联样式被 CSP 拦截的问题，统一使用 nonce。
- Update Core 错误清理不再依赖未声明的 mbstring；更新源失败时必须安全降级而不是拖垮设置页。
- Schema 保持 14；不修改 Domain / Provider / VPS / Cron / RDAP 业务模型，不增加 Provider 写权限。
"""
write('CHANGELOG.md',s.replace(marker,marker+entry,1))

# Strong patch assertions.
checks={
 'public/api.php':['core-updates + GitHub Release'],
 'public/assets/app.js':['统一发布源验证已就绪'],
 'public/maintenance.php':['Web::headers($nonce)','<style nonce='],
 'scripts/build-v251-maintenance-release.py':['$cspNonce','style nonce='],
}
for rel,needles in checks.items():
    t=read(rel)
    for x in needles:
        if x not in t: raise SystemExit(f'{rel}: missing postcondition {x}')
for rel in ['public/api.php','src/app/Core/Update/UpdateManifestService.php','src/app/Core/Update/UpdateRepositoryClient.php']:
    if 'UpdateContract::PRIMARY_KEY_ID' in read(rel): raise SystemExit(f'{rel}: retired PRIMARY_KEY_ID remains')
if 'mb_substr' in read('src/app/Core/Update/UpdateManifestService.php') or 'mb_substr' in read('src/app/Core/Update/UpdateRepositoryClient.php'):
    raise SystemExit('Update Core still depends on mb_substr')
print('V253_HOTFIX_PATCH=PASS')
