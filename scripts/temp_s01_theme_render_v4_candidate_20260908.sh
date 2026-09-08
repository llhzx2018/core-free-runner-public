#!/usr/bin/env bash
set -euo pipefail
: "${WRITE_TOKEN:?}" "${REPO:?}" "${BRANCH:?}" "${BASE_SHA:?}"
echo 'MAIN_WRITE_USED=NO RELEASE_USED=NO DISTRIBUTION_USED=NO PRODUCTION_WRITE_USED=NO STATIC_WRITE_USED=NO ONLINE_WRITE_USED=NO'
rm -rf /tmp/vf-theme-render-v4
git clone -q "https://x-access-token:${WRITE_TOKEN}@github.com/${REPO}.git" /tmp/vf-theme-render-v4
cd /tmp/vf-theme-render-v4
git checkout -q "$BRANCH"
test "$(git rev-parse HEAD)" = "$BASE_SHA"
python3 - <<'PY'
from pathlib import Path
shell=Path('src/inc/admin/admin-shell.php'); s=shell.read_text()
old="        'render' => ['label' => '保存渲染草稿', 'form' => 'vf-theme-render-form', 'data' => 'data-vf-render-save'],"
assert s.count(old)==1, s.count(old); s=s.replace(old,"        'render' => [],"); shell.write_text(s)
view=Path('src/inc/admin/views/render.php'); v=view.read_text()
old='''        <a class="button vf-render-preview-link" href="<?php echo esc_url(function_exists('vf_theme_admin_tab_url') ? vf_theme_admin_tab_url('preview') : admin_url('themes.php?page=vf-theme-modules&tab=preview')); ?>">打开前台预览</a>'''
assert v.count(old)==1
new='''        <div class="vf-render-side-actions" aria-label="页面显示保存与预览">
          <button type="submit" class="button button-primary" data-vf-render-save>保存并验证页面显示</button>
          <a class="button vf-render-preview-link" href="<?php echo esc_url(function_exists('vf_theme_admin_tab_url') ? vf_theme_admin_tab_url('preview') : admin_url('themes.php?page=vf-theme-modules&tab=preview')); ?>">打开前台预览</a>
        </div>'''
v=v.replace(old,new); view.write_text(v)
css=Path('src/assets/css/admin/pages/render/admin-page-render.css'); c=css.read_text(); marker='/* S01 Render V4 side action closure */'; assert marker not in c
c+='''\n/* S01 Render V4 side action closure */
.vf-theme-admin .vf-render-side-actions{display:grid;gap:8px;padding:12px;border:1px solid #c8d8ef;border-radius:14px;background:#fff;box-shadow:0 10px 28px rgba(15,23,42,.07)}.vf-theme-admin .vf-render-side-actions>.button{width:100%;min-height:44px!important;margin:0!important}.vf-theme-admin .vf-render-side-actions>.button-primary{order:0}.vf-theme-admin .vf-render-side-actions>.vf-render-preview-link{order:1}.vf-theme-admin .vf-render-page.is-dirty .vf-render-side-actions{border-color:#f0c36b;box-shadow:0 10px 28px rgba(180,83,9,.10)}
@media(max-width:900px){.vf-theme-admin .vf-render-side-actions{grid-template-columns:1fr 1fr}.vf-theme-admin .vf-render-side-actions>.button{min-height:46px!important}}@media(max-width:600px){.vf-theme-admin .vf-render-side-actions{grid-template-columns:1fr}}
'''; css.write_text(c)
PY
cat > tests/render-workflow-v4-contract.php <<'PHP'
<?php
$root=dirname(__DIR__);$view=(string)file_get_contents($root.'/src/inc/admin/views/render.php');$shell=(string)file_get_contents($root.'/src/inc/admin/admin-shell.php');$css=(string)file_get_contents($root.'/src/assets/css/admin/pages/render/admin-page-render.css');
$checks=['side_actions'=>str_contains($view,'class="vf-render-side-actions"'),'single'=>substr_count($view,'data-vf-render-save')===1,'label'=>str_contains($view,'保存并验证页面显示'),'header_removed'=>str_contains($shell,"'render' => [],")&&!str_contains($shell,"'render' => ['label' => '保存渲染草稿'"),'sticky_owner'=>str_contains($css,'.vf-render-side{position:sticky'),'mobile'=>str_contains($css,'.vf-render-side-actions{grid-template-columns:1fr}')];foreach($checks as $n=>$ok){if(!$ok){fwrite(STDERR,"FAIL_RENDER_V4_$n\n");exit(1);}}echo "PASS_THEME_RENDER_WORKFLOW_V4\n";
PHP
find src -type f -name '*.php' -print0 | xargs -0 -n1 php -l >/dev/null
php tests/render-workflow-v4-contract.php
php tests/render-settings-human-language-contract.php
php tests/final-admin-human-closure-contract.php
php tests/deep-admin-human-language-contract.php
php tests/workbench-primary-action-contract.php
php tests/update-center-human-language-contract.php
php tests/update-refresh-policy-contract.php
php tests/visible-console-v2-contract.php
git add -N tests/render-workflow-v4-contract.php
mapfile -t changed < <(git diff --name-only "$BASE_SHA" -- | sort)
expected=('src/assets/css/admin/pages/render/admin-page-render.css' 'src/inc/admin/admin-shell.php' 'src/inc/admin/views/render.php' 'tests/render-workflow-v4-contract.php')
printf '%s\n' "${changed[@]}" >/tmp/changed; printf '%s\n' "${expected[@]}"|sort >/tmp/expected; sort -o /tmp/changed /tmp/changed; diff -u /tmp/expected /tmp/changed
git config user.name VictorForge; git config user.email llhzx2018@gmail.com; git add "${expected[@]}"; git commit -m 'refine(S01-C01): place render save beside live summary'; git push -q origin "$BRANCH"
echo "THEME_RENDER_V4_HEAD=$(git rev-parse HEAD)"; echo 'PASS_S01_C01_RENDER_V4_CANDIDATE'