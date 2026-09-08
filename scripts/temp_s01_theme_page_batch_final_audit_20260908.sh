#!/usr/bin/env bash
set -euo pipefail
: "${READ_TOKEN:?}" "${REPO:?}" "${HEAD_SHA:?}" "${MAIN_SHA:?}"
echo 'AUDIT_MODE=READ_ONLY MAIN_WRITE_USED=NO RELEASE_USED=NO DISTRIBUTION_USED=NO PRODUCTION_WRITE_USED=NO STATIC_WRITE_USED=NO ONLINE_WRITE_USED=NO'
rm -rf /tmp/vf-theme-page-batch-audit
git clone -q "https://x-access-token:${READ_TOKEN}@github.com/${REPO}.git" /tmp/vf-theme-page-batch-audit
cd /tmp/vf-theme-page-batch-audit
git checkout -q "$HEAD_SHA"
test "$(git rev-parse HEAD)" = "$HEAD_SHA"
test "$(cat VERSION | tr -d '\r\n')" = '1.35.21'
grep -q 'Version: 1.35.21' src/style.css
git diff --check "$MAIN_SHA" "$HEAD_SHA"
python3 - <<'PY'
from pathlib import Path
shell=Path('src/inc/admin/admin-shell.php').read_text()
for tab in ['overview','brand','layout','navigation','render','seo','preview','recovery']:
    needle=f"        '{tab}' => [],"
    assert shell.count(needle)==1,(tab,shell.count(needle))
checks={
'brand':('src/inc/admin/views/brand.php','data-vf-brand-save',1),
'layout':('src/inc/admin/views/layout.php','class="button button-primary" data-vf-layout-save',1),
'navigation':('src/inc/admin/views/navigation.php','class="button button-primary" data-vf-navigation-save',1),
'render':('src/inc/admin/views/render.php','data-vf-render-save',1),
'seo':('src/inc/admin/views/seo.php','data-vf-seo-save>',1),
'preview':('src/inc/admin/views/preview.php','data-vf-preview-run',1),
'recovery':('src/inc/admin/views/recovery-v510.php','data-vf-recovery-primary',1),
}
for name,(path,needle,count) in checks.items():
    text=Path(path).read_text(); assert text.count(needle)==count,(name,text.count(needle),count)
overview=Path('src/inc/admin/views/tabs/overview.php').read_text(); assert overview.count('button-primary')==1
a=Path('src/inc/admin/views/preview.php').read_text(); assert '页头主动作' not in a and '在“执行验收”步骤直接启动' in a
nav=Path('src/inc/admin/views/navigation.php').read_text(); assert '页面顶部“保存并验证前台”' not in nav
recovery_js=Path('src/assets/js/admin/admin-recovery-v510.js').read_text(); assert "restoreConfirm?.value.trim() === 'RESTORE'" in recovery_js and 'disabled = !(selected && confirmed);' in recovery_js
update=Path('src/inc/update/class-vf-wp-update-admin-v1.php').read_text(); assert '配置更新凭证' in update and '先配置更新凭证，再检查或安装此组件的更新。' in update
print('PASS_THEME_PAGE_BATCH_STRUCTURE_AUDIT')
PY
find src -type f -name '*.php' -print0 | xargs -0 -n1 php -l >/dev/null
for js in src/assets/js/admin/admin-brand.js src/assets/js/admin/admin-layout.js src/assets/js/admin/admin-navigation.js src/assets/js/admin/admin-preview.js src/assets/js/admin/admin-recovery-v510.js; do node --check "$js" >/dev/null; done
for t in \
 tests/update-center-human-language-contract.php \
 tests/workbench-primary-action-contract.php \
 tests/final-admin-human-closure-contract.php \
 tests/deep-admin-human-language-contract.php \
 tests/layout-workflow-v4-contract.php \
 tests/navigation-workflow-v4-contract.php \
 tests/render-workflow-v4-contract.php \
 tests/render-settings-human-language-contract.php \
 tests/seo-workflow-v4-contract.php \
 tests/preview-workflow-v4-contract.php \
 tests/preview-human-language-followup-contract.php \
 tests/recovery-workflow-v4-contract.php \
 tests/recovery-human-language-closure-contract.php \
 tests/update-refresh-policy-contract.php \
 tests/visible-console-v2-contract.php; do php "$t"; done
mapfile -t changed < <(git diff --name-only "$MAIN_SHA" "$HEAD_SHA" | sort)
expected=(
'src/assets/css/admin/admin-update-center.css'
'src/assets/css/admin/pages/brand/admin-page-brand.css'
'src/assets/css/admin/pages/maintenance/recovery/admin-page-recovery-v510.css'
'src/assets/css/admin/pages/navigation/admin-page-navigation.css'
'src/assets/css/admin/pages/page-structure/admin-page-layout.css'
'src/assets/css/admin/pages/preview/admin-page-preview.css'
'src/assets/css/admin/pages/render/admin-page-render.css'
'src/assets/css/admin/pages/seo/admin-page-seo.css'
'src/assets/css/admin/pages/workbench/admin-page-workbench.css'
'src/inc/admin/admin-shell.php'
'src/inc/admin/views/brand.php'
'src/inc/admin/views/layout.php'
'src/inc/admin/views/navigation.php'
'src/inc/admin/views/preview.php'
'src/inc/admin/views/recovery-v510.php'
'src/inc/admin/views/render.php'
'src/inc/admin/views/seo.php'
'src/inc/admin/views/tabs/overview.php'
'src/inc/update/class-vf-wp-update-admin-v1.php'
'tests/final-admin-human-closure-contract.php'
'tests/layout-workflow-v4-contract.php'
'tests/navigation-workflow-v4-contract.php'
'tests/preview-workflow-v4-contract.php'
'tests/recovery-workflow-v4-contract.php'
'tests/render-workflow-v4-contract.php'
'tests/seo-workflow-v4-contract.php'
'tests/update-center-human-language-contract.php'
'tests/workbench-primary-action-contract.php'
)
printf '%s\n' "${changed[@]}" >/tmp/changed; printf '%s\n' "${expected[@]}"|sort >/tmp/expected; diff -u /tmp/expected /tmp/changed
echo "AUDITED_HEAD=$HEAD_SHA"
echo 'PASS_S01_C01_ADMIN_PAGE_BATCH_FINAL_AUDIT'