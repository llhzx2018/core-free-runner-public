#!/usr/bin/env bash
set -euo pipefail
: "${WRITE_TOKEN:?}" "${REPO:?}" "${BRANCH:?}" "${BASE_SHA:?}"
echo 'MAIN_WRITE_USED=NO RELEASE_USED=NO DISTRIBUTION_USED=NO PRODUCTION_WRITE_USED=NO STATIC_WRITE_USED=NO ONLINE_WRITE_USED=NO'
rm -rf /tmp/vf-theme-seo-v4
git clone -q "https://x-access-token:${WRITE_TOKEN}@github.com/${REPO}.git" /tmp/vf-theme-seo-v4
cd /tmp/vf-theme-seo-v4
git checkout -q "$BRANCH"
test "$(git rev-parse HEAD)" = "$BASE_SHA"
python3 - <<'PY'
from pathlib import Path
shell=Path('src/inc/admin/admin-shell.php'); s=shell.read_text()
old="        'seo' => ['label' => '保存并运行技术 SEO 检查', 'form' => 'vf-theme-seo-form', 'data' => 'data-vf-seo-save'],"
assert s.count(old)==1, s.count(old); s=s.replace(old,"        'seo' => [],"); shell.write_text(s)
view=Path('src/inc/admin/views/seo.php'); v=view.read_text()
needle='''    <nav class="vf-seo-workflow" data-vf-seo-workflow data-vf-admin-workflow="seo" aria-label="技术 SEO 设置流程">'''
assert v.count(needle)==1
insert='''    <section class="vf-seo-save-dock" data-vf-seo-save-dock aria-label="技术 SEO 保存操作">
      <div><span>技术 SEO · <b data-vf-seo-dock-route-count><?php echo esc_html((string)count($policy)); ?></b> 条公开路由</span><strong><?php echo esc_html($runtime_ok?'当前正式配置已被路由、Head 与静态消费者读取。':'修改后保存并运行技术 SEO 检查，再处理失败消费者。'); ?></strong></div>
      <button type="submit" class="button button-primary" data-vf-seo-save>保存并运行技术 SEO 检查</button>
    </section>

'''
v=v.replace(needle,insert+needle); view.write_text(v)
css=Path('src/assets/css/admin/pages/seo/admin-page-seo.css'); c=css.read_text(); marker='/* S01 SEO V4 persistent save dock */'; assert marker not in c
c+='''\n\n/* S01 SEO V4 persistent save dock */
.vf-theme-admin .vf-seo-save-dock{position:sticky;bottom:12px;z-index:24;display:flex;align-items:center;justify-content:space-between;gap:18px;margin:0 0 14px;padding:12px 14px;border:1px solid #c8d8ef;border-radius:14px;background:rgba(255,255,255,.96);box-shadow:0 14px 34px rgba(15,23,42,.14);backdrop-filter:blur(10px)}
.vf-theme-admin .vf-seo-save-dock>div{display:grid;gap:2px;min-width:0}.vf-theme-admin .vf-seo-save-dock>div>span{color:#2563eb;font-size:10px;font-weight:900;letter-spacing:.04em}.vf-theme-admin .vf-seo-save-dock>div>strong{overflow:hidden;color:#475569;font-size:12px;line-height:1.45;text-overflow:ellipsis;white-space:nowrap}.vf-theme-admin .vf-seo-save-dock>.button{flex:0 0 auto;min-width:230px;min-height:44px!important;margin:0!important}
.vf-theme-admin .vf-seo-page[data-vf-seo-dirty="1"] .vf-seo-save-dock{border-color:#f0c36b;box-shadow:0 14px 34px rgba(180,83,9,.14)}.vf-theme-admin .vf-seo-page[data-vf-seo-dirty="1"] .vf-seo-save-dock>div>span{color:#b45309}
@media(max-width:782px){.vf-theme-admin .vf-seo-save-dock{bottom:8px;display:grid;gap:10px;padding:11px}.vf-theme-admin .vf-seo-save-dock>div>strong{white-space:normal}.vf-theme-admin .vf-seo-save-dock>.button{width:100%;min-width:0;min-height:46px!important}}
'''; css.write_text(c)
PY
cat > tests/seo-workflow-v4-contract.php <<'PHP'
<?php
$root=dirname(__DIR__);$view=(string)file_get_contents($root.'/src/inc/admin/views/seo.php');$shell=(string)file_get_contents($root.'/src/inc/admin/admin-shell.php');$css=(string)file_get_contents($root.'/src/assets/css/admin/pages/seo/admin-page-seo.css');
$checks=['dock'=>str_contains($view,'class="vf-seo-save-dock"')&&str_contains($view,'data-vf-seo-save-dock'),'single'=>substr_count($view,'data-vf-seo-save>')===1,'label'=>str_contains($view,'保存并运行技术 SEO 检查'),'header_removed'=>str_contains($shell,"'seo' => [],")&&!str_contains($shell,"'seo' => ['label' => '保存并运行技术 SEO 检查'"),'dirty'=>str_contains($css,'.vf-seo-page[data-vf-seo-dirty="1"] .vf-seo-save-dock'),'mobile'=>str_contains($css,'.vf-seo-save-dock>.button{width:100%')];foreach($checks as $n=>$ok){if(!$ok){fwrite(STDERR,"FAIL_SEO_V4_$n\n");exit(1);}}echo "PASS_THEME_SEO_WORKFLOW_V4\n";
PHP
find src -type f -name '*.php' -print0 | xargs -0 -n1 php -l >/dev/null
php tests/seo-workflow-v4-contract.php
php tests/final-admin-human-closure-contract.php
php tests/deep-admin-human-language-contract.php
php tests/workbench-primary-action-contract.php
php tests/update-center-human-language-contract.php
php tests/update-refresh-policy-contract.php
php tests/visible-console-v2-contract.php
git add -N tests/seo-workflow-v4-contract.php
mapfile -t changed < <(git diff --name-only "$BASE_SHA" -- | sort)
expected=('src/assets/css/admin/pages/seo/admin-page-seo.css' 'src/inc/admin/admin-shell.php' 'src/inc/admin/views/seo.php' 'tests/seo-workflow-v4-contract.php')
printf '%s\n' "${changed[@]}" >/tmp/changed; printf '%s\n' "${expected[@]}"|sort >/tmp/expected; sort -o /tmp/changed /tmp/changed; diff -u /tmp/expected /tmp/changed
git config user.name VictorForge; git config user.email llhzx2018@gmail.com; git add "${expected[@]}"; git commit -m 'refine(S01-C01): keep SEO verification action in reach'; git push -q origin "$BRANCH"
echo "THEME_SEO_V4_HEAD=$(git rev-parse HEAD)"; echo 'PASS_S01_C01_SEO_V4_CANDIDATE'