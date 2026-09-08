#!/usr/bin/env bash
set -Eeuo pipefail
: "${WRITE_TOKEN:?}" "${REPO:?}" "${BRANCH:?}" "${BASE_SHA:?}" "${MAIN_SHA:?}"
echo 'MAIN_WRITE_USED=NO RELEASE_USED=NO DISTRIBUTION_USED=NO PRODUCTION_WRITE_USED=NO STATIC_WRITE_USED=NO ONLINE_WRITE_USED=NO'
cp fixtures/s01_theme_brand_v4_append_20260907.css /tmp/s01_brand_v4.css
rm -rf /tmp/s01-theme-brand-v4
git clone -q "https://x-access-token:${WRITE_TOKEN}@github.com/${REPO}.git" /tmp/s01-theme-brand-v4
cd /tmp/s01-theme-brand-v4
git checkout -q "$BRANCH"
test "$(git rev-parse HEAD)" = "$BASE_SHA"
test "$(git rev-parse origin/main)" = "$MAIN_SHA"

python3 - <<'PY'
from pathlib import Path
shell=Path('src/inc/admin/admin-shell.php')
s=shell.read_text()
old="        'brand' => ['label' => '保存样式草稿', 'form' => 'vf-theme-brand-form', 'data' => 'data-vf-brand-save'],"
assert s.count(old)==1
shell.write_text(s.replace(old,"        'brand' => [],",1))

view=Path('src/inc/admin/views/brand.php')
s=view.read_text()
old='<section class="vf-brand-page" data-vf-brand-page'
assert s.count(old)==1
s=s.replace(old,'<section class="vf-brand-page vf-brand-page-v4" data-vf-brand-page',1)
old='<div><span>04 · 预览并保存</span><h2>确认候选视觉</h2><p data-vf-brand-change-summary>当前没有未保存变化。</p></div>\n            <button type="button" class="button" data-vf-brand-preview-diff disabled>对比变化</button>'
new='<div><span>04 · 预览并保存</span><h2>预览变化并保存</h2><p data-vf-brand-change-summary>当前没有未保存变化。</p></div>\n            <div class="vf-brand-preview-card__actions">\n              <button type="button" class="button" data-vf-brand-preview-diff disabled>对比变化</button>\n              <button type="submit" class="button button-primary" data-vf-brand-save>保存并验证前台</button>\n            </div>'
assert s.count(old)==1
view.write_text(s.replace(old,new,1))

css=Path('src/assets/css/admin/pages/brand/admin-page-brand.css')
s=css.read_text()
assert 'Theme Brand V4 — edit → preview → save as one visible flow.' not in s
css.write_text(s.rstrip()+"\n"+Path('/tmp/s01_brand_v4.css').read_text())

test=Path('tests/final-admin-human-closure-contract.php')
s=test.read_text()
old="$root=dirname(__DIR__);$brand=(string)file_get_contents($root.'/src/inc/admin/views/brand.php');$nav=(string)file_get_contents($root.'/src/inc/admin/views/navigation.php');$css=(string)file_get_contents($root.'/src/assets/css/admin/admin-s01-uiux-pages.css');"
new=old+"$shell=(string)file_get_contents($root.'/src/inc/admin/admin-shell.php');$brandCss=(string)file_get_contents($root.'/src/assets/css/admin/pages/brand/admin-page-brand.css');$brandJs=(string)file_get_contents($root.'/src/assets/js/admin/admin-brand.js');"
assert s.count(old)==1
s=s.replace(old,new,1)
marker='echo "PASS_THEME_FINAL_ADMIN_HUMAN_CLOSURE\\n";'
assert s.count(marker)==1
extra='''if(!str_contains($brand,'vf-brand-page-v4')||!str_contains($brand,'vf-brand-preview-card__actions')||!str_contains($brand,'data-vf-brand-save')||!str_contains($brand,'保存并验证前台')){fwrite(STDERR,"FAIL_BRAND_V4_FLOW\\n");exit(1);}\nif(substr_count($brand,'data-vf-brand-save')!==1||!str_contains($shell,"'brand' => [],")||str_contains($shell,"'brand' => ['label' => '保存样式草稿'")){fwrite(STDERR,"FAIL_BRAND_PRIMARY_OWNER\\n");exit(1);}\nforeach(['Theme Brand V4 — edit → preview → save as one visible flow.','.vf-brand-page-v4 .vf-brand-preview-card__actions','grid-template-columns:minmax(0,1fr) minmax(380px,430px)','@media(max-width:782px)'] as $x){if(!str_contains($brandCss,$x)){fwrite(STDERR,"FAIL_BRAND_V4_CSS:$x\\n");exit(1);}}\nforeach(["document.querySelector('[data-vf-brand-save]')","form.addEventListener('submit'"] as $x){if(!str_contains($brandJs,$x)){fwrite(STDERR,"FAIL_BRAND_SAVE_RUNTIME:$x\\n");exit(1);}}\n'''
s=s.replace(marker,extra+marker,1)
test.write_text(s)
PY

php -l src/inc/admin/admin-shell.php
php -l src/inc/admin/views/brand.php
php -l tests/final-admin-human-closure-contract.php
node --check src/assets/js/admin/admin-brand.js
find src -type f -name '*.php' -print0 | xargs -0 -n1 php -l >/dev/null
php tests/final-admin-human-closure-contract.php
php tests/deep-admin-human-language-contract.php
php tests/workbench-primary-action-contract.php
php tests/update-center-human-language-contract.php
php tests/update-refresh-policy-contract.php
php tests/visible-console-v2-contract.php

grep -F "'brand' => []," src/inc/admin/admin-shell.php >/dev/null
grep -F 'data-vf-brand-save>保存并验证前台' src/inc/admin/views/brand.php >/dev/null
grep -F 'Theme Brand V4 — edit → preview → save as one visible flow.' src/assets/css/admin/pages/brand/admin-page-brand.css >/dev/null

git diff --name-only "$BASE_SHA" | sort >/tmp/s01_actual
printf '%s\n' src/inc/admin/admin-shell.php src/inc/admin/views/brand.php src/assets/css/admin/pages/brand/admin-page-brand.css tests/final-admin-human-closure-contract.php | sort >/tmp/s01_expected
diff -u /tmp/s01_expected /tmp/s01_actual
git diff --check

git config user.name VictorForge
git config user.email llhzx2018@gmail.com
git add src/inc/admin/admin-shell.php src/inc/admin/views/brand.php src/assets/css/admin/pages/brand/admin-page-brand.css tests/final-admin-human-closure-contract.php
git commit -m 'refine(S01-C01): make Brand edit preview save flow explicit'
git push -q origin HEAD:"$BRANCH"
echo "THEME_BRAND_V4_HEAD=$(git rev-parse HEAD)"
echo 'PASS_S01_C01_BRAND_V4_CANDIDATE'
