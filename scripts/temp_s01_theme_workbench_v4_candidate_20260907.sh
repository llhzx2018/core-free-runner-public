#!/usr/bin/env bash
set -Eeuo pipefail
: "${WRITE_TOKEN:?}" "${REPO:?}" "${BRANCH:?}" "${BASE_SHA:?}" "${MAIN_SHA:?}"

echo 'MAIN_WRITE_USED=NO RELEASE_USED=NO DISTRIBUTION_USED=NO PRODUCTION_WRITE_USED=NO STATIC_WRITE_USED=NO ONLINE_WRITE_USED=NO'
cp fixtures/s01_theme_overview_v4_20260907.php /tmp/s01_theme_overview_v4.php
cp fixtures/s01_theme_workbench_v4_20260907.css /tmp/s01_theme_workbench_v4.css
rm -rf /tmp/s01-theme-workbench-v4
git clone -q "https://x-access-token:${WRITE_TOKEN}@github.com/${REPO}.git" /tmp/s01-theme-workbench-v4
cd /tmp/s01-theme-workbench-v4
git checkout -q "$BRANCH"
test "$(git rev-parse HEAD)" = "$BASE_SHA"
test "$(git rev-parse origin/main)" = "$MAIN_SHA"

cp /tmp/s01_theme_overview_v4.php src/inc/admin/views/tabs/overview.php
cp /tmp/s01_theme_workbench_v4.css src/assets/css/admin/pages/workbench/admin-page-workbench.css

python3 - <<'PY'
from pathlib import Path
shell = Path('src/inc/admin/admin-shell.php')
s = shell.read_text()
old = "        'overview' => ['label' => '打开前台预览', 'type' => 'link', 'url' => function_exists('home_url') ? home_url('/') : '/'],"
new = "        'overview' => [],"
assert s.count(old) == 1, s.count(old)
shell.write_text(s.replace(old, new, 1))

test = Path('tests/workbench-primary-action-contract.php')
s = test.read_text()
old = "$view = (string) file_get_contents($root . '/src/inc/admin/views/tabs/overview.php');"
new = old + "\n$shell = (string) file_get_contents($root . '/src/inc/admin/admin-shell.php');\n$css = (string) file_get_contents($root . '/src/assets/css/admin/pages/workbench/admin-page-workbench.css');"
assert s.count(old) == 1
s = s.replace(old, new, 1)
needle = "    'recovery_secondary' => str_contains($view, 'class=\"button\" href=\"<?php echo esc_url((string)($maintenance'),\n"
assert s.count(needle) == 1
extra = needle + "    'overview_header_has_no_competing_primary' => str_contains($shell, \"'overview' => [],\"),\n    'v4_page_owner' => str_contains($view, 'vf-workbench-v4') && str_contains($css, 'Theme workbench V4'),\n    'v4_status_hierarchy' => str_contains($view, 'vf-workbench-v4__status-heading') && str_contains($css, '.vf-workbench-v4__status-heading'),\n    'v4_workspace_cards' => str_contains($view, 'vf-workbench-v4__workspace-title') && str_contains($css, 'grid-template-columns:repeat(2,minmax(0,1fr))'),\n    'v4_mobile' => str_contains($css, '@media(max-width:700px)'),\n"
s = s.replace(needle, extra, 1)
marker = "if (substr_count($view, 'button-primary') !== 1) {"
assert s.count(marker) == 1
pre = "if (str_contains($shell, \"'overview' => ['label' => '打开前台预览'\")) {\n    fwrite(STDERR, \"FAIL_WORKBENCH_COMPETING_HEADER_PRIMARY\\n\");\n    exit(1);\n}\n\n"
s = s.replace(marker, pre + marker, 1)
test.write_text(s)
PY

php -l src/inc/admin/admin-shell.php
php -l src/inc/admin/views/tabs/overview.php
php -l tests/workbench-primary-action-contract.php
find src -type f -name '*.php' -print0 | xargs -0 -n1 php -l >/dev/null
php tests/workbench-primary-action-contract.php
php tests/update-center-human-language-contract.php
php tests/update-refresh-policy-contract.php
php tests/visible-console-v2-contract.php
php tests/final-admin-human-closure-contract.php
php tests/deep-admin-human-language-contract.php

grep -F "'overview' => []," src/inc/admin/admin-shell.php >/dev/null
grep -F 'vf-workbench-v4__status-heading' src/inc/admin/views/tabs/overview.php >/dev/null
grep -F 'grid-template-columns:repeat(2,minmax(0,1fr))' src/assets/css/admin/pages/workbench/admin-page-workbench.css >/dev/null

git diff --name-only "$BASE_SHA" | sort >/tmp/s01_actual
git diff --name-only "$BASE_SHA" -- src/inc/admin/admin-shell.php src/inc/admin/views/tabs/overview.php src/assets/css/admin/pages/workbench/admin-page-workbench.css tests/workbench-primary-action-contract.php | sort >/tmp/s01_expected
printf '%s\n' src/inc/admin/admin-shell.php src/inc/admin/views/tabs/overview.php src/assets/css/admin/pages/workbench/admin-page-workbench.css tests/workbench-primary-action-contract.php | sort >/tmp/s01_expected_names
diff -u /tmp/s01_expected_names /tmp/s01_actual
git diff --check

git config user.name VictorForge
git config user.email llhzx2018@gmail.com
git add src/inc/admin/admin-shell.php src/inc/admin/views/tabs/overview.php src/assets/css/admin/pages/workbench/admin-page-workbench.css tests/workbench-primary-action-contract.php
git commit -m 'refine(S01-C01): rebuild Theme overview workbench hierarchy'
git push -q origin HEAD:"$BRANCH"
echo "THEME_WORKBENCH_V4_HEAD=$(git rev-parse HEAD)"
echo 'PASS_S01_C01_WORKBENCH_V4_CANDIDATE'
