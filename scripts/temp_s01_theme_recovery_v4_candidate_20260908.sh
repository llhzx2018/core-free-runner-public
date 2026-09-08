#!/usr/bin/env bash
set -euo pipefail
: "${WRITE_TOKEN:?}" "${REPO:?}" "${BRANCH:?}" "${BASE_SHA:?}"
echo 'MAIN_WRITE_USED=NO RELEASE_USED=NO DISTRIBUTION_USED=NO PRODUCTION_WRITE_USED=NO STATIC_WRITE_USED=NO ONLINE_WRITE_USED=NO'
rm -rf /tmp/vf-theme-recovery-v4
git clone -q "https://x-access-token:${WRITE_TOKEN}@github.com/${REPO}.git" /tmp/vf-theme-recovery-v4
cd /tmp/vf-theme-recovery-v4
git checkout -q "$BRANCH"
test "$(git rev-parse HEAD)" = "$BASE_SHA"
python3 - <<'PY'
from pathlib import Path
shell=Path('src/inc/admin/admin-shell.php'); s=shell.read_text()
old="        'recovery' => ['label' => '创建主题快照', 'type' => 'button', 'data' => 'data-vf-recovery-primary'],"
assert s.count(old)==1, s.count(old); s=s.replace(old,"        'recovery' => [],"); shell.write_text(s)
view=Path('src/inc/admin/views/recovery-v510.php'); v=view.read_text()
needle='''  <section id="vf-recovery-step-status" class="vf-recovery-status"'''
assert v.count(needle)==1
insert='''  <section class="vf-recovery-action-dock" data-vf-recovery-action-dock aria-label="当前维护步骤主操作">
    <div><span>当前步骤的唯一主操作</span><strong>导入与恢复只有在预检、选择和确认条件满足后才会启用。</strong></div>
    <button type="button" class="button button-primary" data-vf-recovery-primary>创建主题快照</button>
  </section>

'''
v=v.replace(needle,insert+needle); view.write_text(v)
css=Path('src/assets/css/admin/pages/maintenance/recovery/admin-page-recovery-v510.css'); c=css.read_text(); marker='/* S01 Recovery V4 dynamic action dock */'; assert marker not in c
c+='''\n\n/* S01 Recovery V4 dynamic action dock */
.vf-theme-admin .vf-recovery-action-dock{position:sticky;bottom:12px;z-index:24;display:flex;align-items:center;justify-content:space-between;gap:18px;margin:0 0 14px;padding:12px 14px;border:1px solid #c8d8ef;border-radius:14px;background:rgba(255,255,255,.97);box-shadow:0 14px 34px rgba(15,23,42,.14);backdrop-filter:blur(10px)}
.vf-theme-admin .vf-recovery-action-dock>div{display:grid;gap:2px;min-width:0}.vf-theme-admin .vf-recovery-action-dock>div>span{color:#2563eb;font-size:10px;font-weight:900;letter-spacing:.04em}.vf-theme-admin .vf-recovery-action-dock>div>strong{color:#475569;font-size:12px;line-height:1.45}.vf-theme-admin .vf-recovery-action-dock>.button{flex:0 0 auto;min-width:190px;min-height:44px!important;margin:0!important}.vf-theme-admin .vf-recovery-action-dock>.button:disabled{box-shadow:none!important;opacity:.55}
.vf-theme-admin .vf-recovery-page[data-vf-recovery-task="restore"] .vf-recovery-action-dock{border-color:#ead3c8}.vf-theme-admin .vf-recovery-page[data-vf-recovery-task="restore"] .vf-recovery-action-dock>div>span{color:#9f3d29}
@media(max-width:782px){.vf-theme-admin .vf-recovery-action-dock{bottom:8px;display:grid;gap:10px;padding:11px}.vf-theme-admin .vf-recovery-action-dock>.button{width:100%;min-width:0;min-height:46px!important}}
'''; css.write_text(c)
PY
cat > tests/recovery-workflow-v4-contract.php <<'PHP'
<?php
$root=dirname(__DIR__);$view=(string)file_get_contents($root.'/src/inc/admin/views/recovery-v510.php');$shell=(string)file_get_contents($root.'/src/inc/admin/admin-shell.php');$css=(string)file_get_contents($root.'/src/assets/css/admin/pages/maintenance/recovery/admin-page-recovery-v510.css');$js=(string)file_get_contents($root.'/src/assets/js/admin/admin-recovery-v510.js');
$checks=['dock'=>str_contains($view,'class="vf-recovery-action-dock"'),'single_primary'=>substr_count($view,'data-vf-recovery-primary')===1,'header_removed'=>str_contains($shell,"'recovery' => [],")&&!str_contains($shell,"'recovery' => ['label' => '创建主题快照'"),'dynamic_labels'=>str_contains($js,"status: {label: '创建主题快照'}")&&str_contains($js,"export: {label: '验证并导出当前配置'}")&&str_contains($js,"import: {label: '服务器预检配置'}")&&str_contains($js,"restore: {label: '恢复所选版本'}"),'restore_guard'=>str_contains($js,"restoreConfirm?.value.trim() === 'RESTORE'")&&str_contains($js,'disabled = !(selected && confirmed);'),'safety_copy'=>str_contains($view,'导入与恢复只有在预检、选择和确认条件满足后才会启用'),'sticky'=>str_contains($css,'.vf-recovery-action-dock{position:sticky;bottom:12px'),'mobile'=>str_contains($css,'.vf-recovery-action-dock>.button{width:100%')];foreach($checks as $n=>$ok){if(!$ok){fwrite(STDERR,"FAIL_RECOVERY_V4_$n\n");exit(1);}}echo "PASS_THEME_RECOVERY_WORKFLOW_V4\n";
PHP
find src -type f -name '*.php' -print0 | xargs -0 -n1 php -l >/dev/null
php tests/recovery-workflow-v4-contract.php
php tests/recovery-human-language-closure-contract.php
php tests/final-admin-human-closure-contract.php
php tests/deep-admin-human-language-contract.php
php tests/workbench-primary-action-contract.php
php tests/update-center-human-language-contract.php
php tests/update-refresh-policy-contract.php
php tests/visible-console-v2-contract.php
git add -N tests/recovery-workflow-v4-contract.php
mapfile -t changed < <(git diff --name-only "$BASE_SHA" -- | sort)
expected=('src/assets/css/admin/pages/maintenance/recovery/admin-page-recovery-v510.css' 'src/inc/admin/admin-shell.php' 'src/inc/admin/views/recovery-v510.php' 'tests/recovery-workflow-v4-contract.php')
printf '%s\n' "${changed[@]}" >/tmp/changed; printf '%s\n' "${expected[@]}"|sort >/tmp/expected; sort -o /tmp/changed /tmp/changed; diff -u /tmp/expected /tmp/changed
git config user.name VictorForge; git config user.email llhzx2018@gmail.com; git add "${expected[@]}"; git commit -m 'refine(S01-C01): keep recovery action beside active task'; git push -q origin "$BRANCH"
echo "THEME_RECOVERY_V4_HEAD=$(git rev-parse HEAD)"; echo 'PASS_S01_C01_RECOVERY_V4_CANDIDATE'