#!/usr/bin/env bash
set -euo pipefail
: "${WRITE_TOKEN:?}" "${REPO:?}" "${BRANCH:?}" "${BASE_SHA:?}"
echo 'MAIN_WRITE_USED=NO RELEASE_USED=NO DISTRIBUTION_USED=NO PRODUCTION_WRITE_USED=NO STATIC_WRITE_USED=NO ONLINE_WRITE_USED=NO'
rm -rf /tmp/vf-theme-preview-v4
git clone -q "https://x-access-token:${WRITE_TOKEN}@github.com/${REPO}.git" /tmp/vf-theme-preview-v4
cd /tmp/vf-theme-preview-v4
git checkout -q "$BRANCH"
test "$(git rev-parse HEAD)" = "$BASE_SHA"
python3 - <<'PY'
from pathlib import Path
shell=Path('src/inc/admin/admin-shell.php'); s=shell.read_text()
old="        'preview' => ['label' => '开始主题验收', 'form' => 'vf-theme-preview-form', 'data' => 'data-vf-preview-run'],"
assert s.count(old)==1, s.count(old); s=s.replace(old,"        'preview' => [],"); shell.write_text(s)
view=Path('src/inc/admin/views/preview.php'); v=view.read_text()
repls={
'选择页面、语言和优先断点后，由页头唯一主按钮启动。':'选择页面、语言和优先断点后，在“执行验收”步骤直接启动。',
'确认运行准备并启动页头主动作':'确认运行准备并开始主题验收',
}
for a,b in repls.items(): assert v.count(a)==1,(a,v.count(a)); v=v.replace(a,b)
needle='''      <div class="vf-preview-v510__scope-facts" aria-label="本轮覆盖范围">'''
assert v.count(needle)==1
insert='''      <div class="vf-preview-v510__run-action" aria-label="开始主题验收">
        <span><strong>准备完成后从这里启动</strong><small>只运行你刚选择的范围；不会自动把本地或代码级通过记成线上最终通过。</small></span>
        <button type="submit" form="vf-theme-preview-form" class="button button-primary" data-vf-preview-run>开始主题验收</button>
      </div>
'''
v=v.replace(needle,insert+needle); view.write_text(v)
css=Path('src/assets/css/admin/pages/preview/admin-page-preview.css'); c=css.read_text(); marker='/* S01 Preview V4 in-context run action */'; assert marker not in c
c+='''\n\n/* S01 Preview V4 in-context run action */
.vf-theme-admin .vf-preview-v510__run-action{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:14px 16px;border:1px solid #c8d8ef;border-radius:14px;background:linear-gradient(135deg,#f8fbff,#fff);box-shadow:0 8px 24px rgba(37,99,235,.07)}
.vf-theme-admin .vf-preview-v510__run-action>span{display:grid;gap:2px;min-width:0}.vf-theme-admin .vf-preview-v510__run-action strong{color:#1e3a5f;font-size:13px}.vf-theme-admin .vf-preview-v510__run-action small{color:#64748b;line-height:1.5}.vf-theme-admin .vf-preview-v510__run-action>.button{flex:0 0 auto;min-width:180px;min-height:44px!important;margin:0!important}
@media(max-width:782px){.vf-theme-admin .vf-preview-v510__run-action{display:grid}.vf-theme-admin .vf-preview-v510__run-action>.button{width:100%;min-width:0;min-height:46px!important}}
'''; css.write_text(c)
PY
cat > tests/preview-workflow-v4-contract.php <<'PHP'
<?php
$root=dirname(__DIR__);$view=(string)file_get_contents($root.'/src/inc/admin/views/preview.php');$shell=(string)file_get_contents($root.'/src/inc/admin/admin-shell.php');$css=(string)file_get_contents($root.'/src/assets/css/admin/pages/preview/admin-page-preview.css');
$checks=['run_action'=>str_contains($view,'class="vf-preview-v510__run-action"'),'single'=>substr_count($view,'data-vf-preview-run')===1,'form_owner'=>str_contains($view,'form="vf-theme-preview-form" class="button button-primary" data-vf-preview-run'),'copy'=>str_contains($view,'在“执行验收”步骤直接启动')&&str_contains($view,'确认运行准备并开始主题验收'),'header_removed'=>str_contains($shell,"'preview' => [],")&&!str_contains($shell,"'preview' => ['label' => '开始主题验收'"),'boundary'=>str_contains($view,'不会自动把本地或代码级通过记成线上最终通过'),'mobile'=>str_contains($css,'.vf-preview-v510__run-action>.button{width:100%')];foreach($checks as $n=>$ok){if(!$ok){fwrite(STDERR,"FAIL_PREVIEW_V4_$n\n");exit(1);}}echo "PASS_THEME_PREVIEW_WORKFLOW_V4\n";
PHP
find src -type f -name '*.php' -print0 | xargs -0 -n1 php -l >/dev/null
php tests/preview-workflow-v4-contract.php
php tests/preview-human-language-followup-contract.php
php tests/final-admin-human-closure-contract.php
php tests/deep-admin-human-language-contract.php
php tests/workbench-primary-action-contract.php
php tests/update-center-human-language-contract.php
php tests/update-refresh-policy-contract.php
php tests/visible-console-v2-contract.php
git add -N tests/preview-workflow-v4-contract.php
mapfile -t changed < <(git diff --name-only "$BASE_SHA" -- | sort)
expected=('src/assets/css/admin/pages/preview/admin-page-preview.css' 'src/inc/admin/admin-shell.php' 'src/inc/admin/views/preview.php' 'tests/preview-workflow-v4-contract.php')
printf '%s\n' "${changed[@]}" >/tmp/changed; printf '%s\n' "${expected[@]}"|sort >/tmp/expected; sort -o /tmp/changed /tmp/changed; diff -u /tmp/expected /tmp/changed
git config user.name VictorForge; git config user.email llhzx2018@gmail.com; git add "${expected[@]}"; git commit -m 'refine(S01-C01): start preview acceptance where readiness is shown'; git push -q origin "$BRANCH"
echo "THEME_PREVIEW_V4_HEAD=$(git rev-parse HEAD)"; echo 'PASS_S01_C01_PREVIEW_V4_CANDIDATE'