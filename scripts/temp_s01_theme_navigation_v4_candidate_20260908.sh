#!/usr/bin/env bash
set -euo pipefail
: "${WRITE_TOKEN:?}" "${REPO:?}" "${BRANCH:?}" "${BASE_SHA:?}"
echo 'MAIN_WRITE_USED=NO RELEASE_USED=NO DISTRIBUTION_USED=NO PRODUCTION_WRITE_USED=NO STATIC_WRITE_USED=NO ONLINE_WRITE_USED=NO'
rm -rf /tmp/vf-theme-navigation-v4
git clone -q "https://x-access-token:${WRITE_TOKEN}@github.com/${REPO}.git" /tmp/vf-theme-navigation-v4
cd /tmp/vf-theme-navigation-v4
git checkout -q "$BRANCH"
test "$(git rev-parse HEAD)" = "$BASE_SHA"
python3 - <<'PY'
from pathlib import Path
shell=Path('src/inc/admin/admin-shell.php')
s=shell.read_text()
old="        'navigation' => ['label' => '保存导航草稿', 'form' => 'vf-theme-navigation-form', 'data' => 'data-vf-navigation-save'],"
assert s.count(old)==1, s.count(old)
s=s.replace(old,"        'navigation' => [],")
shell.write_text(s)
view=Path('src/inc/admin/views/navigation.php')
v=view.read_text()
needle='''    <nav class="vf-navigation-workflow" data-vf-navigation-workflow data-vf-admin-workflow="navigation" aria-label="导航与页脚设置流程">'''
assert v.count(needle)==1
insert='''    <section class="vf-navigation-save-dock" data-vf-navigation-save-dock aria-label="导航保存操作">
      <div><span>当前导航 · <b data-vf-navigation-dock-bound><?php echo esc_html((string)$selected_count); ?></b>/6 已绑定</span><strong><?php echo esc_html($runtime_ok?'当前保存结果已同步桌面、移动端和页脚。':'修改后保存并验证桌面、移动端和页脚。'); ?></strong></div>
      <button type="submit" class="button button-primary" data-vf-navigation-save>保存并验证前台</button>
    </section>

'''
v=v.replace(needle,insert+needle)
oldcopy='页面顶部“保存并验证前台”是唯一主动作；保存后这里只展示需要处理的失败项。'
newcopy='页面下方常驻保存区是唯一主动作；保存后这里只展示需要处理的失败项。'
assert v.count(oldcopy)==1
v=v.replace(oldcopy,newcopy)
view.write_text(v)
css=Path('src/assets/css/admin/pages/navigation/admin-page-navigation.css')
c=css.read_text()
marker='/* S01 Navigation V4 persistent save dock */'
assert marker not in c
c+='''\n\n/* S01 Navigation V4 persistent save dock */
.vf-theme-admin .vf-navigation-save-dock{position:sticky;bottom:12px;z-index:24;display:flex;align-items:center;justify-content:space-between;gap:18px;margin:0 0 14px;padding:12px 14px;border:1px solid #c8d8ef;border-radius:14px;background:rgba(255,255,255,.96);box-shadow:0 14px 34px rgba(15,23,42,.14);backdrop-filter:blur(10px)}
.vf-theme-admin .vf-navigation-save-dock>div{display:grid;gap:2px;min-width:0}.vf-theme-admin .vf-navigation-save-dock>div>span{color:#2563eb;font-size:10px;font-weight:900;letter-spacing:.04em}.vf-theme-admin .vf-navigation-save-dock>div>strong{overflow:hidden;color:#475569;font-size:12px;line-height:1.45;text-overflow:ellipsis;white-space:nowrap}.vf-theme-admin .vf-navigation-save-dock>.button{flex:0 0 auto;min-width:190px;min-height:44px!important;margin:0!important}
.vf-theme-admin .vf-navigation-page[data-vf-navigation-dirty="1"] .vf-navigation-save-dock{border-color:#f0c36b;box-shadow:0 14px 34px rgba(180,83,9,.14)}.vf-theme-admin .vf-navigation-page[data-vf-navigation-dirty="1"] .vf-navigation-save-dock>div>span{color:#b45309}
@media(max-width:782px){.vf-theme-admin .vf-navigation-save-dock{bottom:8px;display:grid;gap:10px;padding:11px}.vf-theme-admin .vf-navigation-save-dock>div>strong{white-space:normal}.vf-theme-admin .vf-navigation-save-dock>.button{width:100%;min-width:0;min-height:46px!important}}
'''
css.write_text(c)
PY
cat > tests/navigation-workflow-v4-contract.php <<'PHP'
<?php
$root=dirname(__DIR__);$view=(string)file_get_contents($root.'/src/inc/admin/views/navigation.php');$shell=(string)file_get_contents($root.'/src/inc/admin/admin-shell.php');$css=(string)file_get_contents($root.'/src/assets/css/admin/pages/navigation/admin-page-navigation.css');
$checks=[
'dock'=>str_contains($view,'class="vf-navigation-save-dock"')&&str_contains($view,'data-vf-navigation-save-dock'),
'single'=>substr_count($view,'class="button button-primary" data-vf-navigation-save')===1,
'header_removed'=>str_contains($shell,"'navigation' => [],")&&!str_contains($shell,"'navigation' => ['label' => '保存导航草稿'"),
'result_copy'=>str_contains($view,'页面下方常驻保存区是唯一主动作'),
'sticky'=>str_contains($css,'.vf-navigation-save-dock{position:sticky;bottom:12px'),
'mobile'=>str_contains($css,'.vf-navigation-save-dock>.button{width:100%'),
];foreach($checks as $n=>$ok){if(!$ok){fwrite(STDERR,"FAIL_NAV_V4_$n\n");exit(1);}}echo "PASS_THEME_NAVIGATION_WORKFLOW_V4\n";
PHP
find src -type f -name '*.php' -print0 | xargs -0 -n1 php -l >/dev/null
php tests/navigation-workflow-v4-contract.php
php tests/final-admin-human-closure-contract.php
php tests/deep-admin-human-language-contract.php
php tests/workbench-primary-action-contract.php
php tests/update-center-human-language-contract.php
php tests/update-refresh-policy-contract.php
php tests/visible-console-v2-contract.php
git add -N tests/navigation-workflow-v4-contract.php
mapfile -t changed < <(git diff --name-only "$BASE_SHA" -- | sort)
expected=('src/assets/css/admin/pages/navigation/admin-page-navigation.css' 'src/inc/admin/admin-shell.php' 'src/inc/admin/views/navigation.php' 'tests/navigation-workflow-v4-contract.php')
printf '%s\n' "${changed[@]}" >/tmp/changed; printf '%s\n' "${expected[@]}"|sort >/tmp/expected; sort -o /tmp/changed /tmp/changed; diff -u /tmp/expected /tmp/changed
git config user.name VictorForge; git config user.email llhzx2018@gmail.com
git add "${expected[@]}"; git commit -m 'refine(S01-C01): keep navigation save action in reach'; git push -q origin "$BRANCH"
echo "THEME_NAVIGATION_V4_HEAD=$(git rev-parse HEAD)"; echo 'PASS_S01_C01_NAVIGATION_V4_CANDIDATE'